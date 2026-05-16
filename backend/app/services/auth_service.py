import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.auth import AuthSession, EmailVerificationCode, User
from app.services.credit_service import get_credit_service
from app.services.email_service import EmailDeliveryError, send_verification_code, smtp_is_configured
from app.services.referral_service import ReferralError, get_referral_service


class AuthError(ValueError):
    pass


class EmailDomainNotAllowedError(AuthError):
    pass


class VerificationCodeInvalidError(AuthError):
    pass


class VerificationCodeRateLimitedError(AuthError):
    pass


class VerificationEmailDeliveryError(AuthError):
    pass


class UserAlreadyExistsError(AuthError):
    pass


class UserNotRegisteredError(AuthError):
    pass


class PasswordInvalidError(AuthError):
    pass


@dataclass(frozen=True)
class CurrentIdentity:
    user_id: str | None
    email: str | None
    role: str | None
    ip_hash: str
    is_authenticated: bool


@dataclass(frozen=True)
class SendCodeResult:
    email: str
    expires_at: str
    resend_after_seconds: int
    dev_code: str | None = None


@dataclass(frozen=True)
class LoginResult:
    token: str
    expires_at: str
    user: dict


@dataclass(frozen=True)
class RegisterResult:
    token: str
    expires_at: str
    user: dict


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise AuthError("Invalid email address")
    local, domain = normalized.rsplit("@", 1)
    if not local or not domain or "." not in domain:
        raise AuthError("Invalid email address")
    return normalized


def email_domain(email: str) -> str:
    return normalize_email(email).rsplit("@", 1)[1]


def hash_secret(value: str, salt: str) -> str:
    return hmac.new(salt.encode("utf-8"), value.encode("utf-8"), hashlib.sha256).hexdigest()


def request_ip_hash(ip_address: str | None) -> str:
    settings = get_settings()
    secret = settings.ip_hash_secret or settings.auth_cookie_name or "tokenvizppt-dev"
    return hash_secret(ip_address or "unknown", secret)


def validate_password_digest(password_digest: str) -> str:
    normalized = password_digest.strip().lower()
    if len(normalized) != 32 or any(char not in "0123456789abcdef" for char in normalized):
        raise PasswordInvalidError("Invalid password digest")
    return normalized


def user_to_dict(user: User) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "status": user.status,
        "points_balance": user.points_balance,
        "invite_code": user.invite_code,
        "created_at": user.created_at.isoformat(),
        "last_login_at": user.last_login_at.isoformat() if user.last_login_at else None,
    }


class AuthService:
    def send_code(self, email: str, ip_hash: str, purpose: str = "login") -> SendCodeResult:
        settings = get_settings()
        normalized = normalize_email(email)
        self._ensure_allowed_domain(normalized)
        if purpose not in {"login", "register"}:
            raise AuthError("Invalid verification purpose")
        now = datetime.now(UTC)

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == normalized))
            if purpose == "register" and user is not None:
                raise UserAlreadyExistsError("Email is already registered")
            if purpose == "login" and user is None:
                raise UserNotRegisteredError("Please register before logging in")

            latest = db.scalar(
                select(EmailVerificationCode)
                .where(
                    EmailVerificationCode.email == normalized,
                    EmailVerificationCode.purpose == purpose,
                )
                .order_by(EmailVerificationCode.created_at.desc())
                .limit(1)
            )
            if latest and (now - latest.created_at).total_seconds() < settings.auth_code_resend_seconds:
                raise VerificationCodeRateLimitedError("Please wait before requesting another code")

            code = f"{secrets.randbelow(1_000_000):06d}"
            expires_at = now + timedelta(seconds=settings.auth_code_ttl_seconds)
            verification_id = uuid4().hex
            db.add(
                EmailVerificationCode(
                    id=verification_id,
                    email=normalized,
                    code_hash=self._hash_code(normalized, code),
                    purpose=purpose,
                    request_ip_hash=ip_hash,
                    expires_at=expires_at,
                    attempt_count=0,
                )
            )
            db.commit()

        if smtp_is_configured():
            try:
                send_verification_code(
                    normalized,
                    code,
                    expires_minutes=max(1, settings.auth_code_ttl_seconds // 60),
                )
            except EmailDeliveryError as exc:
                with SessionLocal() as db:
                    verification = db.get(EmailVerificationCode, verification_id)
                    if verification:
                        db.delete(verification)
                        db.commit()
                raise VerificationEmailDeliveryError(
                    "Verification email could not be sent. Please check SMTP settings."
                ) from exc

        dev_code = code if settings.app_env != "production" and not smtp_is_configured() else None
        return SendCodeResult(
            email=normalized,
            expires_at=expires_at.isoformat(),
            resend_after_seconds=settings.auth_code_resend_seconds,
            dev_code=dev_code,
        )

    def register(
        self,
        *,
        email: str,
        password_digest: str,
        code: str,
        ip_hash: str,
        user_agent: str | None,
        referral_code: str | None = None,
    ) -> RegisterResult:
        settings = get_settings()
        normalized = normalize_email(email)
        self._ensure_allowed_domain(normalized)
        password_digest = validate_password_digest(password_digest)
        now = datetime.now(UTC)

        with SessionLocal() as db:
            if db.scalar(select(User).where(User.email == normalized)):
                raise UserAlreadyExistsError("Email is already registered")
            self._consume_verification_code(db, normalized, code, "register", now)

            user = User(
                id=uuid4().hex,
                email=normalized,
                email_domain=email_domain(normalized),
                status="active",
                role="admin" if normalized in settings.admin_emails else "user",
                password_hash=self._hash_password_digest(password_digest),
                points_balance=0,
                signup_credits_granted=False,
                invite_code=self._generate_invite_code(),
                referred_by_user_id=None,
                metadata_json="{}",
            )
            db.add(user)
            db.flush()
            get_referral_service().ensure_invite_code(db, user)

            try:
                get_referral_service().bind_referral_for_new_user(
                    db,
                    invitee=user,
                    referral_code=referral_code,
                )
            except ReferralError as exc:
                raise AuthError(str(exc)) from exc

            if settings.signup_credits > 0:
                get_credit_service().grant_in_db(
                    db,
                    user,
                    amount=settings.signup_credits,
                    reason="signup_bonus",
                    reference_type="user",
                    reference_id=user.id,
                    idempotency_key=f"signup:{user.id}",
                )
                user.signup_credits_granted = True

            user.last_login_at = now
            token, expires_at = self._create_session(db, user, ip_hash, user_agent, now)
            db.commit()
            db.refresh(user)

        return RegisterResult(
            token=token,
            expires_at=expires_at.isoformat(),
            user=user_to_dict(user),
        )

    def login(
        self,
        *,
        email: str,
        password_digest: str | None = None,
        code: str | None = None,
        ip_hash: str,
        user_agent: str | None,
    ) -> LoginResult:
        normalized = normalize_email(email)
        self._ensure_allowed_domain(normalized)
        now = datetime.now(UTC)

        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.email == normalized))
            if user is None:
                raise UserNotRegisteredError("Please register before logging in")

            if user.status != "active":
                raise AuthError("Account is disabled")

            if password_digest:
                if not user.password_hash or not self._verify_password_digest(
                    validate_password_digest(password_digest),
                    user.password_hash,
                ):
                    raise AuthError("Invalid email or password")
            elif code:
                self._consume_verification_code(db, normalized, code, "login", now)
            else:
                raise AuthError("Password or verification code is required")

            user.last_login_at = now
            token, expires_at = self._create_session(db, user, ip_hash, user_agent, now)
            db.commit()
            db.refresh(user)

        return LoginResult(
            token=token,
            expires_at=expires_at.isoformat(),
            user=user_to_dict(user),
        )

    def logout(self, token: str | None) -> None:
        if not token:
            return
        with SessionLocal() as db:
            session = db.scalar(select(AuthSession).where(AuthSession.token_hash == self._hash_token(token)))
            if session and not session.revoked_at:
                session.revoked_at = datetime.now(UTC)
                db.commit()

    def get_user_by_token(self, token: str | None) -> User | None:
        if not token:
            return None
        now = datetime.now(UTC)
        with SessionLocal() as db:
            session = db.scalar(
                select(AuthSession)
                .where(
                    AuthSession.token_hash == self._hash_token(token),
                    AuthSession.revoked_at.is_(None),
                    AuthSession.expires_at > now,
                )
                .limit(1)
            )
            if not session:
                return None
            user = db.get(User, session.user_id)
            if not user or user.status != "active":
                return None
            db.expunge(user)
            return user

    def _ensure_allowed_domain(self, email: str) -> None:
        settings = get_settings()
        allowed = {domain.strip().lower() for domain in settings.allowed_email_domains if domain.strip()}
        if allowed and email_domain(email) not in allowed:
            raise EmailDomainNotAllowedError("Email domain is not allowed")

    def _hash_code(self, email: str, code: str) -> str:
        settings = get_settings()
        salt = settings.ip_hash_secret or settings.auth_cookie_name or "tokenvizppt-dev"
        return hash_secret(f"{email}:{code}", salt)

    def _hash_token(self, token: str) -> str:
        settings = get_settings()
        salt = settings.ip_hash_secret or settings.auth_cookie_name or "tokenvizppt-dev"
        return hash_secret(token, salt)

    def _hash_password_digest(self, password_digest: str) -> str:
        salt = secrets.token_hex(16)
        digest = hashlib.pbkdf2_hmac("sha256", password_digest.encode("utf-8"), salt.encode("utf-8"), 260_000)
        return f"pbkdf2_sha256$260000${salt}${digest.hex()}"

    def _verify_password_digest(self, password_digest: str, password_hash: str) -> bool:
        try:
            algorithm, iterations, salt, expected = password_hash.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            digest = hashlib.pbkdf2_hmac(
                "sha256",
                password_digest.encode("utf-8"),
                salt.encode("utf-8"),
                int(iterations),
            ).hex()
            return hmac.compare_digest(digest, expected)
        except (ValueError, TypeError):
            return False

    def _consume_verification_code(self, db, email: str, code: str, purpose: str, now: datetime) -> None:
        verification = db.scalar(
            select(EmailVerificationCode)
            .where(
                EmailVerificationCode.email == email,
                EmailVerificationCode.purpose == purpose,
                EmailVerificationCode.consumed_at.is_(None),
            )
            .order_by(EmailVerificationCode.created_at.desc())
            .limit(1)
        )
        if not verification or verification.expires_at < now:
            raise VerificationCodeInvalidError("Verification code is invalid or expired")
        verification.attempt_count += 1
        if not hmac.compare_digest(verification.code_hash, self._hash_code(email, code)):
            db.commit()
            raise VerificationCodeInvalidError("Verification code is invalid or expired")
        verification.consumed_at = now

    def _create_session(
        self,
        db,
        user: User,
        ip_hash: str,
        user_agent: str | None,
        now: datetime,
    ) -> tuple[str, datetime]:
        settings = get_settings()
        token = secrets.token_urlsafe(32)
        expires_at = now + timedelta(days=settings.auth_session_ttl_days)
        db.add(
            AuthSession(
                id=uuid4().hex,
                user_id=user.id,
                token_hash=self._hash_token(token),
                expires_at=expires_at,
                request_ip_hash=ip_hash,
                user_agent=user_agent,
            )
        )
        return token, expires_at

    def _generate_invite_code(self) -> str:
        return secrets.token_urlsafe(6).replace("-", "").replace("_", "")[:10]


def get_auth_service() -> AuthService:
    return AuthService()
