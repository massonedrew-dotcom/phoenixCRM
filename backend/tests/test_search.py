from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import InterestStatus, MediaKind
from app.models import District, Property, PropertyMedia
from tests import factories
from tests.factories import Team, TeamHeaders

TASHKENT = ZoneInfo("Asia/Tashkent")


async def search(client: AsyncClient, headers: TeamHeaders, **params: object) -> dict:
    response = await client.get("/api/v1/properties", params=params, headers=headers.agent)
    assert response.status_code == 200, response.text
    body: dict = response.json()
    return body


def ids(body: dict) -> set[str]:
    return {item["id"] for item in body["items"]}


@pytest.fixture
async def cards(session: AsyncSession, users: Team, district: District) -> dict[str, Property]:
    yunusabad = await factories.create_district(session, "Юнусабадский")
    return {
        "chilanzar": await factories.create_property(
            session,
            users.agent,
            district,
            landmark="рядом с метро Чиланзар, дом 9",
            owner_phone="+998 90 123-45-67",
            request_no="REQ-2045",
        ),
        "yunusabad": await factories.create_property(
            session,
            users.other_agent,
            yunusabad,
            landmark="Юнусабад 4 квартал, напротив школы",
            owner_phone="(97) 555 11 22",
            interest_status=InterestStatus.COLD,
        ),
        "tower": await factories.create_property(
            session,
            users.head,
            district,
            landmark="ТЦ Самарканд Дарвоза, 12 этаж",
            owner_phone="998-93-777-00-00",
        ),
    }


@pytest.mark.parametrize(
    "query",
    [
        "+998 90 123-45-67",
        "998901234567",
        "901234567",
        "90 123 45 67",
        "(90) 123-45-67",
        "1234567",
        "123 45 67",
    ],
)
async def test_phone_is_found_in_any_input_format(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property], query: str
) -> None:
    body = await search(client, headers, q=query)

    assert str(cards["chilanzar"].id) in ids(body)
    assert str(cards["yunusabad"].id) not in ids(body)


async def test_phone_search_ignores_short_digit_runs(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property]
) -> None:
    """Four digits are too short to be treated as a phone fragment."""
    body = await search(client, headers, q="4567")

    assert str(cards["chilanzar"].id) not in ids(body)


@pytest.mark.parametrize(
    "query",
    ["Чилнзар", "чиланзр", "метро Чиланзар", "Чиланзар метро", "метро", "ЧИЛАНЗАР"],
)
async def test_landmark_search_tolerates_typos_case_and_word_order(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property], query: str
) -> None:
    body = await search(client, headers, q=query)

    assert str(cards["chilanzar"].id) in ids(body)
    assert str(cards["yunusabad"].id) not in ids(body)


async def test_typo_in_multiword_landmark(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property]
) -> None:
    body = await search(client, headers, q="Самрканд Дарвза")

    assert ids(body) == {str(cards["tower"].id)}


async def test_search_by_code_request_number_district_and_realtor(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property]
) -> None:
    code_body = await search(client, headers, q=str(cards["tower"].code))
    assert str(cards["tower"].id) in ids(code_body)
    assert code_body["items"][0]["id"] == str(cards["tower"].id), "exact match ranks first"

    assert ids(await search(client, headers, q="req-2045")) == {str(cards["chilanzar"].id)}
    assert ids(await search(client, headers, q="Юнусабадск")) == {str(cards["yunusabad"].id)}
    assert ids(await search(client, headers, q="агент второй")) == {str(cards["yunusabad"].id)}


async def test_like_wildcards_in_query_are_literal(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property]
) -> None:
    body = await search(client, headers, q="%%%")

    assert body["total"] == 0


async def test_soft_deleted_cards_never_appear(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    cards: dict[str, Property],
) -> None:
    deleted_id = str(cards["chilanzar"].id)
    phone_query = "901234567"
    response = await client.delete(f"/api/v1/properties/{deleted_id}", headers=headers.agent)
    assert response.status_code == 204

    for params in [
        {},
        {"q": phone_query},
        {"q": "Чилнзар"},
        {"q": "REQ-2045"},
        {"q": "Чиланзарский"},
        {"q": "Агент Первый"},
        {"availability": "free"},
        {"has_media": "false"},
    ]:
        for role_headers in (headers.agent, headers.admin):
            response = await client.get("/api/v1/properties", params=params, headers=role_headers)
            assert deleted_id not in ids(response.json()), params


async def test_filters_combine(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
    cards: dict[str, Property],
) -> None:
    today = datetime.now(TASHKENT).date()
    occupied = await factories.create_property(
        session,
        users.agent,
        district,
        landmark="метро Чиланзар, занята",
        interest_status=InterestStatus.HOT,
        occupied_until=today + timedelta(days=30),
    )
    free_soon = await factories.create_property(
        session,
        users.agent,
        district,
        landmark="метро Чиланзар, освобождается",
        interest_status=InterestStatus.HOT,
        occupied_until=today + timedelta(days=5),
    )
    ended_yesterday = await factories.create_property(
        session,
        users.agent,
        district,
        landmark="метро Чиланзар, свободна",
        occupied_until=today - timedelta(days=1),
    )

    occupied_ids = ids(await search(client, headers, availability="occupied"))
    assert occupied_ids == {str(occupied.id), str(free_soon.id)}

    free_ids = ids(await search(client, headers, availability="free"))
    assert str(ended_yesterday.id) in free_ids
    assert str(occupied.id) not in free_ids

    free_in_ten_days = ids(await search(client, headers, free_from=str(today + timedelta(days=10))))
    assert str(free_soon.id) in free_in_ten_days
    assert str(occupied.id) not in free_in_ten_days

    combined = await search(
        client,
        headers,
        q="Чиланзар",
        status=["hot"],
        district_id=[str(district.id)],
        created_by=[str(users.agent.id)],
        availability="occupied",
    )
    assert ids(combined) == {str(occupied.id), str(free_soon.id)}

    cold_or_hot = ids(await search(client, headers, status=["cold", "hot"]))
    assert str(cards["yunusabad"].id) in cold_or_hot
    assert str(cards["tower"].id) not in cold_or_hot


async def test_created_date_range_uses_tashkent_days(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    # 23:30 on 1 March in Tashkent is still 1 March there, but 18:30 UTC.
    late_evening = datetime(2026, 3, 1, 23, 30, tzinfo=TASHKENT)
    # 00:30 on 2 March in Tashkent is 19:30 UTC on 1 March.
    after_midnight = datetime(2026, 3, 2, 0, 30, tzinfo=TASHKENT)
    first = await factories.create_property(
        session, users.agent, district, created_at=late_evening.astimezone(UTC)
    )
    second = await factories.create_property(
        session, users.agent, district, created_at=after_midnight.astimezone(UTC)
    )

    march_first = await search(client, headers, created_from="2026-03-01", created_to="2026-03-01")
    march_second = await search(client, headers, created_from="2026-03-02", created_to="2026-03-02")

    assert ids(march_first) == {str(first.id)}
    assert ids(march_second) == {str(second.id)}


async def test_has_media_filter_and_cover(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    cards: dict[str, Property],
) -> None:
    card = cards["tower"]
    for sort_order, kind, thumb in [
        (0, MediaKind.VIDEO, "properties/x/thumbs/video.webp"),
        (1, MediaKind.PHOTO, "properties/x/thumbs/photo.webp"),
    ]:
        session.add(
            PropertyMedia(
                property_id=card.id,
                kind=kind,
                storage_key="properties/x/file.bin",
                thumb_key=thumb,
                mime_type="image/jpeg",
                size_bytes=10,
                sort_order=sort_order,
                uploaded_by=users.head.id,
            )
        )
    await session.flush()

    with_media = await search(client, headers, has_media="true")
    without_media = await search(client, headers, has_media="false")

    assert ids(with_media) == {str(card.id)}
    assert str(card.id) not in ids(without_media)
    item = with_media["items"][0]
    assert item["media_count"] == 2
    assert item["cover_thumb_url"].startswith("/api/v1/media/")
    assert "variant=thumb" in item["cover_thumb_url"]


async def test_default_sort_pagination_and_total(
    client: AsyncClient,
    session: AsyncSession,
    headers: TeamHeaders,
    users: Team,
    district: District,
) -> None:
    base = datetime(2026, 1, 1, tzinfo=UTC)
    created = [
        await factories.create_property(
            session, users.agent, district, created_at=base + timedelta(days=offset)
        )
        for offset in range(5)
    ]
    newest_first = [str(record.id) for record in reversed(created)]

    first_page = await search(client, headers, page=1, page_size=2)
    second_page = await search(client, headers, page=2, page_size=2)
    past_end = await search(client, headers, page=10, page_size=2)
    oldest_first = await search(client, headers, sort="created_at", page_size=5)
    by_code = await search(client, headers, sort="-code", page_size=5)

    assert [item["id"] for item in first_page["items"]] == newest_first[:2]
    assert [item["id"] for item in second_page["items"]] == newest_first[2:4]
    assert first_page["total"] == 5
    assert (past_end["items"], past_end["total"]) == ([], 5)
    assert [item["id"] for item in oldest_first["items"]] == newest_first[::-1]
    assert [item["code"] for item in by_code["items"]] == sorted(
        (record.code for record in created), reverse=True
    )


async def test_list_item_shape(
    client: AsyncClient, headers: TeamHeaders, cards: dict[str, Property]
) -> None:
    body = await search(client, headers, q="Чиланзар")

    item = next(i for i in body["items"] if i["id"] == str(cards["chilanzar"].id))
    assert set(item) == {
        "id",
        "code",
        "district_name",
        "landmark",
        "interest_status",
        "free_until",
        "occupied_until",
        "created_by_name",
        "created_at",
        "cover_thumb_url",
        "media_count",
    }
    assert item["district_name"] == "Чиланзарский"
    assert item["created_by_name"] == "Агент Первый"


@pytest.mark.parametrize(
    "params",
    [{"page_size": 101}, {"page": 0}, {"status": "lukewarm"}, {"sort": "price"}],
)
async def test_invalid_search_parameters_are_rejected(
    client: AsyncClient, headers: TeamHeaders, params: dict[str, object]
) -> None:
    response = await client.get("/api/v1/properties", params=params, headers=headers.agent)

    assert response.status_code == 422
