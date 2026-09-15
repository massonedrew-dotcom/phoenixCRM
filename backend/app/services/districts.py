import uuid
from collections.abc import Iterable

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import initial_values, write_audit
from app.core.actor import Actor
from app.core.enums import AuditAction, AuditEntity
from app.core.errors import AppError, Conflict, NotFound
from app.models import District
from app.repositories import districts as districts_repository
from app.schemas.districts import DistrictCreate, DistrictPatch, DistrictRead
from app.services.base import apply_patch
from app.services.permissions import ensure_admin

DISTRICT_EXISTS = Conflict("Район с таким названием уже существует", "DISTRICT_EXISTS")


async def list_districts(session: AsyncSession) -> list[DistrictRead]:
    return [DistrictRead.model_validate(d) for d in await districts_repository.list_all(session)]


async def _flush_unique(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise DISTRICT_EXISTS from exc


async def create_district(
    session: AsyncSession, actor: Actor, data: DistrictCreate
) -> DistrictRead:
    ensure_admin(actor)
    if await districts_repository.get_by_name(session, data.name) is not None:
        raise DISTRICT_EXISTS
    district = District(name=data.name, is_active=True)
    districts_repository.add(session, district)
    await _flush_unique(session)
    await write_audit(
        session,
        entity=AuditEntity.DISTRICT,
        entity_id=district.id,
        action=AuditAction.CREATE,
        user_id=actor.id,
        changes=initial_values({"name": district.name, "is_active": district.is_active}),
    )
    await session.commit()
    return DistrictRead.model_validate(district)


async def update_district(
    session: AsyncSession, actor: Actor, district_id: uuid.UUID, data: DistrictPatch
) -> DistrictRead:
    ensure_admin(actor)
    district = await districts_repository.get_by_id(session, district_id)
    if district is None:
        raise NotFound("Район не найден")
    patch = {k: v for k, v in data.model_dump(exclude_unset=True).items() if v is not None}
    if "name" in patch and patch["name"] != district.name:
        existing = await districts_repository.get_by_name(session, patch["name"])
        if existing is not None:
            raise DISTRICT_EXISTS
    changes = apply_patch(district, patch)
    if changes:
        await _flush_unique(session)
        await write_audit(
            session,
            entity=AuditEntity.DISTRICT,
            entity_id=district.id,
            action=AuditAction.UPDATE,
            user_id=actor.id,
            changes=changes,
        )
        await session.commit()
    return DistrictRead.model_validate(district)


async def ensure_district_active(session: AsyncSession, district_id: uuid.UUID) -> District:
    district = await districts_repository.get_by_id(session, district_id)
    if district is None:
        raise AppError("Район не найден", "DISTRICT_NOT_FOUND")
    if not district.is_active:
        raise AppError("Район отключён, выберите другой", "DISTRICT_INACTIVE")
    return district


async def seed_districts(session: AsyncSession, names: Iterable[str]) -> list[str]:
    """Insert missing districts. Returns the names that were added. CLI only."""
    added: list[str] = []
    for raw_name in names:
        name = raw_name.strip()
        if not name or await districts_repository.get_by_name(session, name) is not None:
            continue
        district = District(name=name, is_active=True)
        districts_repository.add(session, district)
        await session.flush()
        await write_audit(
            session,
            entity=AuditEntity.DISTRICT,
            entity_id=district.id,
            action=AuditAction.CREATE,
            user_id=None,
            changes=initial_values({"name": name, "is_active": True}),
        )
        added.append(name)
    await session.commit()
    return added
