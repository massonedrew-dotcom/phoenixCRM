"""create properties with generated phone digits and search indexes

Revision ID: 9a6c2d4e8f07
Revises: 7f4a0b2c6d85
Create Date: 2026-09-15 12:30:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "9a6c2d4e8f07"
down_revision: str | Sequence[str] | None = "7f4a0b2c6d85"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

deal_type = postgresql.ENUM("rent", "sale", name="deal_type", create_type=False)
interest_status = postgresql.ENUM("hot", "warm", "cold", name="interest_status", create_type=False)

ACTIVE = sa.text("is_deleted = false")


def upgrade() -> None:
    bind = op.get_bind()
    deal_type.create(bind)
    interest_status.create(bind)
    op.create_table(
        "properties",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.BigInteger(), sa.Identity(always=False), nullable=False),
        sa.Column("request_no", sa.String(64), nullable=True),
        sa.Column("deal_type", deal_type, server_default="rent", nullable=False),
        sa.Column("district_id", sa.Uuid(), nullable=False),
        sa.Column("landmark", sa.Text(), nullable=False),
        sa.Column("owner_name", sa.String(160), nullable=True),
        sa.Column("owner_phone", sa.String(32), nullable=False),
        sa.Column(
            "owner_phone_digits",
            sa.String(32),
            sa.Computed(r"regexp_replace(owner_phone, '\D', '', 'g')", persisted=True),
            nullable=False,
        ),
        sa.Column("interest_status", interest_status, server_default="warm", nullable=False),
        sa.Column("free_until", sa.Date(), nullable=True),
        sa.Column("occupied_until", sa.Date(), nullable=True),
        sa.Column("price", sa.Numeric(12, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("is_deleted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["district_id"], ["districts.id"], name="fk_properties_district_id_districts"
        ),
        sa.ForeignKeyConstraint(
            ["created_by"], ["users.id"], name="fk_properties_created_by_users"
        ),
        sa.ForeignKeyConstraint(
            ["updated_by"], ["users.id"], name="fk_properties_updated_by_users"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_properties"),
        sa.UniqueConstraint("code", name="uq_properties_code"),
    )

    op.create_index("idx_props_active", "properties", ["is_deleted", sa.text("created_at DESC")])
    op.create_index("idx_props_district", "properties", ["district_id"], postgresql_where=ACTIVE)
    op.create_index("idx_props_created_by", "properties", ["created_by"], postgresql_where=ACTIVE)
    op.create_index("idx_props_status", "properties", ["interest_status"], postgresql_where=ACTIVE)
    op.create_index("idx_props_phone_digits", "properties", ["owner_phone_digits"])
    op.create_index(
        "idx_props_phone_trgm",
        "properties",
        ["owner_phone_digits"],
        postgresql_using="gin",
        postgresql_ops={"owner_phone_digits": "gin_trgm_ops"},
    )
    op.create_index("idx_props_request_no", "properties", ["request_no"])
    op.create_index(
        "idx_props_request_trgm",
        "properties",
        ["request_no"],
        postgresql_using="gin",
        postgresql_ops={"request_no": "gin_trgm_ops"},
    )
    op.create_index(
        "idx_props_landmark_trgm",
        "properties",
        ["landmark"],
        postgresql_using="gin",
        postgresql_ops={"landmark": "gin_trgm_ops"},
    )
    op.create_index("idx_props_occupied", "properties", ["occupied_until"], postgresql_where=ACTIVE)

    op.execute("""
        CREATE FUNCTION properties_reject_delete() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'properties are soft-deleted only';
        END;
        $$
        """)
    op.execute("""
        CREATE TRIGGER properties_soft_delete_only
        BEFORE DELETE ON properties
        FOR EACH ROW EXECUTE FUNCTION properties_reject_delete()
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER properties_soft_delete_only ON properties")
    op.execute("DROP FUNCTION properties_reject_delete()")
    op.drop_table("properties")
    bind = op.get_bind()
    interest_status.drop(bind)
    deal_type.drop(bind)
