import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.enums import MediaKind


class MediaRead(BaseModel):
    id: uuid.UUID
    kind: MediaKind
    original_name: str | None
    mime_type: str
    size_bytes: int
    sort_order: int
    uploaded_at: datetime
    url: str
    thumb_url: str | None


class MediaPatch(BaseModel):
    sort_order: int = Field(ge=0, le=1_000_000)
