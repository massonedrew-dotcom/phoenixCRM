import asyncio
import io
import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import BinaryIO

from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import initial_values, write_audit
from app.core.actor import Actor
from app.core.config import API_PREFIX, Settings
from app.core.enums import AuditAction, AuditEntity, MediaKind
from app.core.errors import AppError, FileTooLarge, NotAuthenticated, NotFound, UnsupportedMediaType
from app.core.security import MediaVariant, sign_media, verify_media_token
from app.models import Property, PropertyMedia
from app.repositories import media as media_repository
from app.repositories import properties as properties_repository
from app.schemas.media import MediaRead
from app.services.base import apply_patch
from app.services.permissions import ensure_can_edit_property
from app.storage import Storage
from app.storage import keys as storage_keys
from app.storage.processing import (
    SNIFF_BYTES,
    DetectedType,
    ThumbnailError,
    detect_type,
    make_photo_thumbnail,
    make_video_poster,
)

logger = logging.getLogger(__name__)

MAX_ORIGINAL_NAME_LENGTH = 255
MEGABYTE = 1024 * 1024
THUMBNAIL_MIME_TYPE = "image/webp"


@dataclass
class IncomingFile:
    """An uploaded file as received by the router."""

    filename: str | None
    file: BinaryIO
    size: int


def media_url(settings: Settings, media_id: uuid.UUID, variant: MediaVariant) -> str:
    token = sign_media(settings, media_id, variant)
    return f"{API_PREFIX}/media/{media_id}/file?variant={variant}&token={token}"


def to_media_read(settings: Settings, media: PropertyMedia) -> MediaRead:
    return MediaRead(
        id=media.id,
        kind=media.kind,
        original_name=media.original_name,
        mime_type=media.mime_type,
        size_bytes=media.size_bytes,
        sort_order=media.sort_order,
        uploaded_at=media.uploaded_at,
        url=media_url(settings, media.id, "original"),
        thumb_url=media_url(settings, media.id, "thumb") if media.thumb_key else None,
    )


async def list_media(
    session: AsyncSession, settings: Settings, property_id: uuid.UUID
) -> list[MediaRead]:
    records = await media_repository.list_for_property(session, property_id)
    return [to_media_read(settings, record) for record in records]


async def _editable_property(
    session: AsyncSession, actor: Actor, property_id: uuid.UUID
) -> Property:
    record = await properties_repository.get_for_update(session, property_id)
    if record is None or record.is_deleted:
        raise NotFound("Карточка не найдена")
    ensure_can_edit_property(actor, record.created_by)
    return record


def _size_limit(settings: Settings, kind: MediaKind) -> int:
    megabytes = settings.max_photo_mb if kind == MediaKind.PHOTO else settings.max_video_mb
    return megabytes * MEGABYTE


def _validate(settings: Settings, incoming: IncomingFile) -> DetectedType:
    incoming.file.seek(0)
    detected = detect_type(incoming.file.read(SNIFF_BYTES))
    incoming.file.seek(0)
    if detected is None:
        raise UnsupportedMediaType(
            f"Файл «{incoming.filename or 'без имени'}»: допустимы JPEG, PNG, WebP, HEIC, MP4, MOV"
        )
    if incoming.size > _size_limit(settings, detected.kind):
        limit_mb = (
            settings.max_photo_mb if detected.kind == MediaKind.PHOTO else settings.max_video_mb
        )
        raise FileTooLarge(
            f"Файл «{incoming.filename or 'без имени'}» больше допустимых {limit_mb} МБ"
        )
    return detected


@dataclass
class _Prepared:
    incoming: IncomingFile
    detected: DetectedType
    media_id: uuid.UUID
    thumbnail: bytes | None


async def _prepare(incoming: IncomingFile, detected: DetectedType) -> _Prepared:
    if detected.kind == MediaKind.PHOTO:
        try:
            thumbnail: bytes | None = await asyncio.to_thread(make_photo_thumbnail, incoming.file)
        except ThumbnailError as exc:
            raise UnsupportedMediaType(
                f"Файл «{incoming.filename or 'без имени'}» повреждён или не является изображением"
            ) from exc
    else:
        thumbnail = await asyncio.to_thread(make_video_poster, incoming.file, detected.extension)
    return _Prepared(incoming, detected, uuid.uuid4(), thumbnail)


def _original_name(filename: str | None) -> str | None:
    name = (filename or "").strip()
    return name[:MAX_ORIGINAL_NAME_LENGTH] or None


async def upload_media(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    actor: Actor,
    property_id: uuid.UUID,
    files: Sequence[IncomingFile],
) -> list[MediaRead]:
    if not files:
        raise AppError("Не выбрано ни одного файла", "NO_FILES")
    record = await _editable_property(session, actor, property_id)

    # Validate every file before storing any, so a bad file rejects the whole batch.
    detected = [await asyncio.to_thread(_validate, settings, incoming) for incoming in files]
    prepared = [
        await _prepare(incoming, kind) for incoming, kind in zip(files, detected, strict=True)
    ]

    saved_keys: list[str] = []
    try:
        sort_order = await media_repository.next_sort_order(session, record.id)
        records: list[PropertyMedia] = []
        for index, item in enumerate(prepared):
            key = storage_keys.media_key(record.id, item.media_id, item.detected.extension)
            saved_keys.append(await storage.save(key, item.incoming.file, item.detected.mime_type))
            thumb_key = None
            if item.thumbnail is not None:
                thumb_key = storage_keys.thumbnail_key(record.id, item.media_id)
                saved_keys.append(
                    await storage.save(thumb_key, io.BytesIO(item.thumbnail), THUMBNAIL_MIME_TYPE)
                )
            records.append(
                PropertyMedia(
                    id=item.media_id,
                    property_id=record.id,
                    kind=item.detected.kind,
                    storage_key=key,
                    thumb_key=thumb_key,
                    original_name=_original_name(item.incoming.filename),
                    mime_type=item.detected.mime_type,
                    size_bytes=item.incoming.size,
                    sort_order=sort_order + index,
                    uploaded_by=actor.id,
                )
            )
        media_repository.add_all(session, records)
        await session.flush()
        for media in records:
            await write_audit(
                session,
                entity=AuditEntity.MEDIA,
                entity_id=media.id,
                action=AuditAction.CREATE,
                user_id=actor.id,
                changes=initial_values(
                    {
                        "property_id": media.property_id,
                        "kind": media.kind,
                        "original_name": media.original_name,
                        "sort_order": media.sort_order,
                    }
                ),
            )
        await session.commit()
    except BaseException:
        await session.rollback()
        for key in saved_keys:
            try:
                await storage.delete(key)
            except OSError:
                logger.warning("Could not remove orphaned media file %s", key, exc_info=True)
        raise
    return [to_media_read(settings, media) for media in records]


async def _editable_media(
    session: AsyncSession, actor: Actor, media_id: uuid.UUID
) -> PropertyMedia:
    found = await media_repository.get_with_property(session, media_id, for_update=True)
    if found is None:
        raise NotFound("Файл не найден")
    media, owner = found
    if media.is_deleted or owner.is_deleted:
        raise NotFound("Файл не найден")
    ensure_can_edit_property(actor, owner.created_by)
    return media


async def reorder_media(
    session: AsyncSession, settings: Settings, actor: Actor, media_id: uuid.UUID, sort_order: int
) -> MediaRead:
    media = await _editable_media(session, actor, media_id)
    changes = apply_patch(media, {"sort_order": sort_order})
    if changes:
        await write_audit(
            session,
            entity=AuditEntity.MEDIA,
            entity_id=media.id,
            action=AuditAction.UPDATE,
            user_id=actor.id,
            changes=changes,
        )
        await session.commit()
    return to_media_read(settings, media)


async def delete_media(session: AsyncSession, actor: Actor, media_id: uuid.UUID) -> None:
    media = await _editable_media(session, actor, media_id)
    media.is_deleted = True
    await write_audit(
        session,
        entity=AuditEntity.MEDIA,
        entity_id=media.id,
        action=AuditAction.DELETE,
        user_id=actor.id,
    )
    await session.commit()


@dataclass(frozen=True)
class FileDelivery:
    location: str
    accel_redirect: bool
    mime_type: str
    filename: str | None


async def resolve_file(
    session: AsyncSession,
    settings: Settings,
    storage: Storage,
    media_id: uuid.UUID,
    variant: MediaVariant,
    *,
    token: str | None,
    actor: Actor | None,
) -> FileDelivery:
    """Authorize a media download and tell nginx (or the client) where the bytes are."""
    if actor is None and not (token and verify_media_token(settings, media_id, variant, token)):
        raise NotAuthenticated("Ссылка на файл недействительна или устарела")
    found = await media_repository.get_with_property(session, media_id)
    if found is None:
        raise NotFound("Файл не найден")
    media, owner = found
    if media.is_deleted or owner.is_deleted:
        raise NotFound("Файл не найден")
    if variant == "thumb":
        if media.thumb_key is None:
            raise NotFound("Миниатюра отсутствует")
        return FileDelivery(
            storage.url(media.thumb_key), storage.uses_accel_redirect, THUMBNAIL_MIME_TYPE, None
        )
    return FileDelivery(
        storage.url(media.storage_key),
        storage.uses_accel_redirect,
        media.mime_type,
        media.original_name,
    )
