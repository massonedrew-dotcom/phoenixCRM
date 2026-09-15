"""File storage abstraction. The only package allowed to build filesystem paths."""

from app.core.config import Settings
from app.storage.base import Storage
from app.storage.local import LocalStorage


def create_storage(settings: Settings) -> Storage:
    if settings.storage_backend == "local":
        return LocalStorage(settings.media_root)
    raise NotImplementedError("S3 storage backend is planned after the MVP")


__all__ = ["LocalStorage", "Storage", "create_storage"]
