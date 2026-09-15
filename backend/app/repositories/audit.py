import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Row, Select, and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.enums import AuditAction, AuditEntity
from app.models import AuditLog, District, Property, PropertyMedia, User


def _entries_statement(*conditions: ColumnElement[bool]) -> Select[tuple[AuditLog, str | None]]:
    return (
        select(AuditLog, User.full_name.label("user_full_name"))
        .outerjoin(User, User.id == AuditLog.user_id)
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    )


async def property_history(session: AsyncSession, property_id: uuid.UUID) -> list[Row]:
    """Audit rows of a card and of its media, newest first."""
    media_ids = select(PropertyMedia.id).where(PropertyMedia.property_id == property_id)
    statement = _entries_statement(
        or_(
            (AuditLog.entity == AuditEntity.PROPERTY.value) & (AuditLog.entity_id == property_id),
            (AuditLog.entity == AuditEntity.MEDIA.value) & AuditLog.entity_id.in_(media_ids),
        )
    )
    return list((await session.execute(statement)).all())


@dataclass(frozen=True)
class AuditFilter:
    page: int
    page_size: int
    entity: str | None = None
    entity_id: uuid.UUID | None = None
    user_id: uuid.UUID | None = None
    action: AuditAction | None = None
    property_code: int | None = None
    created_from: datetime | None = None
    created_before: datetime | None = None


async def feed(session: AsyncSession, criteria: AuditFilter) -> tuple[list[Row], int]:
    """The global journal, with the card number and a readable subject for every row."""
    card = aliased(Property)
    media = aliased(PropertyMedia)
    media_card = aliased(Property)
    subject_user = aliased(User)
    subject_district = aliased(District)
    property_id = func.coalesce(card.id, media_card.id)
    property_code = func.coalesce(card.code, media_card.code)

    conditions: list[ColumnElement[bool]] = []
    if criteria.entity is not None:
        conditions.append(AuditLog.entity == criteria.entity)
    if criteria.entity_id is not None:
        conditions.append(AuditLog.entity_id == criteria.entity_id)
    if criteria.user_id is not None:
        conditions.append(AuditLog.user_id == criteria.user_id)
    if criteria.action is not None:
        conditions.append(AuditLog.action == criteria.action)
    if criteria.property_code is not None:
        conditions.append(property_code == criteria.property_code)
    if criteria.created_from is not None:
        conditions.append(AuditLog.created_at >= criteria.created_from)
    if criteria.created_before is not None:
        conditions.append(AuditLog.created_at < criteria.created_before)

    def with_subjects(statement: Select) -> Select:  # type: ignore[type-arg]
        return (
            statement.outerjoin(
                card,
                and_(AuditLog.entity == AuditEntity.PROPERTY.value, card.id == AuditLog.entity_id),
            )
            .outerjoin(
                media,
                and_(AuditLog.entity == AuditEntity.MEDIA.value, media.id == AuditLog.entity_id),
            )
            .outerjoin(media_card, media_card.id == media.property_id)
            .outerjoin(
                subject_user,
                and_(
                    AuditLog.entity == AuditEntity.USER.value, subject_user.id == AuditLog.entity_id
                ),
            )
            .outerjoin(
                subject_district,
                and_(
                    AuditLog.entity == AuditEntity.DISTRICT.value,
                    subject_district.id == AuditLog.entity_id,
                ),
            )
        )

    total = with_subjects(select(func.count()).select_from(AuditLog)).where(*conditions)
    statement = (
        with_subjects(
            select(
                AuditLog,
                User.full_name.label("user_full_name"),
                property_id.label("property_id"),
                property_code.label("property_code"),
                func.coalesce(subject_user.full_name, subject_district.name).label("subject_name"),
                total.scalar_subquery().label("total"),
            )
            .select_from(AuditLog)
            .outerjoin(User, User.id == AuditLog.user_id)
        )
        .where(*conditions)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(criteria.page_size)
        .offset((criteria.page - 1) * criteria.page_size)
    )
    rows = list((await session.execute(statement)).all())
    return rows, rows[0].total if rows else 0
