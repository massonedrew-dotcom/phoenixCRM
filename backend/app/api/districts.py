import uuid

from fastapi import APIRouter, status

from app.core.dependencies import ActorDep, AdminDep, SessionDep
from app.schemas.districts import DistrictCreate, DistrictPatch, DistrictRead
from app.services import districts as districts_service

router = APIRouter(prefix="/districts", tags=["districts"])


@router.get("", response_model=list[DistrictRead])
async def list_districts(_: ActorDep, session: SessionDep) -> list[DistrictRead]:
    return await districts_service.list_districts(session)


@router.post("", response_model=DistrictRead, status_code=status.HTTP_201_CREATED)
async def create_district(
    body: DistrictCreate, actor: AdminDep, session: SessionDep
) -> DistrictRead:
    return await districts_service.create_district(session, actor, body)


@router.patch("/{district_id}", response_model=DistrictRead)
async def update_district(
    district_id: uuid.UUID, body: DistrictPatch, actor: AdminDep, session: SessionDep
) -> DistrictRead:
    return await districts_service.update_district(session, actor, district_id, body)
