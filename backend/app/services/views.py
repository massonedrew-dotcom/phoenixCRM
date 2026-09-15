import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import Actor
from app.core.config import Settings
from app.core.context import get_request_context
from app.repositories import views as views_repository
from app.repositories.views import ViewFilter
from app.schemas.common import Page, UserRef
from app.schemas.views import PropertyRef, UserViewSummary, ViewEntry
from app.services.dates import day_after, day_start
from app.services.permissions import ensure_head_or_admin

# Reopening the same card within this window is one view (reloads, refetches, tab switches).
REPEAT_VIEW_WINDOW = timedelta(minutes=10)


async def record_property_view(session: AsyncSession, actor: Actor, property_id: uuid.UUID) -> None:
    await views_repository.record_view(
        session,
        property_id=property_id,
        user_id=actor.id,
        ip=get_request_context().ip,
        now=datetime.now(UTC),
        repeat_window=REPEAT_VIEW_WINDOW,
    )
    await session.commit()


async def view_summary(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    *,
    date_from: date | None,
    date_to: date | None,
) -> list[UserViewSummary]:
    ensure_head_or_admin(actor)
    rows = await views_repository.summary_by_user(
        session,
        day_start(date_from, settings.zone) if date_from else None,
        day_after(date_to, settings.zone) if date_to else None,
    )
    return [
        UserViewSummary(
            user_id=row.id,
            full_name=row.full_name,
            username=row.username,
            role=row.role,
            is_active=row.is_active,
            views=row.views,
            cards=row.cards,
            last_viewed_at=row.last_viewed_at,
        )
        for row in rows
    ]


async def list_views(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    *,
    page: int,
    page_size: int,
    user_id: uuid.UUID | None = None,
    property_code: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[ViewEntry]:
    ensure_head_or_admin(actor)
    rows, total = await views_repository.list_views(
        session,
        ViewFilter(
            page=page,
            page_size=page_size,
            user_id=user_id,
            property_code=property_code,
            viewed_from=day_start(date_from, settings.zone) if date_from else None,
            viewed_before=day_after(date_to, settings.zone) if date_to else None,
        ),
    )
    return Page(
        items=[
            ViewEntry(
                id=row.id,
                viewed_at=row.viewed_at,
                user=UserRef(id=row.user_id, full_name=row.user_full_name),
                property=PropertyRef(
                    id=row.property_id, code=row.property_code, landmark=row.property_landmark
                ),
                ip=str(row.ip) if row.ip is not None else None,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
