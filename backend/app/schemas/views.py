import uuid
from datetime import datetime

from pydantic import BaseModel

from app.core.enums import Role
from app.schemas.common import UserRef


class UserViewSummary(BaseModel):
    user_id: uuid.UUID
    full_name: str
    username: str
    role: Role
    is_active: bool
    views: int
    cards: int
    last_viewed_at: datetime


class PropertyRef(BaseModel):
    id: uuid.UUID
    code: int
    landmark: str


class ViewEntry(BaseModel):
    id: int
    viewed_at: datetime
    user: UserRef
    property: PropertyRef
    ip: str | None
