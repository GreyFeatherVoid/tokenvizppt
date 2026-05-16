"""add accounts credits invites and admin tables

Revision ID: 20260515_0003
Revises: 20260511_0002
Create Date: 2026-05-15
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_0003"
down_revision: str | None = "20260511_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("email_domain", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("role", sa.String(length=40), nullable=False),
        sa.Column("points_balance", sa.Integer(), nullable=False),
        sa.Column("signup_credits_granted", sa.Boolean(), nullable=False),
        sa.Column("invite_code", sa.String(length=40), nullable=True),
        sa.Column("referred_by_user_id", sa.String(length=64), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["referred_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_email_domain"), "users", ["email_domain"], unique=False)
    op.create_index(op.f("ix_users_invite_code"), "users", ["invite_code"], unique=True)

    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=40), nullable=False),
        sa.Column("request_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_email_verification_codes_email"),
        "email_verification_codes",
        ["email"],
        unique=False,
    )
    op.create_index(
        op.f("ix_email_verification_codes_request_ip_hash"),
        "email_verification_codes",
        ["request_ip_hash"],
        unique=False,
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("token_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip_hash", sa.String(length=128), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_auth_sessions_token_hash"), "auth_sessions", ["token_hash"], unique=True)
    op.create_index(op.f("ix_auth_sessions_user_id"), "auth_sessions", ["user_id"], unique=False)

    op.create_table(
        "anonymous_usage",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("ip_hash", sa.String(length=128), nullable=False),
        sa.Column("usage_date", sa.Date(), nullable=False),
        sa.Column("generation_count", sa.Integer(), nullable=False),
        sa.Column("edit_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ip_hash", "usage_date", name="uq_anonymous_usage_ip_date"),
    )
    op.create_index(op.f("ix_anonymous_usage_ip_hash"), "anonymous_usage", ["ip_hash"], unique=False)

    op.create_table(
        "credit_ledger",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(length=80), nullable=False),
        sa.Column("reference_type", sa.String(length=80), nullable=True),
        sa.Column("reference_id", sa.String(length=64), nullable=True),
        sa.Column("idempotency_key", sa.String(length=160), nullable=True),
        sa.Column("balance_after", sa.Integer(), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_ledger_reason"), "credit_ledger", ["reason"], unique=False)
    op.create_index(op.f("ix_credit_ledger_user_id"), "credit_ledger", ["user_id"], unique=False)
    op.create_index(
        op.f("ix_credit_ledger_idempotency_key"),
        "credit_ledger",
        ["idempotency_key"],
        unique=True,
    )

    op.create_table(
        "daily_checkins",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("checkin_date", sa.Date(), nullable=False),
        sa.Column("points_awarded", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "checkin_date", name="uq_daily_checkins_user_date"),
    )
    op.create_index(op.f("ix_daily_checkins_user_id"), "daily_checkins", ["user_id"], unique=False)

    op.create_table(
        "credit_rules",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=80), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_credit_rules_action"), "credit_rules", ["action"], unique=False)

    op.create_table(
        "invite_codes",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_invite_codes_code"), "invite_codes", ["code"], unique=True)
    op.create_index(op.f("ix_invite_codes_user_id"), "invite_codes", ["user_id"], unique=False)

    op.create_table(
        "referrals",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("inviter_user_id", sa.String(length=64), nullable=False),
        sa.Column("invitee_user_id", sa.String(length=64), nullable=False),
        sa.Column("invite_code", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("rewarded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["invitee_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["inviter_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_referrals_invitee_user_id"),
        "referrals",
        ["invitee_user_id"],
        unique=True,
    )
    op.create_index(
        op.f("ix_referrals_inviter_user_id"),
        "referrals",
        ["inviter_user_id"],
        unique=False,
    )

    op.create_table(
        "announcements",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_user_id", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_announcements_created_by_user_id"),
        "announcements",
        ["created_by_user_id"],
        unique=False,
    )

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("admin_user_id", sa.String(length=64), nullable=False),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("target_type", sa.String(length=80), nullable=False),
        sa.Column("target_id", sa.String(length=64), nullable=True),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["admin_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_admin_audit_logs_action"),
        "admin_audit_logs",
        ["action"],
        unique=False,
    )
    op.create_index(
        op.f("ix_admin_audit_logs_admin_user_id"),
        "admin_audit_logs",
        ["admin_user_id"],
        unique=False,
    )

    op.create_table(
        "provider_configs",
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=True),
        sa.Column("model", sa.String(length=160), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("metadata_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_provider_configs_provider"), "provider_configs", ["provider"], unique=False)

    op.add_column("sessions", sa.Column("user_id", sa.String(length=64), nullable=True))
    op.create_index(op.f("ix_sessions_user_id"), "sessions", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_sessions_user_id_users",
        "sessions",
        "users",
        ["user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    for table_name in ("generation_runs", "assets", "messages", "slides", "slide_versions"):
        op.add_column(table_name, sa.Column("user_id", sa.String(length=64), nullable=True))
        op.create_index(op.f(f"ix_{table_name}_user_id"), table_name, ["user_id"], unique=False)
        op.create_foreign_key(
            f"fk_{table_name}_user_id_users",
            table_name,
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )


def downgrade() -> None:
    for table_name in ("slide_versions", "slides", "messages", "assets", "generation_runs"):
        op.drop_constraint(f"fk_{table_name}_user_id_users", table_name, type_="foreignkey")
        op.drop_index(op.f(f"ix_{table_name}_user_id"), table_name=table_name)
        op.drop_column(table_name, "user_id")

    op.drop_constraint("fk_sessions_user_id_users", "sessions", type_="foreignkey")
    op.drop_index(op.f("ix_sessions_user_id"), table_name="sessions")
    op.drop_column("sessions", "user_id")

    op.drop_index(op.f("ix_provider_configs_provider"), table_name="provider_configs")
    op.drop_table("provider_configs")
    op.drop_index(op.f("ix_admin_audit_logs_admin_user_id"), table_name="admin_audit_logs")
    op.drop_index(op.f("ix_admin_audit_logs_action"), table_name="admin_audit_logs")
    op.drop_table("admin_audit_logs")
    op.drop_index(op.f("ix_announcements_created_by_user_id"), table_name="announcements")
    op.drop_table("announcements")
    op.drop_index(op.f("ix_referrals_inviter_user_id"), table_name="referrals")
    op.drop_index(op.f("ix_referrals_invitee_user_id"), table_name="referrals")
    op.drop_table("referrals")
    op.drop_index(op.f("ix_invite_codes_user_id"), table_name="invite_codes")
    op.drop_index(op.f("ix_invite_codes_code"), table_name="invite_codes")
    op.drop_table("invite_codes")
    op.drop_index(op.f("ix_credit_rules_action"), table_name="credit_rules")
    op.drop_table("credit_rules")
    op.drop_index(op.f("ix_daily_checkins_user_id"), table_name="daily_checkins")
    op.drop_table("daily_checkins")
    op.drop_index(op.f("ix_credit_ledger_idempotency_key"), table_name="credit_ledger")
    op.drop_index(op.f("ix_credit_ledger_user_id"), table_name="credit_ledger")
    op.drop_index(op.f("ix_credit_ledger_reason"), table_name="credit_ledger")
    op.drop_table("credit_ledger")
    op.drop_index(op.f("ix_anonymous_usage_ip_hash"), table_name="anonymous_usage")
    op.drop_table("anonymous_usage")
    op.drop_index(op.f("ix_auth_sessions_user_id"), table_name="auth_sessions")
    op.drop_index(op.f("ix_auth_sessions_token_hash"), table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_index(
        op.f("ix_email_verification_codes_request_ip_hash"),
        table_name="email_verification_codes",
    )
    op.drop_index(op.f("ix_email_verification_codes_email"), table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
    op.drop_index(op.f("ix_users_invite_code"), table_name="users")
    op.drop_index(op.f("ix_users_email_domain"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
