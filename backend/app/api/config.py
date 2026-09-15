from fastapi import APIRouter

from app.core.dependencies import ActorDep, SettingsDep
from app.schemas.config import ClientConfig

router = APIRouter(tags=["config"])


@router.get("/config", response_model=ClientConfig)
async def client_config(_: ActorDep, settings: SettingsDep) -> ClientConfig:
    """Values the UI needs to show сум prices and upload limits before saving."""
    return ClientConfig(
        uzs_per_ue=settings.uzs_per_ue,
        max_photo_mb=settings.max_photo_mb,
        max_video_mb=settings.max_video_mb,
        time_zone=settings.tz,
    )
