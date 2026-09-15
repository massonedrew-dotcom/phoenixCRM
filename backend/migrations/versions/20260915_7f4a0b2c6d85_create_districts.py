"""create districts

Revision ID: 7f4a0b2c6d85
Revises: 5d2e8f1a4b63
Create Date: 2026-09-15 12:20:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "7f4a0b2c6d85"
down_revision: str | Sequence[str] | None = "5d2e8f1a4b63"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "districts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_districts"),
        sa.UniqueConstraint("name", name="uq_districts_name"),
    )


def downgrade() -> None:
    op.drop_table("districts")
