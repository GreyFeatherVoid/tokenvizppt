"""add slide versions

Revision ID: 20260511_0002
Revises: 20260511_0001
Create Date: 2026-05-11
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260511_0002"
down_revision: str | None = "20260511_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "slide_versions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("session_id", sa.String(length=64), nullable=False),
        sa.Column("slide_id", sa.String(length=64), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("html_path", sa.Text(), nullable=False),
        sa.Column("instruction", sa.Text(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_slide_versions_session_id"),
        "slide_versions",
        ["session_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_slide_versions_slide_id"),
        "slide_versions",
        ["slide_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_slide_versions_slide_id"), table_name="slide_versions")
    op.drop_index(op.f("ix_slide_versions_session_id"), table_name="slide_versions")
    op.drop_table("slide_versions")
