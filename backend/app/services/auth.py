import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import FieldChange, write_audit
from app.core.actor import Actor
from app.core.config import Settings
from app.core.context import get_request_context
from app.core.enums import AuditAction, AuditEntity
from app.core.errors import AppError, InvalidCredentials, NotAuthenticated
from app.core.security import (
    TokenType,
    create_token,
    decode_token,
    hash_password,
    spend_verification_time,
    verify_password,
)
from app.models import User
from app.repositories import users as users_repository
from app.schemas.auth import LoginResponse, RefreshResponse
from app.schemas.users import UserRead

MAX_LOGGED_USERNAME_LENGTH = 64


def _actor(user: User, session_id: uuid.UUID) -> Actor:
    return Actor(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        session_id=session_id,
    )


async def _record_failed_login(session: AsyncSession, username: str, user: User | None) -> None:
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id if user else None,
        action=AuditAction.LOGIN_FAILED,
        user_id=None,
        changes=[FieldChange("username", None, username[:MAX_LOGGED_USERNAME_LENGTH])],
    )
    await session.commit()


async def login(
    session: AsyncSession, settings: Settings, username: str, password: str
) -> LoginResponse:
    normalized = username.strip().lower()
    user = await users_repository.get_by_username(session, normalized)
    if user is None:
        await spend_verification_time(password)
        await _record_failed_login(session, normalized, None)
        raise InvalidCredentials()
    if not await verify_password(user.password_hash, password) or not user.is_active:
        await _record_failed_login(session, normalized, user)
        raise InvalidCredentials()

    now = datetime.now(UTC)
    auth_session = await users_repository.create_session(
        session,
        user_id=user.id,
        expires_at=now + timedelta(days=settings.refresh_token_days),
        ip=get_request_context().ip,
    )
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id,
        action=AuditAction.LOGIN,
        user_id=user.id,
    )
    await session.commit()

    token_args = {"user_id": user.id, "session_id": auth_session.id, "now": now}
    return LoginResponse(
        access_token=create_token(settings, token_type="access", **token_args),
        refresh_token=create_token(settings, token_type="refresh", **token_args),
        user=UserRead.model_validate(user),
    )


async def authenticate(
    session: AsyncSession, settings: Settings, token: str, token_type: TokenType = "access"
) -> Actor:
    payload = decode_token(settings, token, token_type)
    user = await users_repository.get_active_session_user(
        session,
        session_id=payload.session_id,
        user_id=payload.user_id,
        now=datetime.now(UTC),
    )
    if user is None:
        raise NotAuthenticated()
    return _actor(user, payload.session_id)


async def refresh(session: AsyncSession, settings: Settings, refresh_token: str) -> RefreshResponse:
    actor = await authenticate(session, settings, refresh_token, token_type="refresh")
    return RefreshResponse(
        access_token=create_token(
            settings, user_id=actor.id, session_id=actor.session_id, token_type="access"
        )
    )


async def logout(session: AsyncSession, actor: Actor) -> None:
    await users_repository.revoke_session(session, actor.session_id, datetime.now(UTC))
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=actor.id,
        action=AuditAction.LOGOUT,
        user_id=actor.id,
    )
    await session.commit()


async def get_me(session: AsyncSession, actor: Actor) -> UserRead:
    user = await users_repository.get_by_id(session, actor.id)
    if user is None:
        raise NotAuthenticated()
    return UserRead.model_validate(user)


PASSWORD_CHANGE = FieldChange("password", None, None)


async def change_password(
    session: AsyncSession, actor: Actor, old_password: str, new_password: str
) -> None:
    user = await users_repository.get_by_id(session, actor.id)
    if user is None:
        raise NotAuthenticated()
    if not await verify_password(user.password_hash, old_password):
        raise AppError("Текущий пароль указан неверно", "INVALID_PASSWORD")
    user.password_hash = await hash_password(new_password)
    await users_repository.revoke_user_sessions(
        session, user.id, datetime.now(UTC), except_session_id=actor.session_id
    )
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id,
        action=AuditAction.UPDATE,
        user_id=actor.id,
        changes=[PASSWORD_CHANGE],
    )
    await session.commit()
