import uuid
from dataclasses import dataclass

from app.core.enums import Role


@dataclass(frozen=True)
class Actor:
    """The authenticated user performing a request."""

    id: uuid.UUID
    username: str
    full_name: str
    role: Role
    session_id: uuid.UUID

    @property
    def is_head_or_admin(self) -> bool:
        return self.role in (Role.HEAD, Role.ADMIN)
