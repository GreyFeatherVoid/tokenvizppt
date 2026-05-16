import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as DbSession

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.auth import User
from app.models.credit import CreditLedger, CreditRule, DailyCheckin


class CreditError(ValueError):
    pass


class InsufficientCreditsError(CreditError):
    pass


class DailyCheckinAlreadyClaimedError(CreditError):
    pass


@dataclass(frozen=True)
class CreditBalance:
    user_id: str
    points_balance: int
    can_checkin: bool
    checkin_credits: int


def ledger_to_dict(row: CreditLedger) -> dict:
    metadata = {}
    try:
        metadata = json.loads(row.metadata_json or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "id": row.id,
        "user_id": row.user_id,
        "amount": row.amount,
        "reason": row.reason,
        "reference_type": row.reference_type,
        "reference_id": row.reference_id,
        "balance_after": row.balance_after,
        "metadata": metadata,
        "created_at": row.created_at.isoformat(),
    }


class CreditService:
    def get_balance(self, user_id: str) -> CreditBalance:
        with SessionLocal() as db:
            user = self._get_active_user(db, user_id)
            today = date.today()
            checkin = db.scalar(
                select(DailyCheckin).where(
                    DailyCheckin.user_id == user_id,
                    DailyCheckin.checkin_date == today,
                )
            )
            return CreditBalance(
                user_id=user.id,
                points_balance=user.points_balance,
                can_checkin=checkin is None,
                checkin_credits=self.rule_amount(db, "daily_checkin", get_settings().daily_checkin_credits),
            )

    def list_ledger(self, user_id: str, limit: int = 50) -> list[dict]:
        with SessionLocal() as db:
            self._get_active_user(db, user_id)
            rows = db.scalars(
                select(CreditLedger)
                .where(CreditLedger.user_id == user_id)
                .order_by(CreditLedger.created_at.desc())
                .limit(max(1, min(limit, 200)))
            ).all()
            return [ledger_to_dict(row) for row in rows]

    def checkin(self, user_id: str) -> CreditBalance:
        today = date.today()
        with SessionLocal() as db:
            user = self._get_active_user(db, user_id, for_update=True)
            existing = db.scalar(
                select(DailyCheckin).where(
                    DailyCheckin.user_id == user_id,
                    DailyCheckin.checkin_date == today,
                )
            )
            if existing:
                raise DailyCheckinAlreadyClaimedError("Daily check-in already claimed")
            amount = self.rule_amount(db, "daily_checkin", get_settings().daily_checkin_credits)
            db.add(
                DailyCheckin(
                    id=uuid4().hex,
                    user_id=user_id,
                    checkin_date=today,
                    points_awarded=amount,
                )
            )
            self.grant_in_db(
                db,
                user,
                amount=amount,
                reason="daily_checkin",
                reference_type="daily_checkin",
                reference_id=today.isoformat(),
                idempotency_key=f"daily_checkin:{user_id}:{today.isoformat()}",
            )
            try:
                db.commit()
            except IntegrityError as exc:
                db.rollback()
                raise DailyCheckinAlreadyClaimedError("Daily check-in already claimed") from exc
            db.refresh(user)
            return CreditBalance(
                user_id=user.id,
                points_balance=user.points_balance,
                can_checkin=False,
                checkin_credits=amount,
            )

    def grant(
        self,
        user_id: str,
        *,
        amount: int,
        reason: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> CreditLedger:
        with SessionLocal() as db:
            user = self._get_active_user(db, user_id, for_update=True)
            ledger = self.grant_in_db(
                db,
                user,
                amount=amount,
                reason=reason,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                metadata=metadata,
            )
            db.commit()
            db.refresh(ledger)
            return ledger

    def charge(
        self,
        user_id: str,
        *,
        amount: int,
        reason: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> CreditLedger:
        if amount < 0:
            raise CreditError("Charge amount must be positive")
        with SessionLocal() as db:
            user = self._get_active_user(db, user_id, for_update=True)
            if user.points_balance < amount:
                raise InsufficientCreditsError("Insufficient credits")
            ledger = self._insert_ledger(
                db,
                user,
                amount=-amount,
                reason=reason,
                reference_type=reference_type,
                reference_id=reference_id,
                idempotency_key=idempotency_key,
                metadata=metadata,
            )
            db.commit()
            db.refresh(ledger)
            return ledger

    def grant_in_db(
        self,
        db: DbSession,
        user: User,
        *,
        amount: int,
        reason: str,
        reference_type: str | None = None,
        reference_id: str | None = None,
        idempotency_key: str | None = None,
        metadata: dict | None = None,
    ) -> CreditLedger:
        if amount < 0:
            raise CreditError("Grant amount must be positive")
        return self._insert_ledger(
            db,
            user,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            metadata=metadata,
        )

    def rule_amount(self, db: DbSession, action: str, fallback: int) -> int:
        now = datetime.now(UTC)
        rule = db.scalar(
            select(CreditRule)
            .where(
                CreditRule.action == action,
                CreditRule.enabled.is_(True),
                (CreditRule.effective_from.is_(None)) | (CreditRule.effective_from <= now),
            )
            .order_by(CreditRule.effective_from.desc().nullslast(), CreditRule.created_at.desc())
            .limit(1)
        )
        return int(rule.amount) if rule else int(fallback)

    def _insert_ledger(
        self,
        db: DbSession,
        user: User,
        *,
        amount: int,
        reason: str,
        reference_type: str | None,
        reference_id: str | None,
        idempotency_key: str | None,
        metadata: dict | None,
    ) -> CreditLedger:
        if idempotency_key:
            existing = db.scalar(select(CreditLedger).where(CreditLedger.idempotency_key == idempotency_key))
            if existing:
                return existing
        user.points_balance += amount
        ledger = CreditLedger(
            id=uuid4().hex,
            user_id=user.id,
            amount=amount,
            reason=reason,
            reference_type=reference_type,
            reference_id=reference_id,
            idempotency_key=idempotency_key,
            balance_after=user.points_balance,
            metadata_json=json.dumps(metadata or {}, ensure_ascii=False),
        )
        db.add(ledger)
        return ledger

    def _get_active_user(self, db: DbSession, user_id: str, *, for_update: bool = False) -> User:
        statement = select(User).where(User.id == user_id)
        if for_update:
            statement = statement.with_for_update()
        user = db.scalar(statement)
        if not user or user.status != "active":
            raise CreditError("User not found or disabled")
        return user


def get_credit_service() -> CreditService:
    return CreditService()
