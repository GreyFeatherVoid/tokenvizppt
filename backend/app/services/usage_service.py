from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.auth import AnonymousUsage
from app.services.auth_service import request_ip_hash
from app.services.credit_service import (
    CreditError,
    InsufficientCreditsError,
    get_credit_service,
)


class UsageError(ValueError):
    pass


class UsageQuotaExceededError(UsageError):
    pass


class UsageCreditsInsufficientError(UsageError):
    pass


@dataclass(frozen=True)
class UsageCharge:
    enabled: bool
    user_id: str | None
    action: str
    amount: int
    reference_type: str | None
    reference_id: str | None
    idempotency_key: str | None
    anonymous: bool = False

    @property
    def charged(self) -> bool:
        return self.enabled and bool(self.user_id) and self.amount > 0


class UsageService:
    def current_user_id(self, token: str | None) -> str | None:
        if not token:
            return None
        from app.services.auth_service import get_auth_service

        user = get_auth_service().get_user_by_token(token)
        return user.id if user else None

    def reserve_deck_generation(
        self,
        *,
        user_id: str | None,
        ip_address: str | None,
        session_id: str,
        page_count: int,
    ) -> UsageCharge:
        settings = get_settings()
        if not settings.auth_enabled:
            return self._disabled_charge("deck_generation", page_count, "session", session_id)
        if user_id:
            amount = self._rule_amount("deck_generation_page", settings.deck_generation_page_credits)
            total = max(0, int(page_count)) * amount
            return self._charge_user(
                user_id=user_id,
                amount=total,
                reason="deck_generation",
                reference_type="session",
                reference_id=session_id,
                idempotency_key=f"deck_generation:{session_id}",
                metadata={"page_count": page_count, "unit_amount": amount},
            )
        self._consume_anonymous(
            ip_address=ip_address,
            field="generation_count",
            limit=settings.anon_daily_generation_limit,
        )
        return UsageCharge(
            enabled=True,
            user_id=None,
            action="deck_generation",
            amount=0,
            reference_type="session",
            reference_id=session_id,
            idempotency_key=None,
            anonymous=True,
        )

    def reserve_slide_edit(
        self,
        *,
        user_id: str | None,
        ip_address: str | None,
        session_id: str,
        slide_id: str,
        action: str = "slide_edit",
    ) -> UsageCharge:
        settings = get_settings()
        if not settings.auth_enabled:
            return self._disabled_charge(action, 1, "slide", f"{session_id}:{slide_id}")
        if user_id:
            amount = self._rule_amount("slide_edit", settings.slide_edit_credits)
            return self._charge_user(
                user_id=user_id,
                amount=amount,
                reason=action,
                reference_type="slide",
                reference_id=f"{session_id}:{slide_id}",
                idempotency_key=f"{action}:{session_id}:{slide_id}:{uuid4().hex}",
                metadata={"session_id": session_id, "slide_id": slide_id},
            )
        self._consume_anonymous(
            ip_address=ip_address,
            field="edit_count",
            limit=settings.anon_daily_edit_limit,
        )
        return UsageCharge(
            enabled=True,
            user_id=None,
            action=action,
            amount=0,
            reference_type="slide",
            reference_id=f"{session_id}:{slide_id}",
            idempotency_key=None,
            anonymous=True,
        )

    def reserve_ai_images(
        self,
        *,
        user_id: str | None,
        run_id: str,
        count: int,
    ) -> UsageCharge:
        settings = get_settings()
        amount = max(0, int(count)) * self._rule_amount(
            "ai_image_generation",
            settings.ai_image_generation_credits,
        )
        if not settings.auth_enabled:
            return self._disabled_charge("ai_image_generation", amount, "generation_run", run_id)
        if not user_id or amount <= 0:
            return UsageCharge(
                enabled=True,
                user_id=user_id,
                action="ai_image_generation",
                amount=0,
                reference_type="generation_run",
                reference_id=run_id,
                idempotency_key=None,
            )
        return self._charge_user(
            user_id=user_id,
            amount=amount,
            reason="ai_image_generation",
            reference_type="generation_run",
            reference_id=run_id,
            idempotency_key=f"ai_image_generation:{run_id}:{count}",
            metadata={"image_count": count},
        )

    def refund(self, charge: UsageCharge, *, reason: str = "refund") -> None:
        if not charge.charged or not charge.idempotency_key:
            return
        get_credit_service().grant(
            charge.user_id or "",
            amount=charge.amount,
            reason=reason,
            reference_type=charge.reference_type,
            reference_id=charge.reference_id,
            idempotency_key=f"refund:{charge.idempotency_key}",
            metadata={
                "original_action": charge.action,
                "original_idempotency_key": charge.idempotency_key,
            },
        )

    def _charge_user(
        self,
        *,
        user_id: str,
        amount: int,
        reason: str,
        reference_type: str,
        reference_id: str,
        idempotency_key: str,
        metadata: dict | None = None,
    ) -> UsageCharge:
        try:
            if amount > 0:
                get_credit_service().charge(
                    user_id,
                    amount=amount,
                    reason=reason,
                    reference_type=reference_type,
                    reference_id=reference_id,
                    idempotency_key=idempotency_key,
                    metadata=metadata,
                )
        except InsufficientCreditsError as exc:
            raise UsageCreditsInsufficientError(str(exc)) from exc
        except CreditError as exc:
            raise UsageError(str(exc)) from exc
        return UsageCharge(
            enabled=True,
            user_id=user_id,
            action=reason,
            amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
        )

    def _consume_anonymous(self, *, ip_address: str | None, field: str, limit: int) -> None:
        if limit <= 0:
            raise UsageQuotaExceededError("Anonymous quota is exhausted")
        ip_hash = request_ip_hash(ip_address)
        today = date.today()
        with SessionLocal() as db:
            usage = db.scalar(
                select(AnonymousUsage)
                .where(
                    AnonymousUsage.ip_hash == ip_hash,
                    AnonymousUsage.usage_date == today,
                )
                .with_for_update()
            )
            if not usage:
                usage = AnonymousUsage(
                    id=uuid4().hex,
                    ip_hash=ip_hash,
                    usage_date=today,
                    generation_count=0,
                    edit_count=0,
                )
                db.add(usage)
                try:
                    db.flush()
                except IntegrityError:
                    db.rollback()
                    usage = db.scalar(
                        select(AnonymousUsage)
                        .where(
                            AnonymousUsage.ip_hash == ip_hash,
                            AnonymousUsage.usage_date == today,
                        )
                        .with_for_update()
                    )
                    if not usage:
                        raise

            current = int(getattr(usage, field))
            if current >= limit:
                raise UsageQuotaExceededError("Anonymous daily quota is exhausted")
            setattr(usage, field, current + 1)
            db.commit()

    def _rule_amount(self, action: str, fallback: int) -> int:
        with SessionLocal() as db:
            return get_credit_service().rule_amount(db, action, fallback)

    def _disabled_charge(
        self,
        action: str,
        amount: int,
        reference_type: str | None,
        reference_id: str | None,
    ) -> UsageCharge:
        return UsageCharge(
            enabled=False,
            user_id=None,
            action=action,
            amount=amount,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=None,
        )


def get_usage_service() -> UsageService:
    return UsageService()
