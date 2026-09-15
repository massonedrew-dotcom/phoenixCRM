import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import ColumnElement, Row, String, cast, exists, func, insert, literal, select
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Property, PropertyView, User


async def record_view(
    session: AsyncSession,
    *,
    property_id: uuid.UUID,
    user_id: uuid.UUID,
    ip: str | None,
    now: datetime,
    repeat_window: timedelta,
) -> None:
    """Insert a view unless the same user opened the same card within the window.

    One statement, so reloads and background refetches do not inflate the journal.
    """
    recent = exists().where(
        PropertyView.property_id == property_id,
        PropertyView.user_id == user_id,
        PropertyView.viewed_at > now - repeat_window,
    )
    source = select(
        literal(property_id).label("property_id"),
        literal(user_id).label("user_id"),
        literal(now).label("viewed_at"),
        cast(literal(ip, String()), INET()).label("ip"),
    ).where(~recent)
    await session.execute(
        insert(PropertyView).from_select(["property_id", "user_id", "viewed_at", "ip"], source)
    )


@dataclass(frozen=True)
class ViewFilter:
    page: int
    page_size: int
    user_id: uuid.UUID | None = None
    property_code: int | None = None
    viewed_from: datetime | None = None
    viewed_before: datetime | None = None


def _period(
    viewed_from: datetime | None, viewed_before: datetime | None
) -> list[ColumnElement[bool]]:
    conditions: list[ColumnElement[bool]] = []
    if viewed_from is not None:
        conditions.append(PropertyView.viewed_at >= viewed_from)
    if viewed_before is not None:
        conditions.append(PropertyView.viewed_at < viewed_before)
    return conditions


async def summary_by_user(
    session: AsyncSession, viewed_from: datetime | None, viewed_before: datetime | None
) -> list[Row]:
    """Views and distinct cards per user for the period, most active first."""
    statement = (
        select(
            User.id,
            User.full_name,
            User.username,
            User.role,
            User.is_active,
            func.count(PropertyView.id).label("views"),
            func.count(func.distinct(PropertyView.property_id)).label("cards"),
            func.max(PropertyView.viewed_at).label("last_viewed_at"),
        )
        .join(PropertyView, PropertyView.user_id == User.id)
        .where(*_period(viewed_from, viewed_before))
        .group_by(User.id)
        .order_by(func.count(func.distinct(PropertyView.property_id)).desc(), User.full_name)
    )
    return list((await session.execute(statement)).all())


async def list_views(session: AsyncSession, criteria: ViewFilter) -> tuple[list[Row], int]:
    conditions = _period(criteria.viewed_from, criteria.viewed_before)
    if criteria.user_id is not None:
        conditions.append(PropertyView.user_id == criteria.user_id)
    if criteria.property_code is not None:
        conditions.append(Property.code == criteria.property_code)

    total = (
        select(func.count())
        .select_from(PropertyView)
        .join(Property, Property.id == PropertyView.property_id)
        .where(*conditions)
        .scalar_subquery()
    )
    statement = (
        select(
            PropertyView.id,
            PropertyView.viewed_at,
            PropertyView.ip,
            User.id.label("user_id"),
            User.full_name.label("user_full_name"),
            Property.id.label("property_id"),
            Property.code.label("property_code"),
            Property.landmark.label("property_landmark"),
            total.label("total"),
        )
        .join(User, User.id == PropertyView.user_id)
        .join(Property, Property.id == PropertyView.property_id)
        .where(*conditions)
        .order_by(PropertyView.viewed_at.desc(), PropertyView.id.desc())
        .limit(criteria.page_size)
        .offset((criteria.page - 1) * criteria.page_size)
    )
    rows = list((await session.execute(statement)).all())
    return rows, rows[0].total if rows else 0
