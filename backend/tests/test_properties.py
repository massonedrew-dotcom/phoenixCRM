import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditAction, AuditEntity
from app.models import District, Property
from tests import factories
from tests.factories import Team, TeamHeaders

ROLES = ["admin", "head", "agent"]


@pytest.fixture
async def own_card(session: AsyncSession, users: Team, district: District) -> Property:
    """A card created by `agent`."""
    return await factories.create_property(session, users.agent, district)


@pytest.fixture
async def foreign_card(session: AsyncSession, users: Team, district: District) -> Property:
    """A card created by `other_agent`."""
    return await factories.create_property(session, users.other_agent, district)


# --- permission matrix -------------------------------------------------------------------------


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_searches_and_reads_any_card(
    client: AsyncClient, headers: TeamHeaders, foreign_card: Property, role: str
) -> None:
    auth = headers.for_role(role)

    listing = await client.get("/api/v1/properties", headers=auth)
    detail = await client.get(f"/api/v1/properties/{foreign_card.id}", headers=auth)

    assert listing.status_code == 200
    assert str(foreign_card.id) in {item["id"] for item in listing.json()["items"]}
    assert detail.status_code == 200
    # Owner phone numbers are visible to every authenticated user (PRD §3).
    assert detail.json()["owner_phone"] == "+998 90 123-45-67"


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_creates_cards(
    client: AsyncClient, headers: TeamHeaders, users: Team, district: District, role: str
) -> None:
    response = await client.post(
        "/api/v1/properties",
        json=factories.property_payload(district),
        headers=headers.for_role(role),
    )

    assert response.status_code == 201
    assert response.json()["created_by"]["id"] == str(getattr(users, role).id)
    assert response.json()["can_edit"] is True


@pytest.mark.parametrize(
    ("role", "card", "expected"),
    [
        ("admin", "foreign_card", 200),
        ("head", "foreign_card", 200),
        ("agent", "own_card", 200),
        ("agent", "foreign_card", 403),
    ],
)
async def test_update_permissions(
    client: AsyncClient,
    headers: TeamHeaders,
    own_card: Property,
    foreign_card: Property,
    role: str,
    card: str,
    expected: int,
) -> None:
    record = own_card if card == "own_card" else foreign_card

    response = await client.patch(
        f"/api/v1/properties/{record.id}",
        json={"note": "новая заметка"},
        headers=headers.for_role(role),
    )

    assert response.status_code == expected


@pytest.mark.parametrize(
    ("role", "card", "expected"),
    [
        ("admin", "foreign_card", 204),
        ("head", "foreign_card", 204),
        ("agent", "own_card", 204),
        ("agent", "foreign_card", 403),
    ],
)
async def test_delete_permissions(
    client: AsyncClient,
    headers: TeamHeaders,
    own_card: Property,
    foreign_card: Property,
    role: str,
    card: str,
    expected: int,
) -> None:
    record = own_card if card == "own_card" else foreign_card

    response = await client.delete(
        f"/api/v1/properties/{record.id}", headers=headers.for_role(role)
    )

    assert response.status_code == expected


@pytest.mark.parametrize(("role", "expected"), [("admin", 200), ("head", 200), ("agent", 403)])
async def test_restore_permissions(
    client: AsyncClient, headers: TeamHeaders, own_card: Property, role: str, expected: int
) -> None:
    await client.delete(f"/api/v1/properties/{own_card.id}", headers=headers.agent)

    response = await client.post(
        f"/api/v1/properties/{own_card.id}/restore", headers=headers.for_role(role)
    )

    assert response.status_code == expected


@pytest.mark.parametrize("role", ROLES)
async def test_every_role_reads_history_of_any_card(
    client: AsyncClient, headers: TeamHeaders, foreign_card: Property, role: str
) -> None:
    response = await client.get(
        f"/api/v1/properties/{foreign_card.id}/history", headers=headers.for_role(role)
    )

    assert response.status_code == 200


@pytest.mark.parametrize(("role", "expected"), [("admin", 200), ("head", 200), ("agent", 403)])
async def test_deleted_list_permissions(
    client: AsyncClient, headers: TeamHeaders, role: str, expected: int
) -> None:
    response = await client.get("/api/v1/properties/deleted", headers=headers.for_role(role))

    assert response.status_code == expected


async def test_property_endpoints_require_authentication(
    client: AsyncClient, own_card: Property
) -> None:
    base = f"/api/v1/properties/{own_card.id}"
    for method, url in [
        ("GET", "/api/v1/properties"),
        ("POST", "/api/v1/properties"),
        ("GET", base),
        ("PATCH", base),
        ("DELETE", base),
        ("POST", f"{base}/restore"),
        ("GET", f"{base}/history"),
        ("GET", "/api/v1/properties/deleted"),
    ]:
        response = await client.request(method, url, json={})
        assert response.status_code == 401, f"{method} {url}"


# --- behaviour ---------------------------------------------------------------------------------


async def test_create_returns_detail_with_price_in_uzs(
    client: AsyncClient, headers: TeamHeaders, district: District
) -> None:
    response = await client.post(
        "/api/v1/properties",
        json=factories.property_payload(district, price="350.50"),
        headers=headers.agent,
    )

    body = response.json()
    assert body["price"] == "350.50"
    assert body["price_uzs"] == "4206000.00"
    assert body["district"] == {"id": str(district.id), "name": "Чиланзарский"}
    assert body["deal_type"] == "rent"
    assert body["code"] > 0
    assert body["media"] == []


async def test_server_owned_fields_in_payload_are_ignored(
    client: AsyncClient, headers: TeamHeaders, users: Team, district: District
) -> None:
    payload = factories.property_payload(
        district,
        created_by=str(users.admin.id),
        updated_by=str(users.admin.id),
        created_at="2001-01-01T00:00:00Z",
        updated_at="2001-01-01T00:00:00Z",
        code=999999,
        is_deleted=True,
        price_uzs="1",
    )

    created = await client.post("/api/v1/properties", json=payload, headers=headers.agent)

    body = created.json()
    assert created.status_code == 201
    assert body["created_by"]["id"] == str(users.agent.id)
    assert body["created_at"][:4] != "2001"
    assert body["code"] != 999999
    assert body["is_deleted"] is False
    assert body["updated_by"] is None
    assert body["price_uzs"] == "4200000.00"

    patched = await client.patch(
        f"/api/v1/properties/{body['id']}",
        json={"note": "x", "created_by": str(users.admin.id), "is_deleted": True, "code": 1},
        headers=headers.agent,
    )
    assert patched.json()["created_by"]["id"] == str(users.agent.id)
    assert patched.json()["is_deleted"] is False
    assert patched.json()["code"] == body["code"]
    assert patched.json()["updated_by"]["id"] == str(users.agent.id)


async def test_create_writes_audit_row_per_populated_field(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, district: District
) -> None:
    response = await client.post(
        "/api/v1/properties",
        json=factories.property_payload(district, owner_name=None, note=""),
        headers=headers.agent,
    )

    rows = await factories.audit_rows(
        session, AuditEntity.PROPERTY, uuid.UUID(response.json()["id"])
    )
    assert all(r.action == AuditAction.CREATE and r.old_value is None for r in rows)
    assert {r.field for r in rows} == {
        "request_no",
        "district_id",
        "landmark",
        "owner_phone",
        "interest_status",
        "free_until",
        "price",
    }


@pytest.mark.parametrize(
    "payload",
    [
        {"landmark": "  "},
        {"owner_phone": "12"},
        {"owner_phone": "звоните"},
        {"price": "-1"},
        {"district_id": None},
    ],
)
async def test_invalid_create_payload_is_rejected(
    client: AsyncClient, headers: TeamHeaders, district: District, payload: dict[str, object]
) -> None:
    response = await client.post(
        "/api/v1/properties",
        json=factories.property_payload(district, **payload),
        headers=headers.agent,
    )

    assert response.status_code == 422


@pytest.mark.parametrize("field", ["landmark", "owner_phone", "district_id", "interest_status"])
async def test_required_fields_cannot_be_cleared(
    client: AsyncClient, headers: TeamHeaders, own_card: Property, field: str
) -> None:
    response = await client.patch(
        f"/api/v1/properties/{own_card.id}", json={field: None}, headers=headers.agent
    )

    assert response.status_code == 422


async def test_patch_changes_only_supplied_fields(
    client: AsyncClient, headers: TeamHeaders, own_card: Property
) -> None:
    before = (await client.get(f"/api/v1/properties/{own_card.id}", headers=headers.agent)).json()

    response = await client.patch(
        f"/api/v1/properties/{own_card.id}", json={"note": "только заметка"}, headers=headers.agent
    )

    after = response.json()
    changed = {key for key in before if before[key] != after[key]}
    assert changed == {"note", "updated_by", "updated_at"}


async def test_soft_delete_hides_card_from_agents_and_keeps_it_for_managers(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    own_card: Property,
) -> None:
    url = f"/api/v1/properties/{own_card.id}"
    card_id, admin_id = own_card.id, users.admin.id

    assert (await client.delete(url, headers=headers.agent)).status_code == 204

    assert (await client.get(url, headers=headers.agent)).status_code == 404
    assert (await client.get(f"{url}/history", headers=headers.agent)).status_code == 404
    detail = await client.get(url, headers=headers.head)
    assert detail.status_code == 200
    assert detail.json()["is_deleted"] is True
    assert detail.json()["can_edit"] is False
    assert (await client.patch(url, json={"note": "x"}, headers=headers.head)).status_code == 409
    assert (await client.delete(url, headers=headers.head)).status_code == 409

    deleted = (await client.get("/api/v1/properties/deleted", headers=headers.head)).json()
    assert deleted["total"] == 1
    assert deleted["items"][0]["deleted_by_name"] == "Агент Первый"

    session.expire_all()
    row = await session.get(Property, card_id)
    assert row is not None and row.is_deleted is True

    restored = await client.post(f"{url}/restore", headers=headers.admin)
    assert restored.json()["is_deleted"] is False
    assert (await client.get(url, headers=headers.agent)).status_code == 200

    history = (await client.get(f"{url}/history", headers=headers.agent)).json()
    assert [(entry["action"], entry["field"]) for entry in history[:2]] == [
        ("restore", None),
        ("delete", None),
    ]
    assert history[0]["user"]["id"] == str(admin_id)


async def test_restore_of_active_card_is_conflict(
    client: AsyncClient, headers: TeamHeaders, own_card: Property
) -> None:
    response = await client.post(f"/api/v1/properties/{own_card.id}/restore", headers=headers.head)

    assert response.status_code == 409


async def test_unknown_card_is_not_found(client: AsyncClient, headers: TeamHeaders) -> None:
    missing = uuid.uuid4()

    assert (
        await client.get(f"/api/v1/properties/{missing}", headers=headers.admin)
    ).status_code == 404
    response = await client.patch(
        f"/api/v1/properties/{missing}", json={"note": "x"}, headers=headers.admin
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Карточка не найдена", "code": "NOT_FOUND"}
