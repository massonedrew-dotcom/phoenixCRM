import uuid
from datetime import datetime
from ipaddress import IPv4Address, IPv6Address

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, func
from sqlalchemy.dialects.postgresql import INET
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PropertyView(Base):
    """Append-only journal of who opened which card, so bulk copying is visible."""

    __tablename__ = "property_views"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id"))
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ip: Mapped[IPv4Address | IPv6Address | None] = mapped_column(INET)


Index("idx_views_user", PropertyView.user_id, PropertyView.viewed_at.desc())
Index("idx_views_property", PropertyView.property_id, PropertyView.viewed_at.desc())
Index("idx_views_time", PropertyView.viewed_at.desc())
