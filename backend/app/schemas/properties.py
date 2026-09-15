import re
import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import (
    AfterValidator,
    BaseModel,
    BeforeValidator,
    ConfigDict,
    Field,
    model_validator,
)

from app.core.enums import DealType, InterestStatus
from app.schemas.common import UserRef, strip_or_none
from app.schemas.media import MediaRead

MIN_PHONE_DIGITS = 5
MAX_PHONE_DIGITS = 15
_PHONE_CHARS = re.compile(r"^[0-9+\-\s()]+$")

SortOption = Literal["created_at", "-created_at", "updated_at", "-updated_at", "code", "-code"]
Availability = Literal["free", "occupied"]


def _validate_phone(value: str) -> str:
    value = value.strip()
    if not _PHONE_CHARS.fullmatch(value):
        raise ValueError("Телефон может содержать только цифры, пробелы, +, -, ( и )")
    digits = re.sub(r"\D", "", value)
    if not MIN_PHONE_DIGITS <= len(digits) <= MAX_PHONE_DIGITS:
        raise ValueError(f"В телефоне должно быть от {MIN_PHONE_DIGITS} до {MAX_PHONE_DIGITS} цифр")
    return value


def _require_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Поле не может быть пустым")
    return value


def optional_text(max_length: int) -> object:
    """Trimmed optional text; blank becomes None."""
    return Annotated[
        Annotated[str, Field(max_length=max_length)] | None, BeforeValidator(strip_or_none)
    ]


RequestNo = optional_text(64)
OwnerName = optional_text(160)
Note = optional_text(10000)
Phone = Annotated[str, Field(max_length=32), AfterValidator(_validate_phone)]
Landmark = Annotated[str, Field(max_length=2000), AfterValidator(_require_text)]
Price = Annotated[Decimal, Field(ge=0, max_digits=12, decimal_places=2)]


class PropertyCreate(BaseModel):
    # Unknown keys, including created_by, code, is_deleted, and timestamps, are ignored.
    model_config = ConfigDict(extra="ignore")

    request_no: RequestNo = None
    district_id: uuid.UUID
    landmark: Landmark
    owner_name: OwnerName = None
    owner_phone: Phone
    interest_status: InterestStatus = InterestStatus.WARM
    free_until: date | None = None
    occupied_until: date | None = None
    price: Price | None = None
    note: Note = None


REQUIRED_FIELDS = ("district_id", "landmark", "owner_phone", "interest_status")


class PropertyPatch(BaseModel):
    """Partial update: only fields present in the request body are changed."""

    model_config = ConfigDict(extra="ignore")

    request_no: RequestNo = None
    district_id: uuid.UUID | None = None
    landmark: Landmark | None = None
    owner_name: OwnerName = None
    owner_phone: Phone | None = None
    interest_status: InterestStatus | None = None
    free_until: date | None = None
    occupied_until: date | None = None
    price: Price | None = None
    note: Note = None

    @model_validator(mode="after")
    def required_fields_not_null(self) -> Self:
        for field in REQUIRED_FIELDS:
            if field in self.model_fields_set and getattr(self, field) is None:
                raise ValueError(f"Поле {field} не может быть пустым")
        return self


class DistrictRef(BaseModel):
    id: uuid.UUID
    name: str


class PropertyRead(BaseModel):
    id: uuid.UUID
    code: int
    deal_type: DealType
    request_no: str | None
    district: DistrictRef
    landmark: str
    owner_name: str | None
    owner_phone: str
    interest_status: InterestStatus
    free_until: date | None
    occupied_until: date | None
    price: Decimal | None
    price_uzs: Decimal | None
    note: str | None
    is_deleted: bool
    created_by: UserRef
    created_at: datetime
    updated_by: UserRef | None
    updated_at: datetime | None
    media: list[MediaRead]
    can_edit: bool


class PropertyListItem(BaseModel):
    id: uuid.UUID
    code: int
    district_name: str
    landmark: str
    interest_status: InterestStatus
    free_until: date | None
    occupied_until: date | None
    created_by_name: str
    created_at: datetime
    cover_thumb_url: str | None
    media_count: int


class DeletedPropertyItem(BaseModel):
    id: uuid.UUID
    code: int
    district_name: str
    landmark: str
    created_by_name: str
    deleted_by_name: str | None
    deleted_at: datetime | None
