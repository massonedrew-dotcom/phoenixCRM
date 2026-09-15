import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query

from app.core.dependencies import HeadOrAdminDep, SessionDep, SettingsDep
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.views import UserViewSummary, ViewEntry
from app.services import views as views_service

router = APIRouter(prefix="/views", tags=["views"])


@router.get("/summary", response_model=list[UserViewSummary])
async def view_summary(
    actor: HeadOrAdminDep,
    session: SessionDep,
    settings: SettingsDep,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[UserViewSummary]:
    return await views_service.view_summary(
        session, settings, actor, date_from=date_from, date_to=date_to
    )


@router.get("", response_model=Page[ViewEntry])
async def list_views(
    actor: HeadOrAdminDep,
    session: SessionDep,
    settings: SettingsDep,
    user_id: uuid.UUID | None = None,
    property_code: Annotated[int | None, Query(ge=1)] = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)] = DEFAULT_PAGE_SIZE,
) -> Page[ViewEntry]:
    return await views_service.list_views(
        session,
        settings,
        actor,
        page=page,
        page_size=page_size,
        user_id=user_id,
        property_code=property_code,
        date_from=date_from,
        date_to=date_to,
    )
