"""Test data helpers. They write directly through the ORM, bypassing services and audit."""

import io
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.enums import AuditEntity, Role
from app.core.security import create_token, hash_password
from app.models import AuditLog, AuthSession, District, Property, User

PASSWORD = "correct-horse-battery"
_password_hash: str | None = None


@dataclass
class Team:
    admin: User
    head: User
    agent: User
    other_agent: User


@dataclass
class TeamHeaders:
    admin: dict[str, str]
    head: dict[str, str]
    agent: dict[str, str]
    other_agent: dict[str, str]

    def for_role(self, role: str) -> dict[str, str]:
        headers: dict[str, str] = getattr(self, role)
        return headers


async def _hashed_password() -> str:
    global _password_hash
    if _password_hash is None:
        _password_hash = await hash_password(PASSWORD)
    return _password_hash


async def create_user(
    session: AsyncSession,
    role: Role,
    username: str,
    full_name: str,
    *,
    is_active: bool = True,
) -> User:
    user = User(
        username=username,
        full_name=full_name,
        password_hash=await _hashed_password(),
        role=role,
        is_active=is_active,
    )
    session.add(user)
    await session.flush()
    return user


async def auth_headers(session: AsyncSession, settings: Settings, user: User) -> dict[str, str]:
    now = datetime.now(UTC)
    auth_session = AuthSession(user_id=user.id, expires_at=now + timedelta(days=1))
    session.add(auth_session)
    await session.flush()
    token = create_token(
        settings, user_id=user.id, session_id=auth_session.id, token_type="access", now=now
    )
    return {"Authorization": f"Bearer {token}"}


async def create_district(session: AsyncSession, name: str, *, is_active: bool = True) -> District:
    district = District(name=name, is_active=is_active)
    session.add(district)
    await session.flush()
    return district


async def create_property(
    session: AsyncSession, creator: User, district: District, **fields: Any
) -> Property:
    values: dict[str, Any] = {
        "landmark": "рядом с метро Чиланзар, дом 9",
        "owner_phone": "+998 90 123-45-67",
    }
    values.update(fields)
    record = Property(district_id=district.id, created_by=creator.id, **values)
    session.add(record)
    await session.flush()
    return record


def property_payload(district: District, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "request_no": "12345",
        "district_id": str(district.id),
        "landmark": "рядом с метро Чиланзар, дом 9",
        "owner_name": "Иван",
        "owner_phone": "+998 90 123-45-67",
        "interest_status": "hot",
        "free_until": "2026-10-01",
        "occupied_until": None,
        "price": "350.00",
        "note": "Хозяин на связи после 18:00",
    }
    payload.update(overrides)
    return payload


async def audit_rows(
    session: AsyncSession, entity: AuditEntity, entity_id: object
) -> list[AuditLog]:
    result = await session.scalars(
        select(AuditLog)
        .where(AuditLog.entity == entity.value, AuditLog.entity_id == entity_id)
        .order_by(AuditLog.id)
    )
    return list(result)


def image_bytes(image_format: str = "JPEG", size: tuple[int, int] = (1200, 800)) -> bytes:
    image = Image.new("RGB", size, (180, 120, 60))
    buffer = io.BytesIO()
    image.save(buffer, format=image_format)
    return buffer.getvalue()


def mp4_bytes(size: int = 2048) -> bytes:
    """A buffer with an MP4 signature. Not playable; enough for type detection."""
    header = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"
    return header + b"\x00" * (size - len(header))
