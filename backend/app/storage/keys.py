"""Storage keys for property media. Keys never contain user input."""

import uuid

THUMBNAIL_EXTENSION = "webp"


def media_key(property_id: uuid.UUID, media_id: uuid.UUID, extension: str) -> str:
    return f"properties/{property_id}/{media_id}.{extension}"


def thumbnail_key(property_id: uuid.UUID, media_id: uuid.UUID) -> str:
    return f"properties/{property_id}/thumbs/{media_id}.{THUMBNAIL_EXTENSION}"
