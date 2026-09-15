from datetime import UTC, datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import District, Property, PropertyView
from tests import factories
from tests.factories import Team, TeamHeaders


@pytest.fixture
async def cards(session: AsyncSession, users: Team, district: District) -> list[Property]:
    return [
        await factories.create_property(session, users.head, district, landmark=f"дом {n}")
        for n in range(3)
    ]


async def view_count(session: AsyncSession, **filters: object) -> int:
    statement = select(func.count()).select_from(PropertyView).filter_by(**filters)
    return int(await session.scalar(statement) or 0)


async def test_opening_a_card_is_journaled_once_per_window(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    cards: list[Property],
) -> None:
    card_id, agent_id = cards[0].id, users.agent.id

    for _ in range(3):
        response = await client.get(f"/api/v1/properties/{card_id}", headers=headers.agent)
        assert response.status_code == 200

    assert await view_count(session, property_id=card_id, user_id=agent_id) == 1
    row = await session.scalar(select(PropertyView).where(PropertyView.user_id == agent_id))
    assert row is not None and str(row.ip) == "127.0.0.1"


async def test_a_view_older_than_the_window_counts_again(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    cards: list[Property],
) -> None:
    card_id, agent_id = cards[0].id, users.agent.id
    session.add(
        PropertyView(
            property_id=card_id,
            user_id=agent_id,
            viewed_at=datetime.now(UTC) - timedelta(minutes=11),
        )
    )
    await session.flush()

    await client.get(f"/api/v1/properties/{card_id}", headers=headers.agent)

    assert await view_count(session, property_id=card_id, user_id=agent_id) == 2


async def test_search_and_history_do_not_count_as_views(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, cards: list[Property]
) -> None:
    await client.get("/api/v1/properties", headers=headers.agent)
    await client.get(f"/api/v1/properties/{cards[0].id}/history", headers=headers.agent)

    assert await view_count(session) == 0


async def test_failed_open_is_not_journaled(
    client: AsyncClient, session: AsyncSession, headers: TeamHeaders, cards: list[Property]
) -> None:
    card_id = cards[0].id
    await client.delete(f"/api/v1/properties/{card_id}", headers=headers.head)

    response = await client.get(f"/api/v1/properties/{card_id}", headers=headers.agent)

    assert response.status_code == 404
    assert await view_count(session) == 0


async def test_view_journal_is_append_only(
    session: AsyncSession, users: Team, cards: list[Property]
) -> None:
    view = PropertyView(property_id=cards[0].id, user_id=users.agent.id)
    session.add(view)
    await session.flush()

    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(
                update(PropertyView).where(PropertyView.id == view.id).values(ip="10.0.0.1")
            )
    with pytest.raises(DBAPIError, match="append-only"):
        async with session.begin_nested():
            await session.execute(delete(PropertyView).where(PropertyView.id == view.id))


@pytest.mark.parametrize(("role", "expected"), [("admin", 200), ("head", 200), ("agent", 403)])
async def test_view_endpoints_are_for_managers_only(
    client: AsyncClient, headers: TeamHeaders, role: str, expected: int
) -> None:
    auth = headers.for_role(role)

    assert (await client.get("/api/v1/views/summary", headers=auth)).status_code == expected
    assert (await client.get("/api/v1/views", headers=auth)).status_code == expected


async def test_summary_and_list_show_who_opened_what(
    client: AsyncClient, headers: TeamHeaders, users: Team, cards: list[Property]
) -> None:
    for card in cards:
        await client.get(f"/api/v1/properties/{card.id}", headers=headers.agent)
    await client.get(f"/api/v1/properties/{cards[0].id}", headers=headers.other_agent)

    summary = (await client.get("/api/v1/views/summary", headers=headers.admin)).json()
    listing = (
        await client.get(
            "/api/v1/views", params={"user_id": str(users.agent.id)}, headers=headers.admin
        )
    ).json()
    by_card = (
        await client.get(
            "/api/v1/views", params={"property_code": cards[0].code}, headers=headers.admin
        )
    ).json()

    assert [(row["full_name"], row["cards"], row["views"]) for row in summary] == [
        ("Агент Первый", 3, 3),
        ("Агент Второй", 1, 1),
    ]
    assert summary[0]["role"] == "agent"
    assert listing["total"] == 3
    assert {item["property"]["code"] for item in listing["items"]} == {c.code for c in cards}
    assert listing["items"][0]["user"]["full_name"] == "Агент Первый"
    assert by_card["total"] == 2


async def test_summary_period_uses_tashkent_days(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    cards: list[Property],
) -> None:
    session.add(
        PropertyView(
            property_id=cards[0].id,
            user_id=users.agent.id,
            viewed_at=datetime(2026, 3, 1, 19, 30, tzinfo=UTC),  # 2 March 00:30 in Tashkent
        )
    )
    await session.flush()

    march_first = await client.get(
        "/api/v1/views/summary",
        params={"date_from": "2026-03-01", "date_to": "2026-03-01"},
        headers=headers.admin,
    )
    march_second = await client.get(
        "/api/v1/views/summary",
        params={"date_from": "2026-03-02", "date_to": "2026-03-02"},
        headers=headers.admin,
    )

    assert march_first.json() == []
    assert [row["views"] for row in march_second.json()] == [1]


async def test_audit_feed_names_the_card_and_subject(
    client: AsyncClient, headers: TeamHeaders, users: Team, district: District
) -> None:
    created = (
        await client.post(
            "/api/v1/properties", json=factories.property_payload(district), headers=headers.agent
        )
    ).json()
    await client.post(
        f"/api/v1/properties/{created['id']}/media",
        files=[("files", ("a.jpg", factories.image_bytes("JPEG"), "image/jpeg"))],
        headers=headers.agent,
    )
    await client.patch(
        f"/api/v1/users/{users.other_agent.id}",
        json={"full_name": "Агент Переименованный"},
        headers=headers.admin,
    )

    by_card = (
        await client.get(
            "/api/v1/audit", params={"property_code": created["code"]}, headers=headers.head
        )
    ).json()
    user_rows = (
        await client.get("/api/v1/audit", params={"entity": "user"}, headers=headers.head)
    ).json()

    assert {item["entity"] for item in by_card["items"]} == {"property", "media"}
    assert {item["property_code"] for item in by_card["items"]} == {created["code"]}
    assert {item["property_id"] for item in by_card["items"]} == {created["id"]}
    renamed = next(item for item in user_rows["items"] if item["field"] == "full_name")
    assert renamed["subject_name"] == "Агент Переименованный"


async def test_search_list_shows_last_change(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    cards: list[Property],
) -> None:
    await client.patch(
        f"/api/v1/properties/{cards[1].id}", json={"note": "обновлено"}, headers=headers.admin
    )

    items = (await client.get("/api/v1/properties", headers=headers.agent)).json()["items"]

    changed = next(item for item in items if item["id"] == str(cards[1].id))
    untouched = next(item for item in items if item["id"] == str(cards[0].id))
    assert changed["updated_by_name"] == "Админ Админов"
    assert changed["updated_at"] is not None
    assert (untouched["updated_by_name"], untouched["updated_at"]) == (None, None)
