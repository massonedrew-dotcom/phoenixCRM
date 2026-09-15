from collections.abc import Mapping

from app.audit import FieldChange, diff_values
from app.models import Base


def apply_patch(record: Base, patch: Mapping[str, object]) -> list[FieldChange]:
    """Set only the attributes whose value changes and return those changes for the audit log."""
    old = {field: getattr(record, field) for field in patch}
    changes = diff_values(old, patch)
    for change in changes:
        setattr(record, change.field, patch[change.field])
    return changes
