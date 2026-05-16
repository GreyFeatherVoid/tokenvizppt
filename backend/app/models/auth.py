from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, unique=True, index=True)
    email_domain: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="active")
    role: Mapped[str] = mapped_column(String(40), nullable=False, default="user")
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    points_balance: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    signup_credits_granted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    invite_code: Mapped[str | None] = mapped_column(String(40), nullable=True, unique=True)
    referred_by_user_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    metadata_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")

    auth_sessions = relationship("AuthSession", back_populates="user", cascade="all, delete-orphan")
    invite_codes = relationship("InviteCode", back_populates="user", cascade="all, delete-orphan")


class EmailVerificationCode(Base, TimestampMixin):
    __tablename__ = "email_verification_codes"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(320), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    purpose: Mapped[str] = mapped_column(String(40), nullable=False, default="login")
    request_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class AuthSession(Base, TimestampMixin):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip_hash: Mapped[str | None] = mapped_column(String(128), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)

    user = relationship("User", back_populates="auth_sessions")


class AnonymousUsage(Base, TimestampMixin):
    __tablename__ = "anonymous_usage"
    __table_args__ = (UniqueConstraint("ip_hash", "usage_date", name="uq_anonymous_usage_ip_date"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    ip_hash: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    usage_date: Mapped[date] = mapped_column(Date, nullable=False)
    generation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    edit_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
