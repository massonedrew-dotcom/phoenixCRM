import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import AuditAction
from app.models.base import Base, pg_enum


class AuditLog(Base):
    """Append-only change log. Never update or delete rows."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[uuid.UUID | None]
    action: Mapped[AuditAction] = mapped_column(pg_enum(AuditAction, "audit_action"))
    field: Mapped[str | None] = mapped_column(String(64))
    old_value: Mapped[str | None] = mapped_column(Text)
    new_value: Mapped[str | None] = mapped_column(Text)
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


Index("idx_audit_entity", AuditLog.entity, AuditLog.entity_id, AuditLog.created_at.desc())
Index("idx_audit_user", AuditLog.user_id, AuditLog.created_at.desc())
