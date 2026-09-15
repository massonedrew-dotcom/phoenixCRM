from enum import StrEnum
from typing import ClassVar

from sqlalchemy import Enum, MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Fetch server-generated values (defaults, identity, computed) right after INSERT/UPDATE.
    __mapper_args__: ClassVar[dict[str, object]] = {"eager_defaults": True}


def pg_enum(enum_class: type[StrEnum], name: str) -> Enum:
    """A PostgreSQL enum type that stores the enum values, not the member names."""
    return Enum(
        enum_class,
        name=name,
        values_callable=lambda members: [member.value for member in members],
        create_type=False,
    )
