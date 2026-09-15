import uuid
from typing import Annotated
from urllib.parse import quote

from fastapi import APIRouter, Query, Response, status
from fastapi.responses import RedirectResponse

from app.core.dependencies import ActorDep, OptionalActorDep, SessionDep, SettingsDep, StorageDep
from app.core.security import MediaVariant
from app.schemas.media import MediaPatch, MediaRead
from app.services import media as media_service

router = APIRouter(prefix="/media", tags=["media"])


@router.patch("/{media_id}", response_model=MediaRead)
async def reorder_media(
    media_id: uuid.UUID,
    body: MediaPatch,
    actor: ActorDep,
    session: SessionDep,
    settings: SettingsDep,
) -> MediaRead:
    return await media_service.reorder_media(session, settings, actor, media_id, body.sort_order)


@router.delete("/{media_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_media(media_id: uuid.UUID, actor: ActorDep, session: SessionDep) -> None:
    await media_service.delete_media(session, actor, media_id)


@router.get("/{media_id}/file", response_class=Response)
async def media_file(
    media_id: uuid.UUID,
    actor: OptionalActorDep,
    session: SessionDep,
    settings: SettingsDep,
    storage: StorageDep,
    variant: MediaVariant = "original",
    token: Annotated[str | None, Query(max_length=200)] = None,
) -> Response:
    """Authorizes access; nginx delivers the bytes via X-Accel-Redirect (never streamed here)."""
    delivery = await media_service.resolve_file(
        session, settings, storage, media_id, variant, token=token, actor=actor
    )
    if not delivery.accel_redirect:
        return RedirectResponse(delivery.location, status_code=status.HTTP_302_FOUND)
    headers = {
        "X-Accel-Redirect": delivery.location,
        "Cache-Control": "private, max-age=3600",
    }
    if delivery.filename:
        headers["Content-Disposition"] = f"inline; filename*=UTF-8''{quote(delivery.filename)}"
    return Response(status_code=status.HTTP_200_OK, media_type=delivery.mime_type, headers=headers)
