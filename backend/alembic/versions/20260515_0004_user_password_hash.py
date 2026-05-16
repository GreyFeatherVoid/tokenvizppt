"""add user password hash

Revision ID: 20260515_0004
Revises: 20260515_0003
Create Date: 2026-05-15
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0004"
down_revision: str | None = "20260515_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("password_hash", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "password_hash")
