import uuid

from pydantic import BaseModel

DEFAULT_PAGE_SIZE = 50
MAX_PAGE_SIZE = 100


class Page[ItemT](BaseModel):
    items: list[ItemT]
    total: int
    page: int
    page_size: int


class UserRef(BaseModel):
    id: uuid.UUID
    full_name: str


def strip_or_none(value: str | None) -> str | None:
    """Trim a free-text value; an empty string becomes None."""
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
