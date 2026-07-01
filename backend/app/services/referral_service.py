import json
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.admin import InviteCode, Referral
from app.models.auth import User
from app.models.generation import GenerationRun
from app.models.session import Session
from app.services.credit_service import get_credit_service


class ReferralError(ValueError):
    pass


class ReferralService:
    def ensure_invite_code(self, db: DbSession, user: User) -> str:
        if not user.invite_code:
            user.invite_code = self._generate_unique_code(db)
        existing = db.scalar(select(InviteCode).where(InviteCode.code == user.invite_code))
        if not existing:
            db.add(
                InviteCode(
                    id=uuid4().hex,
                    user_id=user.id,
                    code=user.invite_code,
                    status="active",
                    metadata_json="{}",
                )
            )
        return user.invite_code

    def bind_referral_for_new_user(
        self,
        db: DbSession,
        *,
        invitee: User,
        referral_code: str | None,
    ) -> Referral | None:
        code = (referral_code or "").strip()
        if not code:
            return None
        invite = db.scalar(
            select(InviteCode).where(
                InviteCode.code == code,
                InviteCode.status == "active",
            )
        )
        if not invite:
            raise ReferralError("Invalid invite code")
        if invite.user_id == invitee.id:
            raise ReferralError("Cannot use your own invite code")
        inviter = db.get(User, invite.user_id)
        if not inviter or inviter.status != "active":
            raise ReferralError("Invalid invite code")
        existing = db.scalar(select(Referral).where(Referral.invitee_user_id == invitee.id))
        if existing:
            return existing
        invitee.referred_by_user_id = inviter.id
        referral = Referral(
            id=uuid4().hex,
            inviter_user_id=inviter.id,
            invitee_user_id=invitee.id,
            invite_code=code,
            status="pending",
            metadata_json="{}",
        )
        db.add(referral)
        settings = get_settings()
        invitee_bonus = get_credit_service().rule_amount(
            db,
            "referral_invitee_bonus",
            settings.referral_invitee_credits,
        )
        if invitee_bonus > 0:
            get_credit_service().grant_in_db(
                db,
                invitee,
                amount=invitee_bonus,
                reason="referral_invitee_bonus",
                reference_type="referral",
                reference_id=referral.id,
                idempotency_key=f"referral_invitee:{referral.id}",
                metadata={"invite_code": code, "inviter_user_id": inviter.id},
            )
        return referral

    def reward_first_generation(self, user_id: str | None, run_id: str) -> None:
        if not user_id:
            return
        with SessionLocal() as db:
            referral = db.scalar(
                select(Referral)
                .where(
                    Referral.invitee_user_id == user_id,
                    Referral.status == "pending",
                )
                .with_for_update()
            )
            if not referral:
                return
            completed_count = int(
                db.scalar(
                    select(func.count())
                    .select_from(GenerationRun)
                    .join(Session, Session.id == GenerationRun.session_id)
                    .where(
                        Session.user_id == user_id,
                        GenerationRun.status == "completed",
                    )
                )
                or 0
            )
            if completed_count > 0:
                return
            inviter = db.get(User, referral.inviter_user_id)
            if not inviter or inviter.status != "active":
                referral.status = "cancelled"
                referral.metadata_json = json.dumps(
                    {"cancel_reason": "inviter inactive"},
                    ensure_ascii=False,
                )
                db.commit()
                return
            settings = get_settings()
            amount = get_credit_service().rule_amount(
                db,
                "referral_inviter_bonus",
                settings.referral_inviter_credits,
            )
            if amount > 0:
                get_credit_service().grant_in_db(
                    db,
                    inviter,
                    amount=amount,
                    reason="referral_inviter_bonus",
                    reference_type="referral",
                    reference_id=referral.id,
                    idempotency_key=f"referral_inviter:{referral.id}",
                    metadata={"invitee_user_id": user_id, "run_id": run_id},
                )
            referral.status = "rewarded"
            referral.rewarded_at = datetime.now(UTC)
            referral.metadata_json = json.dumps(
                {"rewarded_run_id": run_id, "inviter_bonus": amount},
                ensure_ascii=False,
            )
            db.commit()

    def get_stats(self, user_id: str) -> dict:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise ReferralError("User not found")
            self.ensure_invite_code(db, user)
            total = int(
                db.scalar(
                    select(func.count()).select_from(Referral).where(Referral.inviter_user_id == user_id)
                )
                or 0
            )
            rewarded = int(
                db.scalar(
                    select(func.count())
                    .select_from(Referral)
                    .where(Referral.inviter_user_id == user_id, Referral.status == "rewarded")
                )
                or 0
            )
            pending = int(
                db.scalar(
                    select(func.count())
                    .select_from(Referral)
                    .where(Referral.inviter_user_id == user_id, Referral.status == "pending")
                )
                or 0
            )
            settings = get_settings()
            credit_service = get_credit_service()
            inviter_credits = credit_service.rule_amount(
                db,
                "referral_inviter_bonus",
                settings.referral_inviter_credits,
            )
            invitee_credits = credit_service.rule_amount(
                db,
                "referral_invitee_bonus",
                settings.referral_invitee_credits,
            )
            db.commit()
            return {
                "invite_code": user.invite_code,
                "inviter_credits": inviter_credits,
                "invitee_credits": invitee_credits,
                "total_invites": total,
                "rewarded_invites": rewarded,
                "pending_invites": pending,
            }

    def _generate_unique_code(self, db: DbSession) -> str:
        for _ in range(20):
            code = uuid4().hex[:10]
            if not db.scalar(select(InviteCode).where(InviteCode.code == code)):
                return code
        raise ReferralError("Could not generate invite code")


def get_referral_service() -> ReferralService:
    return ReferralService()
