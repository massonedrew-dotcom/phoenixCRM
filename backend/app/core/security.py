import asyncio
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from functools import lru_cache
from typing import Literal

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.core.config import Settings
from app.core.errors import NotAuthenticated

JWT_ALGORITHM = "HS256"
MIN_PASSWORD_LENGTH = 8
MEDIA_URL_TTL = timedelta(hours=12)

TokenType = Literal["access", "refresh"]
MediaVariant = Literal["original", "thumb"]

_hasher = PasswordHasher()


async def hash_password(password: str) -> str:
    return await asyncio.to_thread(_hasher.hash, password)


def _verify(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


async def verify_password(password_hash: str, password: str) -> bool:
    return await asyncio.to_thread(_verify, password_hash, password)


@lru_cache
def _dummy_hash() -> str:
    return _hasher.hash("timing-equalizer")


async def spend_verification_time(password: str) -> None:
    """Verify against a dummy hash so unknown usernames take as long as known ones."""
    dummy = await asyncio.to_thread(_dummy_hash)
    await verify_password(dummy, password)


@dataclass(frozen=True)
class TokenPayload:
    user_id: uuid.UUID
    session_id: uuid.UUID
    token_type: TokenType


def create_token(
    settings: Settings,
    *,
    user_id: uuid.UUID,
    session_id: uuid.UUID,
    token_type: TokenType,
    now: datetime | None = None,
) -> str:
    issued_at = now or datetime.now(UTC)
    lifetime = (
        timedelta(minutes=settings.access_token_minutes)
        if token_type == "access"
        else timedelta(days=settings.refresh_token_days)
    )
    claims = {
        "sub": str(user_id),
        "sid": str(session_id),
        "typ": token_type,
        "iat": issued_at,
        "exp": issued_at + lifetime,
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=JWT_ALGORITHM)


def decode_token(settings: Settings, token: str, expected_type: TokenType) -> TokenPayload:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[JWT_ALGORITHM],
            options={"require": ["sub", "sid", "typ", "exp"]},
        )
        if claims["typ"] != expected_type:
            raise NotAuthenticated()
        return TokenPayload(
            user_id=uuid.UUID(claims["sub"]),
            session_id=uuid.UUID(claims["sid"]),
            token_type=expected_type,
        )
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise NotAuthenticated() from exc


def _media_signature(settings: Settings, media_id: uuid.UUID, variant: str, expires: int) -> str:
    message = f"{media_id}:{variant}:{expires}".encode()
    key = settings.jwt_secret.get_secret_value().encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def sign_media(
    settings: Settings, media_id: uuid.UUID, variant: MediaVariant, now: datetime | None = None
) -> str:
    expires = int(((now or datetime.now(UTC)) + MEDIA_URL_TTL).timestamp())
    return f"{expires}.{_media_signature(settings, media_id, variant, expires)}"


def verify_media_token(
    settings: Settings,
    media_id: uuid.UUID,
    variant: MediaVariant,
    token: str,
    now: datetime | None = None,
) -> bool:
    expires_raw, _, signature = token.partition(".")
    if not expires_raw.isdigit() or not signature:
        return False
    expires = int(expires_raw)
    if expires < int((now or datetime.now(UTC)).timestamp()):
        return False
    expected = _media_signature(settings, media_id, variant, expires)
    return hmac.compare_digest(expected, signature)
