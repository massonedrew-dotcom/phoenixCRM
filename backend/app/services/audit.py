import uuid
from collections.abc import Sequence
from datetime import date

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.config import Settings
from app.core.enums import AuditAction
from app.repositories import audit as audit_repository
from app.repositories.audit import AuditFilter
from app.schemas.audit import AuditEntry
from app.schemas.common import Page, UserRef
from app.services.dates import day_after, day_start
from app.services.permissions import ensure_head_or_admin


def to_entries(rows: Sequence[Row]) -> list[AuditEntry]:
    entries = []
    for row in rows:
        log = row.AuditLog
        entries.append(
            AuditEntry(
                id=log.id,
                entity=log.entity,
                entity_id=log.entity_id,
                action=log.action.value,
                field=log.field,
                old_value=log.old_value,
                new_value=log.new_value,
                user=(
                    UserRef(id=log.user_id, full_name=row.user_full_name)
                    if log.user_id is not None
                    else None
                ),
                ip=str(log.ip) if log.ip is not None else None,
                created_at=log.created_at,
                property_id=getattr(row, "property_id", None),
                property_code=getattr(row, "property_code", None),
                subject_name=getattr(row, "subject_name", None),
            )
        )
    return entries


async def audit_feed(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    entity: str | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    property_code: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[AuditEntry]:
    ensure_head_or_admin(actor)
    criteria = AuditFilter(
        page=page,
        page_size=page_size,
        entity=entity,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        property_code=property_code,
        created_from=day_start(date_from, settings.zone) if date_from else None,
        created_before=day_after(date_to, settings.zone) if date_to else None,
    )
    rows, total = await audit_repository.feed(session, criteria)
    return Page(items=to_entries(rows), total=total, page=page, page_size=page_size)
