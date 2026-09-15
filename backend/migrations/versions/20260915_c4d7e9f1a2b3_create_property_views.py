"""create append-only property view journal

Revision ID: c4d7e9f1a2b3
Revises: b8e1f3a5c719
Create Date: 2026-09-15 15:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c4d7e9f1a2b3"
down_revision: str | Sequence[str] | None = "b8e1f3a5c719"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "property_views",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("property_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "viewed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.ForeignKeyConstraint(
            ["property_id"], ["properties.id"], name="fk_property_views_property_id_properties"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_property_views_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_property_views"),
    )
    op.create_index("idx_views_user", "property_views", ["user_id", sa.text("viewed_at DESC")])
    op.create_index(
        "idx_views_property", "property_views", ["property_id", sa.text("viewed_at DESC")]
    )
    op.create_index("idx_views_time", "property_views", [sa.text("viewed_at DESC")])

    op.execute("""
        CREATE FUNCTION property_views_reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'property_views is append-only';
        END;
        $$
        """)
    op.execute("""
        CREATE TRIGGER property_views_append_only
        BEFORE UPDATE OR DELETE ON property_views
        FOR EACH ROW EXECUTE FUNCTION property_views_reject_change()
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER property_views_append_only ON property_views")
    op.execute("DROP FUNCTION property_views_reject_change()")
    op.drop_table("property_views")
