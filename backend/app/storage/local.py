import asyncio
import re
import shutil
from pathlib import Path
from typing import BinaryIO

INTERNAL_MEDIA_PREFIX = "/internal-media/"
_SAFE_KEY = re.compile(r"^[A-Za-z0-9_-]+(/[A-Za-z0-9_-]+)*\.[A-Za-z0-9]+$")
COPY_BUFFER_BYTES = 1024 * 1024


class LocalStorage:
    """Stores files under MEDIA_ROOT; nginx serves them from an internal location."""

    uses_accel_redirect = True

    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.fullmatch(key):
            raise ValueError(f"Unsafe storage key: {key!r}")
        return self.root / key

    async def save(self, key: str, data: BinaryIO, content_type: str) -> str:
        path = self._path(key)

        def write() -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            data.seek(0)
            with path.open("wb") as target:
                shutil.copyfileobj(data, target, COPY_BUFFER_BYTES)

        await asyncio.to_thread(write)
        return key

    async def delete(self, key: str) -> None:
        path = self._path(key)
        await asyncio.to_thread(path.unlink, True)

    def url(self, key: str) -> str:
        self._path(key)
        return f"{INTERNAL_MEDIA_PREFIX}{key}"
