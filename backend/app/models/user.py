import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Index, String, func, true
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import Role
from app.models.base import Base, pg_enum


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("username = lower(username)", name="username_lowercase"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[Role] = mapped_column(pg_enum(Role, "user_role"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    __table_args__ = (Index("idx_auth_sessions_user", "user_id"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
