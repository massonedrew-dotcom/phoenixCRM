import uuid

from fastapi import APIRouter, status

from app.core.dependencies import ActorDep, AdminDep, HeadOrAdminDep, SessionDep
from app.schemas.users import PasswordReset, RealtorRead, UserCreate, UserPatch, UserRead
from app.services import users as users_service

router = APIRouter(tags=["users"])


@router.get("/users", response_model=list[UserRead])
async def list_users(actor: HeadOrAdminDep, session: SessionDep) -> list[UserRead]:
    return await users_service.list_users(session, actor)


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def create_user(body: UserCreate, actor: AdminDep, session: SessionDep) -> UserRead:
    return await users_service.create_user(session, actor, body)


@router.patch("/users/{user_id}", response_model=UserRead)
async def update_user(
    user_id: uuid.UUID, body: UserPatch, actor: AdminDep, session: SessionDep
) -> UserRead:
    return await users_service.update_user(session, actor, user_id, body)


@router.post("/users/{user_id}/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(
    user_id: uuid.UUID, body: PasswordReset, actor: AdminDep, session: SessionDep
) -> None:
    await users_service.reset_password(session, actor, user_id, body.new_password)


@router.get("/realtors", response_model=list[RealtorRead])
async def list_realtors(_: ActorDep, session: SessionDep) -> list[RealtorRead]:
    return await users_service.list_realtors(session)
