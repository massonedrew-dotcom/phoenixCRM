"""Role rules. Every service calls these; routers never decide permissions themselves."""

import uuid

from app.core.actor import Actor
from app.core.enums import Role
from app.core.errors import Forbidden


def ensure_admin(actor: Actor) -> None:
    if actor.role != Role.ADMIN:
        raise Forbidden()


def ensure_head_or_admin(actor: Actor) -> None:
    if not actor.is_head_or_admin:
        raise Forbidden()


def can_edit_property(actor: Actor, created_by: uuid.UUID) -> bool:
    """Agents edit only their own cards; head and admin edit every card."""
    return actor.is_head_or_admin or created_by == actor.id


def ensure_can_edit_property(actor: Actor, created_by: uuid.UUID) -> None:
    if not can_edit_property(actor, created_by):
        raise Forbidden("Можно изменять только свои карточки")
