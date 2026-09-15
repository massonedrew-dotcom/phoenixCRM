from decimal import Decimal

from pydantic import BaseModel


class ClientConfig(BaseModel):
    uzs_per_ue: Decimal
    max_photo_mb: int
    max_video_mb: int
    time_zone: str
