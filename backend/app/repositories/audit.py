import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import ColumnElement, Row, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import AuditAction, AuditEntity
from app.models import AuditLog, PropertyMedia, User


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
    created_from: datetime | None = None
    created_before: datetime | None = None


async def feed(session: AsyncSession, criteria: AuditFilter) -> tuple[list[Row], int]:
    conditions: list[ColumnElement[bool]] = []
    if criteria.entity is not None:
        conditions.append(AuditLog.entity == criteria.entity)
    if criteria.entity_id is not None:
        conditions.append(AuditLog.entity_id == criteria.entity_id)
    if criteria.user_id is not None:
        conditions.append(AuditLog.user_id == criteria.user_id)
    if criteria.action is not None:
        conditions.append(AuditLog.action == criteria.action)
    if criteria.created_from is not None:
        conditions.append(AuditLog.created_at >= criteria.created_from)
    if criteria.created_before is not None:
        conditions.append(AuditLog.created_at < criteria.created_before)

    total = select(func.count()).select_from(AuditLog).where(*conditions).scalar_subquery()
    statement = (
        _entries_statement(*conditions)
        .add_columns(total.label("total"))
        .limit(criteria.page_size)
        .offset((criteria.page - 1) * criteria.page_size)
    )
    rows = list((await session.execute(statement)).all())
    return rows, rows[0].total if rows else 0
