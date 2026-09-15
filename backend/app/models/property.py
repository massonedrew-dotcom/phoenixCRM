import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    Boolean,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Identity,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    false,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import DealType, InterestStatus, MediaKind
from app.models.base import Base, pg_enum


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    code: Mapped[int] = mapped_column(BigInteger, Identity(always=False), unique=True)
    request_no: Mapped[str | None] = mapped_column(String(64))
    deal_type: Mapped[DealType] = mapped_column(
        pg_enum(DealType, "deal_type"), default=DealType.RENT, server_default=DealType.RENT.value
    )
    district_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("districts.id"))
    landmark: Mapped[str] = mapped_column(Text)
    owner_name: Mapped[str | None] = mapped_column(String(160))
    owner_phone: Mapped[str] = mapped_column(String(32))
    owner_phone_digits: Mapped[str] = mapped_column(
        String(32), Computed(r"regexp_replace(owner_phone, '\D', '', 'g')", persisted=True)
    )
    interest_status: Mapped[InterestStatus] = mapped_column(
        pg_enum(InterestStatus, "interest_status"),
        default=InterestStatus.WARM,
        server_default=InterestStatus.WARM.value,
    )
    free_until: Mapped[date | None] = mapped_column(Date)
    occupied_until: Mapped[date | None] = mapped_column(Date)
    price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    note: Mapped[str | None] = mapped_column(Text)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_by: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class PropertyMedia(Base):
    __tablename__ = "property_media"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("properties.id", ondelete="RESTRICT"))
    kind: Mapped[MediaKind] = mapped_column(pg_enum(MediaKind, "media_kind"))
    storage_key: Mapped[str] = mapped_column(Text)
    thumb_key: Mapped[str | None] = mapped_column(Text)
    original_name: Mapped[str | None] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    uploaded_by: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


_active = Property.is_deleted == false()

Index("idx_props_active", Property.is_deleted, Property.created_at.desc())
Index("idx_props_district", Property.district_id, postgresql_where=_active)
Index("idx_props_created_by", Property.created_by, postgresql_where=_active)
Index("idx_props_status", Property.interest_status, postgresql_where=_active)
Index("idx_props_phone_digits", Property.owner_phone_digits)
Index(
    "idx_props_phone_trgm",
    Property.owner_phone_digits,
    postgresql_using="gin",
    postgresql_ops={"owner_phone_digits": "gin_trgm_ops"},
)
Index("idx_props_request_no", Property.request_no)
Index(
    "idx_props_request_trgm",
    Property.request_no,
    postgresql_using="gin",
    postgresql_ops={"request_no": "gin_trgm_ops"},
)
Index(
    "idx_props_landmark_trgm",
    Property.landmark,
    postgresql_using="gin",
    postgresql_ops={"landmark": "gin_trgm_ops"},
)
Index("idx_props_occupied", Property.occupied_until, postgresql_where=_active)
Index(
    "idx_media_property",
    PropertyMedia.property_id,
    PropertyMedia.sort_order,
    postgresql_where=PropertyMedia.is_deleted == false(),
)
