import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import initial_values, write_audit
from app.core.actor import Actor
from app.core.enums import AuditAction, AuditEntity, Role
from app.core.errors import Conflict, Forbidden, NotFound
from app.core.security import hash_password
from app.models import User
from app.repositories import users as users_repository
from app.schemas.users import RealtorRead, UserCreate, UserPatch, UserRead
from app.services.auth import PASSWORD_CHANGE
from app.services.base import apply_patch
from app.services.permissions import ensure_admin, ensure_head_or_admin

USERNAME_TAKEN = Conflict("Пользователь с таким логином уже существует", "USERNAME_TAKEN")


async def list_users(session: AsyncSession, actor: Actor) -> list[UserRead]:
    ensure_head_or_admin(actor)
    return [UserRead.model_validate(user) for user in await users_repository.list_all(session)]


async def list_realtors(session: AsyncSession) -> list[RealtorRead]:
    """Names of every user, for the realtor filter. Available to all authenticated users."""
    return [RealtorRead.model_validate(user) for user in await users_repository.list_all(session)]


async def _insert_user(
    session: AsyncSession,
    *,
    username: str,
    full_name: str,
    password: str,
    role: Role,
    created_by: uuid.UUID | None,
) -> User:
    if await users_repository.get_by_username(session, username) is not None:
        raise USERNAME_TAKEN
    user = User(
        username=username,
        full_name=full_name,
        password_hash=await hash_password(password),
        role=role,
        is_active=True,
        created_by=created_by,
    )
    users_repository.add(user=user, session=session)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise USERNAME_TAKEN from exc
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id,
        action=AuditAction.CREATE,
        # The acting user; the seeded first admin is recorded as creating itself.
        user_id=created_by or user.id,
        changes=initial_values(
            {
                "username": user.username,
                "full_name": user.full_name,
                "role": user.role,
                "is_active": user.is_active,
            }
        ),
    )
    await session.commit()
    return user


async def create_user(session: AsyncSession, actor: Actor, data: UserCreate) -> UserRead:
    ensure_admin(actor)
    user = await _insert_user(
        session,
        username=data.username,
        full_name=data.full_name,
        password=data.password,
        role=data.role,
        created_by=actor.id,
    )
    return UserRead.model_validate(user)


async def create_first_admin(
    session: AsyncSession, *, username: str, full_name: str, password: str
) -> UserRead:
    """Used only by the CLI; there is no public endpoint for this."""
    user = await _insert_user(
        session,
        username=username,
        full_name=full_name,
        password=password,
        role=Role.ADMIN,
        created_by=None,
    )
    return UserRead.model_validate(user)


async def _get_user(session: AsyncSession, user_id: uuid.UUID) -> User:
    user = await users_repository.get_by_id(session, user_id)
    if user is None:
        raise NotFound("Пользователь не найден")
    return user


async def update_user(
    session: AsyncSession, actor: Actor, user_id: uuid.UUID, data: UserPatch
) -> UserRead:
    ensure_admin(actor)
    user = await _get_user(session, user_id)
    patch = {
        field: value
        for field, value in data.model_dump(exclude_unset=True).items()
        if value is not None
    }
    if user.id == actor.id and (
        ("role" in patch and patch["role"] != user.role) or patch.get("is_active") is False
    ):
        raise Forbidden(
            "Нельзя изменить свою роль или отключить собственную учётную запись",
            "SELF_MODIFICATION",
        )
    changes = apply_patch(user, patch)
    if not changes:
        return UserRead.model_validate(user)
    if patch.get("is_active") is False:
        await users_repository.revoke_user_sessions(session, user.id, datetime.now(UTC))
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id,
        action=AuditAction.UPDATE,
        user_id=actor.id,
        changes=changes,
    )
    await session.commit()
    return UserRead.model_validate(user)


async def reset_password(
    session: AsyncSession, actor: Actor, user_id: uuid.UUID, new_password: str
) -> None:
    ensure_admin(actor)
    user = await _get_user(session, user_id)
    user.password_hash = await hash_password(new_password)
    await users_repository.revoke_user_sessions(session, user.id, datetime.now(UTC))
    await write_audit(
        session,
        entity=AuditEntity.USER,
        entity_id=user.id,
        action=AuditAction.UPDATE,
        user_id=actor.id,
        changes=[PASSWORD_CHANGE],
    )
    await session.commit()
