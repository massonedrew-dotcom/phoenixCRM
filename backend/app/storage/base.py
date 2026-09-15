from typing import BinaryIO, Protocol


class Storage(Protocol):
    """File storage backend. Keys are backend-neutral strings such as `properties/<id>/<uuid>.jpg`."""

    async def save(self, key: str, data: BinaryIO, content_type: str) -> str: ...

    async def delete(self, key: str) -> None: ...

    def url(self, key: str) -> str:
        """Where the file is delivered from: an nginx internal path or a presigned URL."""
        ...

    @property
    def uses_accel_redirect(self) -> bool:
        """True when `url()` is an nginx internal location for X-Accel-Redirect."""
        ...
