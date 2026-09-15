"""create users and auth sessions

Revision ID: 3b1c9d0e7a21
Revises: 17e7b65a2e0a
Create Date: 2026-09-15 12:00:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "3b1c9d0e7a21"
down_revision: str | Sequence[str] | None = "17e7b65a2e0a"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

user_role = postgresql.ENUM("admin", "head", "agent", name="user_role", create_type=False)


def upgrade() -> None:
    user_role.create(op.get_bind())
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(64), nullable=False),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", user_role, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.CheckConstraint("username = lower(username)", name="ck_users_username_lowercase"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_users_created_by_users"),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("username", name="uq_users_username"),
    )
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"),
    )
    op.create_index("idx_auth_sessions_user", "auth_sessions", ["user_id"])


def downgrade() -> None:
    op.drop_index("idx_auth_sessions_user", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
    user_role.drop(op.get_bind())
