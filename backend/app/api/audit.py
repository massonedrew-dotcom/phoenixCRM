import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import HeadOrAdminDep, SessionDep, SettingsDep
from app.core.enums import AuditAction, AuditEntity
from app.schemas.audit import AuditEntry
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.services import audit as audit_service

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("", response_model=Page[AuditEntry])
async def audit_feed(
    actor: HeadOrAdminDep,
    session: SessionDep,
    settings: SettingsDep,
    entity: AuditEntity | None = None,
    entity_id: uuid.UUID | None = None,
    user_id: uuid.UUID | None = None,
    action: AuditAction | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[AuditEntry]:
    return await audit_service.audit_feed(
        session,
        settings,
        actor,
        page=page,
        page_size=page_size,
        entity=entity.value if entity else None,
        entity_id=entity_id,
        user_id=user_id,
        action=action,
        date_from=date_from,
        date_to=date_to,
    )
