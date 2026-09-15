"""create append-only audit log

Revision ID: 5d2e8f1a4b63
Revises: 3b1c9d0e7a21
Create Date: 2026-09-15 12:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5d2e8f1a4b63"
down_revision: str | Sequence[str] | None = "3b1c9d0e7a21"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

audit_action = postgresql.ENUM(
    "create",
    "update",
    "delete",
    "restore",
    "login",
    "login_failed",
    "logout",
    name="audit_action",
    create_type=False,
)


def upgrade() -> None:
    audit_action.create(op.get_bind())
    op.create_table(
        "audit_log",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("action", audit_action, nullable=False),
        sa.Column("field", sa.String(64), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_audit_log_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_audit_log"),
    )
    op.create_index(
        "idx_audit_entity",
        "audit_log",
        ["entity", "entity_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_audit_user", "audit_log", ["user_id", sa.text("created_at DESC")])

    op.execute("""
        CREATE FUNCTION audit_log_reject_change() RETURNS trigger
        LANGUAGE plpgsql AS $$
        BEGIN
            RAISE EXCEPTION 'audit_log is append-only';
        END;
        $$
        """)
    op.execute("""
        CREATE TRIGGER audit_log_append_only
        BEFORE UPDATE OR DELETE ON audit_log
        FOR EACH ROW EXECUTE FUNCTION audit_log_reject_change()
        """)
    op.execute("""
        CREATE TRIGGER audit_log_no_truncate
        BEFORE TRUNCATE ON audit_log
        FOR EACH STATEMENT EXECUTE FUNCTION audit_log_reject_change()
        """)


def downgrade() -> None:
    op.execute("DROP TRIGGER audit_log_no_truncate ON audit_log")
    op.execute("DROP TRIGGER audit_log_append_only ON audit_log")
    op.execute("DROP FUNCTION audit_log_reject_change()")
    op.drop_index("idx_audit_user", table_name="audit_log")
    op.drop_index("idx_audit_entity", table_name="audit_log")
    op.drop_table("audit_log")
    audit_action.drop(op.get_bind())
