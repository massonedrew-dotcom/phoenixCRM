import uuid
from datetime import datetime

from sqlalchemy import select, true, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuthSession, User


async def get_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_by_username(session: AsyncSession, username: str) -> User | None:
    return await session.scalar(select(User).where(User.username == username))


async def list_all(session: AsyncSession) -> list[User]:
    result = await session.scalars(select(User).order_by(User.full_name, User.username))
    return list(result)


def add(session: AsyncSession, user: User) -> None:
    session.add(user)


async def create_session(
    session: AsyncSession, *, user_id: uuid.UUID, expires_at: datetime, ip: str | None
) -> AuthSession:
    auth_session = AuthSession(user_id=user_id, expires_at=expires_at, ip=ip)
    session.add(auth_session)
    await session.flush()
    return auth_session


async def get_active_session_user(
    session: AsyncSession, *, session_id: uuid.UUID, user_id: uuid.UUID, now: datetime
) -> User | None:
    """The user of a live session: not revoked, not expired, user still active."""
    return await session.scalar(
        select(User)
        .join(AuthSession, AuthSession.user_id == User.id)
        .where(
            AuthSession.id == session_id,
            AuthSession.user_id == user_id,
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
            User.is_active == true(),
        )
    )


async def revoke_session(session: AsyncSession, session_id: uuid.UUID, now: datetime) -> None:
    await session.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )


async def revoke_user_sessions(
    session: AsyncSession,
    user_id: uuid.UUID,
    now: datetime,
    except_session_id: uuid.UUID | None = None,
) -> None:
    statement = update(AuthSession).where(
        AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
    )
    if except_session_id is not None:
        statement = statement.where(AuthSession.id != except_session_id)
    await session.execute(statement.values(revoked_at=now))
