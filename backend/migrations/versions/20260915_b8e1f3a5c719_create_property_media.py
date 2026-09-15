"""create property media

Revision ID: b8e1f3a5c719
Revises: 9a6c2d4e8f07
Create Date: 2026-09-15 12:40:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "b8e1f3a5c719"
down_revision: str | Sequence[str] | None = "9a6c2d4e8f07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

media_kind = postgresql.ENUM("photo", "video", name="media_kind", create_type=False)


def upgrade() -> None:
    media_kind.create(op.get_bind())
    op.create_table(
        "property_media",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("kind", media_kind, nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("thumb_key", sa.Text(), nullable=True),
        sa.Column("original_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("uploaded_by", sa.Uuid(), nullable=False),
        sa.Column(
            "uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["property_id"],
            ["properties.id"],
            name="fk_property_media_property_id_properties",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by"], ["users.id"], name="fk_property_media_uploaded_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_property_media"),
    )
    op.create_index(
        "idx_media_property",
        "property_media",
        ["property_id", "sort_order"],
        postgresql_where=sa.text("is_deleted = false"),
    )


def downgrade() -> None:
    op.drop_index("idx_media_property", table_name="property_media")
    op.drop_table("property_media")
    media_kind.drop(op.get_bind())
