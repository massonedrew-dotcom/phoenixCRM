import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.cli import TASHKENT_DISTRICTS
from app.core.enums import AuditEntity
from app.models import District
from app.services import districts as districts_service
from tests import factories
from tests.factories import Team, TeamHeaders


@pytest.mark.parametrize("role", ["admin", "head", "agent"])
async def test_every_role_lists_districts_including_inactive(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, role: str
) -> None:
    await factories.create_district(session, "Бектемирский", is_active=False)
    await factories.create_district(session, "Алмазарский")

    response = await client.get("/api/v1/districts", headers=headers.for_role(role))

    assert response.status_code == 200
    names = [item["name"] for item in response.json()]
    assert names == sorted(names)
    assert {"Бектемирский", "Алмазарский"} <= set(names)


@pytest.mark.parametrize(("role", "expected"), [("admin", 201), ("head", 403), ("agent", 403)])
async def test_create_district_permissions(
    client: AsyncClient, headers: TeamHeaders, role: str, expected: int
) -> None:
    response = await client.post(
        "/api/v1/districts", json={"name": "  Сергелийский "}, headers=headers.for_role(role)
    )

    assert response.status_code == expected
    if expected == 201:
        assert response.json()["name"] == "Сергелийский"


@pytest.mark.parametrize(("role", "expected"), [("admin", 200), ("head", 403), ("agent", 403)])
async def test_update_district_permissions(
    client: AsyncClient, headers: TeamHeaders, district: District, role: str, expected: int
) -> None:
    response = await client.patch(
        f"/api/v1/districts/{district.id}",
        json={"is_active": False},
        headers=headers.for_role(role),
    )

    assert response.status_code == expected


async def test_duplicate_district_name_is_conflict(
    client: AsyncClient, headers: TeamHeaders, district: District
) -> None:
    response = await client.post(
        "/api/v1/districts", json={"name": district.name}, headers=headers.admin
    )

    assert response.status_code == 409
    assert response.json()["code"] == "DISTRICT_EXISTS"


async def test_district_changes_are_audited(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    await client.patch(
        f"/api/v1/districts/{district.id}",
        json={"name": "Чиланзар", "is_active": False},
        headers=headers.admin,
    )

    rows = await factories.audit_rows(session, AuditEntity.DISTRICT, district.id)
    assert sorted((r.field, r.old_value, r.new_value) for r in rows) == [
        ("is_active", "true", "false"),
        ("name", "Чиланзарский", "Чиланзар"),
    ]


async def test_card_cannot_use_inactive_district(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, users: Team
) -> None:
    inactive = await factories.create_district(session, "Закрытый", is_active=False)
    active = await factories.create_district(session, "Открытый")

    created = await client.post(
        "/api/v1/properties", json=factories.property_payload(inactive), headers=headers.agent
    )
    assert created.status_code == 400
    assert created.json()["code"] == "DISTRICT_INACTIVE"

    record = await factories.create_property(session, users.agent, active)
    active.is_active = False
    await session.flush()
    # A card already in a deactivated district can still be edited.
    edited = await client.patch(
        f"/api/v1/properties/{record.id}", json={"note": "уточнено"}, headers=headers.agent
    )
    assert edited.status_code == 200
    moved = await client.patch(
        f"/api/v1/properties/{record.id}",
        json={"district_id": str(inactive.id)},
        headers=headers.agent,
    )
    assert moved.status_code == 400


async def test_seed_districts_is_idempotent(session: AsyncSession) -> None:
    first = await districts_service.seed_districts(session, TASHKENT_DISTRICTS)
    second = await districts_service.seed_districts(session, TASHKENT_DISTRICTS)

    assert len(first) == 12
    assert second == []
