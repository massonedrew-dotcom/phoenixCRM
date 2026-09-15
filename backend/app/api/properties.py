import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Query, UploadFile, status

from app.core.dependencies import ActorDep, SessionDep, SettingsDep, StorageDep
from app.core.enums import InterestStatus
from app.schemas.audit import AuditEntry
from app.schemas.common import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE, Page
from app.schemas.media import MediaRead
from app.schemas.properties import (
    Availability,
    DeletedPropertyItem,
    PropertyCreate,
    PropertyListItem,
    PropertyPatch,
    PropertyRead,
    SortOption,
)
from app.services import media as media_service
from app.services import properties as properties_service
from app.services.media import IncomingFile

router = APIRouter(prefix="/properties", tags=["properties"])

PageNumber = Annotated[int, Query(ge=1)]
PageSize = Annotated[int, Query(ge=1, le=MAX_PAGE_SIZE)]


@router.get("", response_model=Page[PropertyListItem])
async def search_properties(
    _: ActorDep,
    session: SessionDep,
    settings: SettingsDep,
    q: Annotated[str | None, Query(max_length=200)] = None,
    district_id: Annotated[list[uuid.UUID] | None, Query()] = None,
    status_: Annotated[list[InterestStatus] | None, Query(alias="status")] = None,
    availability: Availability | None = None,
    free_from: date | None = None,
    created_by: Annotated[list[uuid.UUID] | None, Query()] = None,
    created_from: date | None = None,
    created_to: date | None = None,
    has_media: bool | None = None,
    sort: SortOption | None = None,
    page: PageNumber = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[PropertyListItem]:
    return await properties_service.search_properties(
        session,
        settings,
        page=page,
        page_size=page_size,
        q=q,
        district_ids=district_id or (),
        statuses=status_ or (),
        availability=availability,
        free_from=free_from,
        created_by=created_by or (),
        created_from=created_from,
        created_to=created_to,
        has_media=has_media,
        sort=sort,
    )


@router.get("/deleted", response_model=Page[DeletedPropertyItem])
async def list_deleted_properties(
    actor: ActorDep,
    session: SessionDep,
    page: PageNumber = 1,
    page_size: PageSize = DEFAULT_PAGE_SIZE,
) -> Page[DeletedPropertyItem]:
    return await properties_service.list_deleted_properties(
        session, actor, page=page, page_size=page_size
    )


@router.get("/{property_id}", response_model=PropertyRead)
async def get_property(
    property_id: uuid.UUID, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> PropertyRead:
    return await properties_service.open_property(session, settings, actor, property_id)


@router.post("", response_model=PropertyRead, status_code=status.HTTP_201_CREATED)
async def create_property(
    body: PropertyCreate, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> PropertyRead:
    return await properties_service.create_property(session, settings, actor, body)


@router.patch("/{property_id}", response_model=PropertyRead)
async def update_property(
    property_id: uuid.UUID,
    body: PropertyPatch,
    actor: ActorDep,
    session: SessionDep,
    settings: SettingsDep,
) -> PropertyRead:
    return await properties_service.update_property(session, settings, actor, property_id, body)


@router.delete("/{property_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_property(property_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await properties_service.delete_property(session, actor, property_id)


@router.post("/{property_id}/restore", response_model=PropertyRead)
async def restore_property(
    property_id: uuid.UUID, actor: ActorDep, session: SessionDep, settings: SettingsDep
) -> PropertyRead:
    return await properties_service.restore_property(session, settings, actor, property_id)


@router.get("/{property_id}/history", response_model=list[AuditEntry])
async def property_history(
    property_id: uuid.UUID, actor: ActorDep, session: SessionDep
) -> list[AuditEntry]:
    return await properties_service.property_history(session, actor, property_id)


@router.post(
    "/{property_id}/media",
    response_model=list[MediaRead],
    status_code=status.HTTP_201_CREATED,
)
async def upload_media(
    property_id: uuid.UUID,
    files: list[UploadFile],
    actor: ActorDep,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
) -> list[MediaRead]:
    incoming = [
        IncomingFile(filename=upload.filename, file=upload.file, size=upload.size or 0)
        for upload in files
    ]
    return await media_service.upload_media(
        session, settings, storage, actor, property_id, incoming
    )
