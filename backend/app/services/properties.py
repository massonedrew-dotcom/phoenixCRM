import uuid
from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import Row
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import initial_values, write_audit
from app.core.actor import Actor
from app.core.config import Settings
from app.core.enums import AuditAction, AuditEntity, InterestStatus
from app.core.errors import Conflict, NotFound
from app.models import Property
from app.repositories import audit as audit_repository
from app.repositories import properties as properties_repository
from app.repositories.properties import SearchCriteria
from app.schemas.audit import AuditEntry
from app.schemas.common import Page, UserRef
from app.schemas.properties import (
    DeletedPropertyItem,
    DistrictRef,
    PropertyCreate,
    PropertyListItem,
    PropertyPatch,
    PropertyRead,
)
from app.services import media as media_service
from app.services import views as views_service
from app.services.audit import to_entries
from app.services.base import apply_patch
from app.services.dates import day_after, day_start, local_today
from app.services.districts import ensure_district_active
from app.services.permissions import (
    can_edit_property,
    ensure_can_edit_property,
    ensure_head_or_admin,
)

PRICE_UZS_QUANTUM = Decimal("0.01")
PROPERTY_NOT_FOUND = "Карточка не найдена"


def price_in_uzs(price: Decimal | None, settings: Settings) -> Decimal | None:
    """Prices are stored in у.е.; the сум amount is always derived (DECISIONS.md D1)."""
    if price is None:
        return None
    return (price * settings.uzs_per_ue).quantize(PRICE_UZS_QUANTUM)


def _visible_to(actor: Actor, record: Property) -> bool:
    return not record.is_deleted or actor.is_head_or_admin


async def get_property(
    session: AsyncSession, settings: Settings, actor: Actor, property_id: uuid.UUID
) -> PropertyRead:
    row = await properties_repository.get_detail(session, property_id)
    if row is None or not _visible_to(actor, row.Property):
        raise NotFound(PROPERTY_NOT_FOUND)
    record: Property = row.Property
    return PropertyRead(
        id=record.id,
        code=record.code,
        deal_type=record.deal_type,
        request_no=record.request_no,
        district=DistrictRef(id=record.district_id, name=row.district_name),
        landmark=record.landmark,
        owner_name=record.owner_name,
        owner_phone=record.owner_phone,
        interest_status=record.interest_status,
        free_until=record.free_until,
        occupied_until=record.occupied_until,
        price=record.price,
        price_uzs=price_in_uzs(record.price, settings),
        note=record.note,
        is_deleted=record.is_deleted,
        created_by=UserRef(id=record.created_by, full_name=row.created_by_name),
        created_at=record.created_at,
        updated_by=(
            UserRef(id=record.updated_by, full_name=row.updated_by_name)
            if record.updated_by is not None
            else None
        ),
        updated_at=record.updated_at,
        media=(
            []
            if record.is_deleted
            else await media_service.list_media(session, settings, record.id)
        ),
        can_edit=not record.is_deleted and can_edit_property(actor, record.created_by),
    )


async def open_property(
    session: AsyncSession, settings: Settings, actor: Actor, property_id: uuid.UUID
) -> PropertyRead:
    """A user opens a card: return it and write the view journal."""
    detail = await get_property(session, settings, actor, property_id)
    await views_service.record_property_view(session, actor, property_id)
    return detail


async def create_property(
    session: AsyncSession, settings: Settings, actor: Actor, data: PropertyCreate
) -> PropertyRead:
    await ensure_district_active(session, data.district_id)
    values = data.model_dump()
    record = Property(**values, created_by=actor.id)
    properties_repository.add(session, record)
    await session.flush()
    await write_audit(
        session,
        entity=AuditEntity.PROPERTY,
        entity_id=record.id,
        action=AuditAction.CREATE,
        user_id=actor.id,
        changes=initial_values(values),
    )
    await session.commit()
    return await get_property(session, settings, actor, record.id)


async def _load_for_change(session: AsyncSession, actor: Actor, property_id: uuid.UUID) -> Property:
    record = await properties_repository.get_for_update(session, property_id)
    if record is None or not _visible_to(actor, record):
        raise NotFound(PROPERTY_NOT_FOUND)
    return record


async def update_property(
    session: AsyncSession,
    settings: Settings,
    actor: Actor,
    property_id: uuid.UUID,
    data: PropertyPatch,
) -> PropertyRead:
    record = await _load_for_change(session, actor, property_id)
    if record.is_deleted:
        raise Conflict("Карточка удалена. Сначала восстановите её", "PROPERTY_DELETED")
    ensure_can_edit_property(actor, record.created_by)

    patch = data.model_dump(exclude_unset=True)
    if "district_id" in patch and patch["district_id"] != record.district_id:
        await ensure_district_active(session, patch["district_id"])

    changes = apply_patch(record, patch)
    if changes:
        record.updated_by = actor.id
        record.updated_at = datetime.now(UTC)
        await session.flush()
        await write_audit(
            session,
            entity=AuditEntity.PROPERTY,
            entity_id=record.id,
            action=AuditAction.UPDATE,
            user_id=actor.id,
            changes=changes,
        )
        await session.commit()
    return await get_property(session, settings, actor, record.id)


async def delete_property(session: AsyncSession, actor: Actor, property_id: uuid.UUID) -> None:
    record = await _load_for_change(session, actor, property_id)
    if record.is_deleted:
        raise Conflict("Карточка уже удалена", "PROPERTY_DELETED")
    ensure_can_edit_property(actor, record.created_by)
    record.is_deleted = True
    record.updated_by = actor.id
    record.updated_at = datetime.now(UTC)
    await session.flush()
    await write_audit(
        session,
        entity=AuditEntity.PROPERTY,
        entity_id=record.id,
        action=AuditAction.DELETE,
        user_id=actor.id,
    )
    await session.commit()


async def restore_property(
    session: AsyncSession, settings: Settings, actor: Actor, property_id: uuid.UUID
) -> PropertyRead:
    ensure_head_or_admin(actor)
    record = await _load_for_change(session, actor, property_id)
    if not record.is_deleted:
        raise Conflict("Карточка не удалена", "PROPERTY_NOT_DELETED")
    record.is_deleted = False
    record.updated_by = actor.id
    record.updated_at = datetime.now(UTC)
    await session.flush()
    await write_audit(
        session,
        entity=AuditEntity.PROPERTY,
        entity_id=record.id,
        action=AuditAction.RESTORE,
        user_id=actor.id,
    )
    await session.commit()
    return await get_property(session, settings, actor, record.id)


async def property_history(
    session: AsyncSession, actor: Actor, property_id: uuid.UUID
) -> list[AuditEntry]:
    row = await properties_repository.get_detail(session, property_id)
    if row is None or not _visible_to(actor, row.Property):
        raise NotFound(PROPERTY_NOT_FOUND)
    return to_entries(await audit_repository.property_history(session, property_id))


def _list_item(settings: Settings, row: Row) -> PropertyListItem:
    return PropertyListItem(
        id=row.id,
        code=row.code,
        district_name=row.district_name,
        landmark=row.landmark,
        interest_status=row.interest_status,
        free_until=row.free_until,
        occupied_until=row.occupied_until,
        created_by_name=row.created_by_name,
        created_at=row.created_at,
        updated_by_name=row.updated_by_name,
        updated_at=row.updated_at,
        cover_thumb_url=(
            media_service.media_url(settings, row.cover_media_id, "thumb")
            if row.cover_media_id is not None
            else None
        ),
        media_count=row.media_count,
    )


async def search_properties(
    session: AsyncSession,
    settings: Settings,
    *,
    page: int,
    page_size: int,
    q: str | None = None,
    district_ids: Sequence[uuid.UUID] = (),
    statuses: Sequence[InterestStatus] = (),
    availability: str | None = None,
    free_from: date | None = None,
    created_by: Sequence[uuid.UUID] = (),
    created_from: date | None = None,
    created_to: date | None = None,
    has_media: bool | None = None,
    sort: str | None = None,
) -> Page[PropertyListItem]:
    """Every authenticated user sees every active card, so there is no role filter."""
    zone = settings.zone
    criteria = SearchCriteria(
        today=local_today(zone),
        page=page,
        page_size=page_size,
        q=q,
        district_ids=district_ids,
        statuses=statuses,
        availability=availability,
        free_from=free_from,
        created_by=created_by,
        created_from=day_start(created_from, zone) if created_from else None,
        created_before=day_after(created_to, zone) if created_to else None,
        has_media=has_media,
        sort=sort,
    )
    rows, total = await properties_repository.search(session, criteria)
    return Page(
        items=[_list_item(settings, row) for row in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


async def list_deleted_properties(
    session: AsyncSession, actor: Actor, *, page: int, page_size: int
) -> Page[DeletedPropertyItem]:
    ensure_head_or_admin(actor)
    rows, total = await properties_repository.list_deleted(session, page, page_size)
    return Page(
        items=[
            DeletedPropertyItem(
                id=row.id,
                code=row.code,
                district_name=row.district_name,
                landmark=row.landmark,
                created_by_name=row.created_by_name,
                deleted_by_name=row.deleted_by_name,
                deleted_at=row.deleted_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )
