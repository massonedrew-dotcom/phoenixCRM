from fastapi import APIRouter, Request, status

from app.core.context import get_request_context
from app.core.dependencies import ActorDep, SessionDep, SettingsDep
from app.core.errors import RateLimited
from app.core.rate_limit import SlidingWindowRateLimiter
from app.schemas.auth import (
    ChangePasswordRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
)
from app.schemas.users import UserRead
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _enforce_login_rate_limit(request: Request) -> None:
    limiter: SlidingWindowRateLimiter = request.app.state.login_rate_limiter
    if not limiter.hit(get_request_context().ip or "unknown"):
        raise RateLimited()


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest, request: Request, session: SessionDep, settings: SettingsDep
) -> LoginResponse:
    _enforce_login_rate_limit(request)
    return await auth_service.login(session, settings, body.username, body.password)


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(
    body: RefreshRequest, session: SessionDep, settings: SettingsDep
) -> RefreshResponse:
    return await auth_service.refresh(session, settings, body.refresh_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(actor: ActorDep, session: SessionDep) -> None:
    await auth_service.logout(session, actor)


@router.get("/me", response_model=UserRead)
async def me(actor: ActorDep, session: SessionDep) -> UserRead:
    return await auth_service.get_me(session, actor)


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest, actor: ActorDep, session: SessionDep
) -> None:
    await auth_service.change_password(session, actor, body.old_password, body.new_password)
