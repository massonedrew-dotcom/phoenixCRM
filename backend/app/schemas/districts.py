import uuid
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, StringConstraints


def _not_blank(value: str) -> str:
    if not value:
        raise ValueError("Название не может быть пустым")
    return value


DistrictName = Annotated[
    str, StringConstraints(strip_whitespace=True, max_length=120), AfterValidator(_not_blank)
]


class DistrictRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    is_active: bool


class DistrictCreate(BaseModel):
    name: DistrictName


class DistrictPatch(BaseModel):
    name: DistrictName | None = None
    is_active: bool | None = None
