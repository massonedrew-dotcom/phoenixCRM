from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.actor import Actor
from app.core.config import Settings
from app.core.context import get_request_context
from app.core.errors import NotAuthenticated
from app.services import auth as auth_service
from app.services.permissions import ensure_admin, ensure_head_or_admin
from app.storage import Storage


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """Yield one database session per request; it is closed when the request ends."""
    sessionmaker: async_sessionmaker[AsyncSession] = request.app.state.sessionmaker
    async with sessionmaker() as session:
        yield session


def get_app_settings(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_storage(request: Request) -> Storage:
    storage: Storage = request.app.state.storage
    return storage


SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
StorageDep = Annotated[Storage, Depends(get_storage)]

_bearer = HTTPBearer(auto_error=False, description="Access token")
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]


async def get_optional_actor(
    session: SessionDep, settings: SettingsDep, credentials: BearerDep
) -> Actor | None:
    if credentials is None:
        return None
    actor = await auth_service.authenticate(session, settings, credentials.credentials)
    get_request_context().user_id = actor.id
    return actor


async def get_current_actor(actor: Annotated[Actor | None, Depends(get_optional_actor)]) -> Actor:
    if actor is None:
        raise NotAuthenticated()
    return actor


ActorDep = Annotated[Actor, Depends(get_current_actor)]
OptionalActorDep = Annotated[Actor | None, Depends(get_optional_actor)]


async def require_admin(actor: ActorDep) -> Actor:
    """Router-level guard; services repeat the same check from services.permissions."""
    ensure_admin(actor)
    return actor


async def require_head_or_admin(actor: ActorDep) -> Actor:
    ensure_head_or_admin(actor)
    return actor


AdminDep = Annotated[Actor, Depends(require_admin)]
HeadOrAdminDep = Annotated[Actor, Depends(require_head_or_admin)]
