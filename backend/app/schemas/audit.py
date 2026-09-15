import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.common import UserRef


class AuditEntry(BaseModel):
    id: int
    entity: str
    entity_id: uuid.UUID | None
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    user: UserRef | None
    ip: str | None
    created_at: datetime
