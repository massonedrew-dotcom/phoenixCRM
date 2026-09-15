"""enable pg_trgm extension

Trigram similarity is required for fuzzy landmark search (see DATA_MODEL.md).

Revision ID: 17e7b65a2e0a
Revises:
Create Date: 2026-09-15 11:03:00

"""

from collections.abc import Sequence

from alembic import op

revision: str = "17e7b65a2e0a"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
