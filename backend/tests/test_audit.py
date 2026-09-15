import uuid
from datetime import date
from decimal import Decimal

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import FieldChange, diff_values, initial_values, to_audit_text
from app.core.enums import AuditAction, AuditEntity, InterestStatus
from app.models import District, Property
from app.services import properties as properties_service
from tests import factories
from tests.factories import Team, TeamHeaders


def test_to_audit_text_formats_values() -> None:
    identifier = uuid.UUID("12345678-1234-5678-1234-567812345678")

    assert to_audit_text(None) is None
    assert to_audit_text(True) == "true"
    assert to_audit_text(Decimal("350.50")) == "350.50"
    assert to_audit_text(date(2026, 10, 1)) == "2026-10-01"
    assert to_audit_text(InterestStatus.HOT) == "hot"
    assert to_audit_text(identifier) == str(identifier)


def test_diff_values_reports_only_changed_fields() -> None:
    old = {"landmark": "a", "price": Decimal("350.00"), "note": None}
    new = {"landmark": "b", "price": Decimal(350), "note": "x"}

    assert diff_values(old, new) == [
        FieldChange("landmark", "a", "b"),
        FieldChange("note", None, "x"),
    ]


def test_initial_values_skip_empty_fields() -> None:
    assert initial_values({"landmark": "a", "note": None}) == [FieldChange("landmark", None, "a")]


async def test_update_writes_one_row_per_changed_field_with_old_and_new_values(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    record = await factories.create_property(
        session, users.agent, district, interest_status=InterestStatus.WARM, price=Decimal(300)
    )

    response = await client.patch(
        f"/api/v1/properties/{record.id}",
        json={
            "interest_status": "hot",
            "price": "350.00",
            "landmark": "рядом с метро Чиланзар, дом 9",  # unchanged
            "occupied_until": "2026-12-31",
        },
        headers=headers.agent,
    )

    assert response.status_code == 200
    rows = await factories.audit_rows(session, AuditEntity.PROPERTY, record.id)
    assert sorted((r.field, r.old_value, r.new_value) for r in rows) == [
        ("interest_status", "warm", "hot"),
        ("occupied_until", None, "2026-12-31"),
        ("price", "300.00", "350.00"),
    ]
    assert all(r.action == AuditAction.UPDATE and r.user_id == users.agent.id for r in rows)
    assert all(str(r.ip) == "127.0.0.1" for r in rows)
    assert len({r.created_at for r in rows}) == 1, "rows belong to one transaction"


async def test_patch_without_real_changes_writes_nothing(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    record = await factories.create_property(session, users.agent, district)

    response = await client.patch(
        f"/api/v1/properties/{record.id}",
        json={"owner_phone": "+998 90 123-45-67"},
        headers=headers.agent,
    )

    assert response.status_code == 200
    assert response.json()["updated_at"] is None
    assert await factories.audit_rows(session, AuditEntity.PROPERTY, record.id) == []


async def test_mutation_rolls_back_when_audit_write_fails(
    app: FastAPI,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = await factories.create_property(session, users.agent, district, note="до")
    record_id = record.id

    async def failing_audit(*args: object, **kwargs: object) -> None:
        raise RuntimeError("audit storage unavailable")

    monkeypatch.setattr(properties_service, "write_audit", failing_audit)

    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.patch(
            f"/api/v1/properties/{record_id}", json={"note": "после"}, headers=headers.agent
        )

    assert response.status_code == 500
    assert response.json()["code"] == "INTERNAL_ERROR"
    session.expire_all()
    note = await session.scalar(select(Property.note).where(Property.id == record_id))
    assert note == "до"


async def test_audit_feed_permissions_and_filters(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    created = await client.post(
        "/api/v1/properties", json=factories.property_payload(district), headers=headers.agent
    )
    property_id = created.json()["id"]

    assert (await client.get("/api/v1/audit", headers=headers.agent)).status_code == 403
    for role_headers in (headers.head, headers.admin):
        response = await client.get(
            "/api/v1/audit",
            params={"entity": "property", "entity_id": property_id, "page_size": 5},
            headers=role_headers,
        )
        assert response.status_code == 200
        body = response.json()
        assert body["page_size"] == 5
        assert body["total"] >= len(body["items"]) > 0
        assert {item["entity_id"] for item in body["items"]} == {property_id}
        assert body["items"][0]["user"] == {
            "id": str(users.agent.id),
            "full_name": "Агент Первый",
        }
