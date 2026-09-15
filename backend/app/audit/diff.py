import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum


@dataclass(frozen=True)
class FieldChange:
    field: str
    old_value: str | None
    new_value: str | None


def to_audit_text(value: object) -> str | None:
    """Stable text form of a field value for the audit log."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, Enum):
        return str(value.value)
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def diff_values(old: Mapping[str, object], new: Mapping[str, object]) -> list[FieldChange]:
    """One change per key of `new` whose value differs from `old`."""
    return [
        FieldChange(field, to_audit_text(old.get(field)), to_audit_text(value))
        for field, value in new.items()
        if old.get(field) != value
    ]


def initial_values(values: Mapping[str, object]) -> list[FieldChange]:
    """Changes describing a newly created record: every populated field."""
    return [
        FieldChange(field, None, to_audit_text(value))
        for field, value in values.items()
        if value is not None
    ]
