import re
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime

from sqlalchemy import (
    ColumnElement,
    Float,
    Row,
    Select,
    and_,
    exists,
    false,
    func,
    literal,
    or_,
    select,
    true,
    union_all,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql.base import ReadOnlyColumnCollection

from app.core.enums import InterestStatus, MediaKind
from app.models import District, Property, PropertyMedia, User

MIN_PHONE_SEARCH_DIGITS = 5
MIN_SUBSTRING_LENGTH = 3
MAX_CODE = 2**63 - 1
EXACT_MATCH_RANK = 2.0
_WORD = re.compile(r"\w[\w-]*")


@dataclass(frozen=True)
class SearchCriteria:
    today: date
    page: int
    page_size: int
    q: str | None = None
    district_ids: Sequence[uuid.UUID] = field(default_factory=tuple)
    statuses: Sequence[InterestStatus] = field(default_factory=tuple)
    availability: str | None = None
    free_from: date | None = None
    created_by: Sequence[uuid.UUID] = field(default_factory=tuple)
    created_from: datetime | None = None
    created_before: datetime | None = None
    has_media: bool | None = None
    sort: str | None = None


LIKE_ESCAPE = "!"


def escape_like(value: str) -> str:
    """Make `%`, `_`, and the escape character itself match literally."""
    return re.sub(r"([!%_])", r"!\1", value)


def _active_media() -> ColumnElement[bool]:
    return and_(PropertyMedia.property_id == Property.id, PropertyMedia.is_deleted == false())


@dataclass(frozen=True)
class _QueryTerms:
    """Normalized forms of the search box input (DECISIONS.md D12)."""

    text: str
    pattern: str
    phone_digits: str | None
    code: int | None
    words: tuple[str, ...]

    @classmethod
    def parse(cls, q: str) -> "_QueryTerms":
        digits = re.sub(r"\D", "", q)
        words = tuple(
            word for word in _WORD.findall(q.lower()) if len(word) >= MIN_SUBSTRING_LENGTH
        )
        return cls(
            text=q,
            pattern=f"%{escape_like(q)}%",
            phone_digits=digits if len(digits) >= MIN_PHONE_SEARCH_DIGITS else None,
            code=int(q) if q.isdigit() and int(q) <= MAX_CODE else None,
            words=words,
        )


def _exact_matches(
    terms: _QueryTerms,
    phone_digits: ColumnElement[str],
    code: ColumnElement[int],
    request_no: ColumnElement[str | None],
) -> list[ColumnElement[bool]]:
    """Phone, code, and request-number matches; they rank above fuzzy landmark matches."""
    matches: list[ColumnElement[bool]] = []
    if terms.phone_digits is not None:
        matches.append(phone_digits.like(f"%{terms.phone_digits}%"))
    if terms.code is not None:
        matches.append(code == terms.code)
    if len(terms.text) >= MIN_SUBSTRING_LENGTH:
        matches.append(request_no.ilike(terms.pattern, escape=LIKE_ESCAPE))
    else:
        matches.append(request_no == terms.text)
    return matches


def _changed_at() -> ColumnElement[datetime]:
    return func.coalesce(Property.updated_at, Property.created_at)


def _matching_rows(terms: _QueryTerms, conditions: Sequence[ColumnElement[bool]]) -> Select:
    """Cards matching the search box with their relevance, from index-backed branches.

    Every branch carries all filters, so nothing is joined back to the whole `properties`
    table, and computes its own relevance, so trigram similarity is evaluated once per row.
    """
    base = (
        Property.id,
        Property.code,
        Property.created_at,
        _changed_at().label("changed_at"),
    )
    exact_rank = literal(EXACT_MATCH_RANK, Float).label("relevance")
    similarity = func.word_similarity(terms.text, Property.landmark).label("relevance")

    exact = _exact_matches(terms, Property.owner_phone_digits, Property.code, Property.request_no)
    branches = [select(*base, exact_rank).where(match, *conditions) for match in exact]
    if terms.words:
        # Every word must appear in the landmark, each tolerating typos; word order is free.
        words_match = [literal(word).op("<%")(Property.landmark) for word in terms.words]
        branches.append(select(*base, similarity).where(*words_match, *conditions))
    if len(terms.text) >= MIN_SUBSTRING_LENGTH:
        # One or two characters carry no signal and would match most of the base.
        branches.append(
            select(*base, similarity)
            .join(District, District.id == Property.district_id)
            .where(District.name.ilike(terms.pattern, escape=LIKE_ESCAPE), *conditions)
        )
        branches.append(
            select(*base, similarity)
            .join(User, User.id == Property.created_by)
            .where(User.full_name.ilike(terms.pattern, escape=LIKE_ESCAPE), *conditions)
        )

    matched = union_all(*branches).subquery("matched")
    return select(
        matched.c.id,
        matched.c.code,
        matched.c.created_at,
        matched.c.changed_at,
        func.max(matched.c.relevance).label("relevance"),
    ).group_by(matched.c.id, matched.c.code, matched.c.created_at, matched.c.changed_at)


def _filters(criteria: SearchCriteria) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = [Property.is_deleted == false()]
    if criteria.district_ids:
        conditions.append(Property.district_id.in_(criteria.district_ids))
    if criteria.statuses:
        conditions.append(Property.interest_status.in_(criteria.statuses))
    if criteria.availability == "occupied":
        conditions.append(Property.occupied_until >= criteria.today)
    elif criteria.availability == "free":
        conditions.append(
            or_(Property.occupied_until.is_(None), Property.occupied_until < criteria.today)
        )
    if criteria.free_from is not None:
        conditions.append(
            or_(Property.occupied_until.is_(None), Property.occupied_until < criteria.free_from)
        )
    if criteria.created_by:
        conditions.append(Property.created_by.in_(criteria.created_by))
    if criteria.created_from is not None:
        conditions.append(Property.created_at >= criteria.created_from)
    if criteria.created_before is not None:
        conditions.append(Property.created_at < criteria.created_before)
    if criteria.has_media is not None:
        media_exists = exists().where(_active_media())
        conditions.append(media_exists if criteria.has_media else ~media_exists)
    return conditions


def build_search_statement(criteria: SearchCriteria) -> Select[tuple[object, ...]]:
    """Filtered, sorted, paginated list with its total, as one SQL statement."""
    conditions = _filters(criteria)
    q = (criteria.q or "").strip()
    if q:
        source = _matching_rows(_QueryTerms.parse(q), conditions)
    else:
        source = select(
            Property.id,
            Property.code,
            Property.created_at,
            _changed_at().label("changed_at"),
            literal(0.0, Float).label("relevance"),
        ).where(*conditions)

    # Without `q` the CTE is inlined so the page can stop early on an index scan; with `q`
    # it is materialized so the union of search branches runs once for both total and page.
    filtered = source.cte("filtered").prefix_with("MATERIALIZED" if q else "NOT MATERIALIZED")
    sort = criteria.sort or ("relevance" if q else "-created_at")

    def ordering(c: ReadOnlyColumnCollection[str, ColumnElement[object]]) -> list[ColumnElement]:
        """Sort keys applied to both the page subquery and the final statement."""
        if sort == "relevance":
            return [c.relevance.desc(), c.created_at.desc(), c.id.desc()]
        column = {"created_at": c.created_at, "updated_at": c.changed_at, "code": c.code}[
            sort.lstrip("-")
        ]
        return [column.desc() if sort.startswith("-") else column.asc(), c.id.desc()]

    page = (
        select(filtered)
        .order_by(*ordering(filtered.c))
        .limit(criteria.page_size)
        .offset((criteria.page - 1) * criteria.page_size)
        .subquery("page")
    )

    cover_media_id = (
        select(PropertyMedia.id)
        .where(_active_media(), PropertyMedia.thumb_key.is_not(None))
        .order_by(
            (PropertyMedia.kind != MediaKind.PHOTO).asc(),
            PropertyMedia.sort_order,
            PropertyMedia.uploaded_at,
        )
        .limit(1)
        .scalar_subquery()
    )
    media_count = select(func.count(PropertyMedia.id)).where(_active_media()).scalar_subquery()
    creator = aliased(User)
    editor = aliased(User)
    details = (
        select(
            page.c.id,
            page.c.code,
            page.c.created_at,
            page.c.changed_at,
            page.c.relevance,
            District.name.label("district_name"),
            Property.landmark,
            Property.interest_status,
            Property.free_until,
            Property.occupied_until,
            creator.full_name.label("created_by_name"),
            Property.updated_at,
            editor.full_name.label("updated_by_name"),
            cover_media_id.label("cover_media_id"),
            media_count.label("media_count"),
        )
        .join_from(page, Property, Property.id == page.c.id)
        .join(District, District.id == Property.district_id)
        .join(creator, creator.id == Property.created_by)
        .outerjoin(editor, editor.id == Property.updated_by)
        .subquery("details")
    )
    totals = select(func.count().label("total")).select_from(filtered).subquery("totals")
    # LEFT JOIN keeps the total even when the requested page is past the end.
    return (
        select(totals.c.total, details)
        .select_from(totals)
        .outerjoin(details, true())
        .order_by(*ordering(details.c))
    )


async def search(session: AsyncSession, criteria: SearchCriteria) -> tuple[list[Row], int]:
    rows = (await session.execute(build_search_statement(criteria))).all()
    total = rows[0].total if rows else 0
    return [row for row in rows if row.id is not None], total


async def get_detail(session: AsyncSession, property_id: uuid.UUID) -> Row | None:
    """The card with district, creator, and last editor names."""
    creator = aliased(User)
    editor = aliased(User)
    statement = (
        select(
            Property,
            District.name.label("district_name"),
            creator.full_name.label("created_by_name"),
            editor.full_name.label("updated_by_name"),
        )
        .join(District, District.id == Property.district_id)
        .join(creator, creator.id == Property.created_by)
        .outerjoin(editor, editor.id == Property.updated_by)
        .where(Property.id == property_id)
    )
    return (await session.execute(statement)).one_or_none()


async def get_for_update(session: AsyncSession, property_id: uuid.UUID) -> Property | None:
    return await session.scalar(
        select(Property).where(Property.id == property_id).with_for_update()
    )


def add(session: AsyncSession, record: Property) -> None:
    session.add(record)


async def list_deleted(session: AsyncSession, page: int, page_size: int) -> tuple[list[Row], int]:
    creator = aliased(User)
    editor = aliased(User)
    conditions = [Property.is_deleted == true()]
    total_sq = select(func.count()).where(*conditions).scalar_subquery()
    statement = (
        select(
            Property.id,
            Property.code,
            District.name.label("district_name"),
            Property.landmark,
            creator.full_name.label("created_by_name"),
            editor.full_name.label("deleted_by_name"),
            Property.updated_at.label("deleted_at"),
            total_sq.label("total"),
        )
        .join(District, District.id == Property.district_id)
        .join(creator, creator.id == Property.created_by)
        .outerjoin(editor, editor.id == Property.updated_by)
        .where(*conditions)
        .order_by(Property.updated_at.desc().nulls_last(), Property.id.desc())
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    rows = (await session.execute(statement)).all()
    return list(rows), rows[0].total if rows else 0
