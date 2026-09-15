import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit.diff import FieldChange
from app.core.context import get_request_context
from app.core.enums import AuditAction, AuditEntity
from app.models import AuditLog


async def write_audit(
    session: AsyncSession,
    *,
    entity: AuditEntity,
    entity_id: uuid.UUID | None,
    action: AuditAction,
    user_id: uuid.UUID | None,
    changes: Sequence[FieldChange] | None = None,
) -> None:
    """Add audit rows to the caller's transaction and flush them.

    `changes=None` writes a single row without a field (delete, restore, login).
    A list writes one row per change; an empty list writes nothing.
    The caller commits, so the audit rows and the mutation succeed or fail together.
    """
    ip = get_request_context().ip
    if changes is None:
        rows = [
            AuditLog(
                entity=entity.value, entity_id=entity_id, action=action, user_id=user_id, ip=ip
            )
        ]
    else:
        rows = [
            AuditLog(
                entity=entity.value,
                entity_id=entity_id,
                action=action,
                field=change.field,
                old_value=change.old_value,
                new_value=change.new_value,
                user_id=user_id,
                ip=ip,
            )
            for change in changes
        ]
    if not rows:
        return
    session.add_all(rows)
    await session.flush()
