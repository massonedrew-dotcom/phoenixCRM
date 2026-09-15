import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditAction, AuditEntity
from app.models import District, Property
from app.storage import processing
from tests import factories
from tests.factories import Team, TeamHeaders


@pytest.fixture
async def card(session: AsyncSession, users: Team, district: District) -> Property:
    return await factories.create_property(session, users.agent, district)


async def upload(
    client: AsyncClient,
    card_id: uuid.UUID,
    headers: dict[str, str],
    files: list[tuple[str, bytes, str]],
) -> dict[str, Any]:
    response = await client.post(
        f"/api/v1/properties/{card_id}/media",
        files=[("files", item) for item in files],
        headers=headers,
    )
    return {"status": response.status_code, "body": response.json()}


def test_detect_type_uses_file_signature() -> None:
    assert processing.detect_type(factories.image_bytes("JPEG")[:32]) == processing.JPEG
    assert processing.detect_type(factories.image_bytes("PNG")[:32]) == processing.PNG
    assert processing.detect_type(factories.image_bytes("WEBP")[:32]) == processing.WEBP
    assert processing.detect_type(factories.mp4_bytes()[:32]) == processing.MP4
    assert processing.detect_type(b"%PDF-1.7 not an image") is None
    assert processing.detect_type(b"GIF89a") is None


async def test_upload_photos_creates_files_thumbnails_and_order(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    card: Property,
    media_root: Path,
) -> None:
    result = await upload(
        client,
        card.id,
        headers.agent,
        [
            ("фасад.jpg", factories.image_bytes("JPEG"), "image/jpeg"),
            ("plan.png", factories.image_bytes("PNG", (300, 900)), "image/png"),
        ],
    )

    assert result["status"] == 201
    records = result["body"]
    assert [(r["original_name"], r["sort_order"], r["kind"]) for r in records] == [
        ("фасад.jpg", 0, "photo"),
        ("plan.png", 1, "photo"),
    ]
    assert records[1]["mime_type"] == "image/png"
    for record in records:
        assert record["url"].startswith(f"/api/v1/media/{record['id']}/file?variant=original")
        assert record["thumb_url"] is not None

    stored = sorted(path.relative_to(media_root).as_posix() for path in media_root.rglob("*.*"))
    assert len(stored) == 4
    assert sum("/thumbs/" in path and path.endswith(".webp") for path in stored) == 2
    thumbnail = next(path for path in media_root.rglob("*.webp"))
    with Image.open(thumbnail) as image:
        assert max(image.size) <= 480

    more = await upload(
        client,
        card.id,
        headers.agent,
        [("third.webp", factories.image_bytes("WEBP"), "image/webp")],
    )
    assert more["body"][0]["sort_order"] == 2

    detail = (await client.get(f"/api/v1/properties/{card.id}", headers=headers.agent)).json()
    assert [m["original_name"] for m in detail["media"]] == ["фасад.jpg", "plan.png", "third.webp"]

    rows = await factories.audit_rows(session, AuditEntity.MEDIA, uuid.UUID(records[0]["id"]))
    assert {(r.action, r.field, r.new_value) for r in rows} >= {
        (AuditAction.CREATE, "original_name", "фасад.jpg"),
        (AuditAction.CREATE, "kind", "photo"),
    }


async def test_client_content_type_is_not_trusted(
    client: AsyncClient, headers: TeamHeaders, card: Property, media_root: Path
) -> None:
    result = await upload(
        client, card.id, headers.agent, [("evil.jpg", b"<?php echo 'hi'; ?>", "image/jpeg")]
    )

    assert result["status"] == 415
    assert result["body"]["code"] == "UNSUPPORTED_MEDIA_TYPE"
    assert list(media_root.rglob("*.*")) == []


async def test_one_bad_file_rejects_the_whole_batch(
    client: AsyncClient, headers: TeamHeaders, card: Property, media_root: Path
) -> None:
    result = await upload(
        client,
        card.id,
        headers.agent,
        [
            ("ok.jpg", factories.image_bytes("JPEG"), "image/jpeg"),
            ("doc.pdf", b"%PDF-1.7 ...", "application/pdf"),
        ],
    )

    assert result["status"] == 415
    assert list(media_root.rglob("*.*")) == []


async def test_corrupted_image_is_rejected(
    client: AsyncClient, headers: TeamHeaders, card: Property
) -> None:
    broken = factories.image_bytes("JPEG")[:40]

    result = await upload(client, card.id, headers.agent, [("broken.jpg", broken, "image/jpeg")])

    assert result["status"] == 415


async def test_oversize_file_is_rejected(
    app: FastAPI, client: AsyncClient, headers: TeamHeaders, card: Property, media_root: Path
) -> None:
    app.state.settings.max_photo_mb = 1
    # A valid PNG followed by trailing bytes: the size check runs before decoding.
    oversized = factories.image_bytes("PNG") + b"\x00" * (1024 * 1024)

    result = await upload(client, card.id, headers.agent, [("huge.png", oversized, "image/png")])

    assert result["status"] == 413
    assert result["body"]["code"] == "FILE_TOO_LARGE"
    assert list(media_root.rglob("*.*")) == []


async def test_video_upload_without_poster_is_accepted(
    client: AsyncClient,
    headers: TeamHeaders,
    card: Property,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.storage.processing.shutil.which", lambda _: None)

    result = await upload(
        client, card.id, headers.agent, [("tour.mp4", factories.mp4_bytes(), "video/mp4")]
    )

    assert result["status"] == 201
    record = result["body"][0]
    assert (record["kind"], record["mime_type"], record["thumb_url"]) == (
        "video",
        "video/mp4",
        None,
    )


@pytest.mark.parametrize(
    ("role", "expected"), [("admin", 201), ("head", 201), ("other_agent", 403)]
)
async def test_upload_follows_card_edit_permission(
    client: AsyncClient, headers: TeamHeaders, card: Property, role: str, expected: int
) -> None:
    result = await upload(
        client,
        card.id,
        headers.for_role(role),
        [("a.jpg", factories.image_bytes("JPEG"), "image/jpeg")],
    )

    assert result["status"] == expected


async def test_reorder_and_delete_media(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, card: Property
) -> None:
    records = (
        await upload(
            client,
            card.id,
            headers.agent,
            [(f"{n}.jpg", factories.image_bytes("JPEG"), "image/jpeg") for n in ("a", "b", "c")],
        )
    )["body"]
    first, second, third = (record["id"] for record in records)

    forbidden = await client.patch(
        f"/api/v1/media/{third}", json={"sort_order": 0}, headers=headers.other_agent
    )
    assert forbidden.status_code == 403
    for media_id, order in ((third, 0), (first, 1), (second, 2)):
        response = await client.patch(
            f"/api/v1/media/{media_id}", json={"sort_order": order}, headers=headers.agent
        )
        assert response.status_code == 200

    detail = (await client.get(f"/api/v1/properties/{card.id}", headers=headers.agent)).json()
    assert [m["original_name"] for m in detail["media"]] == ["c.jpg", "a.jpg", "b.jpg"]

    assert (await client.delete(f"/api/v1/media/{first}", headers=headers.agent)).status_code == 204
    detail = (await client.get(f"/api/v1/properties/{card.id}", headers=headers.agent)).json()
    assert [m["original_name"] for m in detail["media"]] == ["c.jpg", "b.jpg"]
    assert (await client.delete(f"/api/v1/media/{first}", headers=headers.agent)).status_code == 404

    reorder_rows = await factories.audit_rows(session, AuditEntity.MEDIA, uuid.UUID(third))
    assert (AuditAction.UPDATE, "sort_order", "2", "0") in {
        (r.action, r.field, r.old_value, r.new_value) for r in reorder_rows
    }
    history = (
        await client.get(f"/api/v1/properties/{card.id}/history", headers=headers.agent)
    ).json()
    assert {"media"} <= {entry["entity"] for entry in history}
    assert any(e["entity"] == "media" and e["action"] == "delete" for e in history)


async def test_file_endpoint_uses_signed_url_and_accel_redirect(
    client: AsyncClient, headers: TeamHeaders, card: Property
) -> None:
    record = (
        await upload(
            client,
            card.id,
            headers.agent,
            [("вид.jpg", factories.image_bytes("JPEG"), "image/jpeg")],
        )
    )["body"][0]

    original = await client.get(record["url"])
    thumb = await client.get(record["thumb_url"])

    assert original.status_code == 200
    assert original.content == b""
    assert original.headers["x-accel-redirect"].startswith(f"/internal-media/properties/{card.id}/")
    assert original.headers["content-type"] == "image/jpeg"
    assert "filename*=UTF-8''%D0%B2%D0%B8%D0%B4.jpg" in original.headers["content-disposition"]
    assert thumb.headers["x-accel-redirect"].endswith(".webp")

    tampered = record["url"][:-4] + "0000"
    assert (await client.get(tampered)).status_code == 401
    no_token = record["url"].split("&token=")[0]
    assert (await client.get(no_token)).status_code == 401
    assert (await client.get(no_token, headers=headers.other_agent)).status_code == 200
    swapped = record["url"].replace("variant=original", "variant=thumb")
    assert (await client.get(swapped)).status_code == 401


async def test_media_of_deleted_card_is_hidden_and_returns_on_restore(
    client: AsyncClient, headers: TeamHeaders, card: Property
) -> None:
    record = (
        await upload(
            client, card.id, headers.agent, [("a.jpg", factories.image_bytes("JPEG"), "image/jpeg")]
        )
    )["body"][0]

    await client.delete(f"/api/v1/properties/{card.id}", headers=headers.agent)

    assert (await client.get(record["url"])).status_code == 404
    assert (
        await client.patch(
            f"/api/v1/media/{record['id']}", json={"sort_order": 5}, headers=headers.head
        )
    ).status_code == 404
    upload_to_deleted = await upload(
        client, card.id, headers.head, [("b.jpg", factories.image_bytes("JPEG"), "image/jpeg")]
    )
    assert upload_to_deleted["status"] == 404

    await client.post(f"/api/v1/properties/{card.id}/restore", headers=headers.head)
    assert (await client.get(record["url"])).status_code == 200
    detail = (await client.get(f"/api/v1/properties/{card.id}", headers=headers.agent)).json()
    assert [m["id"] for m in detail["media"]] == [record["id"]]
