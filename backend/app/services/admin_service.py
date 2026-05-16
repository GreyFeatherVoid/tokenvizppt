import json
from dataclasses import dataclass
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import func, select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.admin import AdminAuditLog
from app.models.auth import User
from app.models.credit import CreditLedger
from app.models.generation import GenerationRun
from app.models.session import Session
from app.services.auth_service import get_auth_service, user_to_dict
from app.services.credit_service import ledger_to_dict


USER_STATUSES = {"active", "disabled"}
USER_ROLES = {"user", "admin"}


@dataclass(frozen=True)
class AdminUser:
    id: str
    email: str
    role: str


def require_admin(request: Request) -> AdminUser:
    settings = get_settings()
    user = get_auth_service().get_user_by_token(request.cookies.get(settings.auth_cookie_name))
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    admin_emails = {email.strip().lower() for email in settings.admin_emails if email.strip()}
    if user.role != "admin" and user.email not in admin_emails:
        raise HTTPException(status_code=403, detail="Admin access required")
    return AdminUser(id=user.id, email=user.email, role=user.role)


class AdminService:
    def list_users(
        self,
        *,
        query: str | None = None,
        status: str | None = None,
        role: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        with SessionLocal() as db:
            statement = select(User)
            count_statement = select(func.count()).select_from(User)
            filters = []
            if query:
                pattern = f"%{query.strip().lower()}%"
                filters.append(func.lower(User.email).like(pattern))
            if status:
                filters.append(User.status == status)
            if role:
                filters.append(User.role == role)
            for item in filters:
                statement = statement.where(item)
                count_statement = count_statement.where(item)
            total = int(db.scalar(count_statement) or 0)
            users = db.scalars(
                statement.order_by(User.created_at.desc()).offset(offset).limit(limit)
            ).all()
            return {
                "total": total,
                "users": [self._user_summary(db, user) for user in users],
            }

    def get_user(self, user_id: str) -> dict:
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            return self._user_summary(db, user)

    def update_user(
        self,
        *,
        admin: AdminUser,
        user_id: str,
        status: str | None = None,
        role: str | None = None,
    ) -> dict:
        if status is not None and status not in USER_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid user status")
        if role is not None and role not in USER_ROLES:
            raise HTTPException(status_code=400, detail="Invalid user role")
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user.id == admin.id and status == "disabled":
                raise HTTPException(status_code=400, detail="Admins cannot disable themselves")
            before = user_to_dict(user)
            if status is not None:
                user.status = status
            if role is not None:
                user.role = role
            self._audit(
                db,
                admin_user_id=admin.id,
                action="user.update",
                target_type="user",
                target_id=user.id,
                payload={"before": before, "after": user_to_dict(user)},
            )
            db.commit()
            db.refresh(user)
            return self._user_summary(db, user)

    def adjust_credits(
        self,
        *,
        admin: AdminUser,
        user_id: str,
        amount: int,
        reason: str,
    ) -> dict:
        if amount == 0:
            raise HTTPException(status_code=400, detail="Amount cannot be zero")
        clean_reason = reason.strip()[:120] or "Manual admin adjustment"
        with SessionLocal() as db:
            user = db.scalar(select(User).where(User.id == user_id).with_for_update())
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            if user.points_balance + amount < 0:
                raise HTTPException(status_code=400, detail="Credit adjustment would make balance negative")
            user.points_balance += amount
            ledger = CreditLedger(
                id=uuid4().hex,
                user_id=user.id,
                amount=amount,
                reason="admin_adjustment",
                reference_type="admin_user",
                reference_id=admin.id,
                idempotency_key=f"admin_adjustment:{admin.id}:{user.id}:{uuid4().hex}",
                balance_after=user.points_balance,
                metadata_json=json.dumps({"reason": clean_reason}, ensure_ascii=False),
            )
            db.add(ledger)
            self._audit(
                db,
                admin_user_id=admin.id,
                action="credit.adjust",
                target_type="user",
                target_id=user.id,
                payload={"amount": amount, "reason": clean_reason, "balance_after": user.points_balance},
            )
            db.commit()
            db.refresh(ledger)
            db.refresh(user)
            return {
                "user": self._user_summary(db, user),
                "ledger": ledger_to_dict(ledger),
            }

    def list_user_credits(self, user_id: str, *, limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            total = int(
                db.scalar(
                    select(func.count()).select_from(CreditLedger).where(CreditLedger.user_id == user_id)
                )
                or 0
            )
            rows = db.scalars(
                select(CreditLedger)
                .where(CreditLedger.user_id == user_id)
                .order_by(CreditLedger.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {"total": total, "entries": [ledger_to_dict(row) for row in rows]}

    def list_user_sessions(self, user_id: str, *, limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        with SessionLocal() as db:
            user = db.get(User, user_id)
            if not user:
                raise HTTPException(status_code=404, detail="User not found")
            total = int(
                db.scalar(select(func.count()).select_from(Session).where(Session.user_id == user_id))
                or 0
            )
            rows = db.scalars(
                select(Session)
                .where(Session.user_id == user_id)
                .order_by(Session.updated_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {"total": total, "sessions": [self._session_summary(row) for row in rows]}

    def list_audit_logs(self, *, limit: int = 50, offset: int = 0) -> dict:
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with SessionLocal() as db:
            total = int(db.scalar(select(func.count()).select_from(AdminAuditLog)) or 0)
            rows = db.scalars(
                select(AdminAuditLog)
                .order_by(AdminAuditLog.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
            return {"total": total, "logs": [self._audit_to_dict(row) for row in rows]}

    def _user_summary(self, db, user: User) -> dict:
        session_count = int(
            db.scalar(select(func.count()).select_from(Session).where(Session.user_id == user.id)) or 0
        )
        generation_count = int(
            db.scalar(
                select(func.count())
                .select_from(GenerationRun)
                .join(Session, Session.id == GenerationRun.session_id)
                .where(Session.user_id == user.id)
            )
            or 0
        )
        payload = user_to_dict(user)
        payload.update(
            {
                "session_count": session_count,
                "generation_count": generation_count,
            }
        )
        return payload

    def _session_summary(self, session: Session) -> dict:
        try:
            metadata = json.loads(session.metadata_json or "{}")
        except json.JSONDecodeError:
            metadata = {}
        return {
            "id": session.id,
            "topic": session.topic,
            "brief": session.brief,
            "page_count": session.page_count,
            "style_id": session.style_id,
            "status": session.status,
            "latest_run_id": session.latest_run_id,
            "slide_count": int(metadata.get("slide_count") or 0),
            "output_language": metadata.get("output_language") or "auto",
            "enable_ai_images": bool(metadata.get("enable_ai_images")),
            "created_at": session.created_at.isoformat(),
            "updated_at": session.updated_at.isoformat(),
        }

    def _audit(
        self,
        db,
        *,
        admin_user_id: str,
        action: str,
        target_type: str,
        target_id: str | None,
        payload: dict,
    ) -> None:
        db.add(
            AdminAuditLog(
                id=uuid4().hex,
                admin_user_id=admin_user_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                payload_json=json.dumps(payload, ensure_ascii=False),
            )
        )

    def _audit_to_dict(self, row: AdminAuditLog) -> dict:
        try:
            payload = json.loads(row.payload_json or "{}")
        except json.JSONDecodeError:
            payload = {}
        return {
            "id": row.id,
            "admin_user_id": row.admin_user_id,
            "action": row.action,
            "target_type": row.target_type,
            "target_id": row.target_id,
            "payload": payload,
            "created_at": row.created_at.isoformat(),
        }


def get_admin_service() -> AdminService:
    return AdminService()
