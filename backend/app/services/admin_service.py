import json
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from fastapi import HTTPException, Request
from sqlalchemy import func, select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.admin import AdminAuditLog, Announcement
from app.models.auth import User
from app.models.credit import CreditLedger
from app.models.generation import GenerationRun
from app.models.session import Session
from app.services.auth_service import get_auth_service, user_to_dict
from app.services.credit_service import CreditError, get_credit_service, ledger_to_dict
from app.services.provider_config_service import (
    ProviderConfigError,
    list_provider_configs,
    upsert_provider_config,
)
from app.services.session_store import get_session_store
from app.services.usage_service import UsageCharge


USER_STATUSES = {"active", "disabled"}
USER_ROLES = {"user", "admin"}
RUN_STATUSES = {"queued", "running", "completed", "failed", "cancelled"}
ANNOUNCEMENT_STATUSES = {"draft", "published", "archived"}


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

    def list_announcements(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if status is not None and status not in ANNOUNCEMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid announcement status")
        limit = max(1, min(limit, 100))
        offset = max(0, offset)
        with SessionLocal() as db:
            statement = select(Announcement)
            count_statement = select(func.count()).select_from(Announcement)
            if status:
                statement = statement.where(Announcement.status == status)
                count_statement = count_statement.where(Announcement.status == status)
            total = int(db.scalar(count_statement) or 0)
            rows = db.scalars(
                statement.order_by(Announcement.updated_at.desc()).offset(offset).limit(limit)
            ).all()
            return {
                "total": total,
                "announcements": [self._announcement_to_dict(row) for row in rows],
            }

    def upsert_announcement(
        self,
        *,
        admin: AdminUser,
        title: str,
        body: str,
        status: str,
        announcement_id: str | None = None,
    ) -> dict:
        clean_title = title.strip()[:240]
        clean_body = body.strip()
        if not clean_title:
            raise HTTPException(status_code=400, detail="Announcement title is required")
        if not clean_body:
            raise HTTPException(status_code=400, detail="Announcement body is required")
        if status not in ANNOUNCEMENT_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid announcement status")
        with SessionLocal() as db:
            row = db.get(Announcement, announcement_id) if announcement_id else None
            before = self._announcement_to_dict(row) if row else None
            if not row:
                row = Announcement(
                    id=uuid4().hex,
                    title=clean_title,
                    body=clean_body,
                    status=status,
                    published_at=datetime.now(UTC) if status == "published" else None,
                    created_by_user_id=admin.id,
                )
                db.add(row)
            else:
                row.title = clean_title
                row.body = clean_body
                if row.status != "published" and status == "published":
                    row.published_at = datetime.now(UTC)
                row.status = status
            db.flush()
            after = self._announcement_to_dict(row)
            self._audit(
                db,
                admin_user_id=admin.id,
                action="announcement.upsert",
                target_type="announcement",
                target_id=row.id,
                payload={"before": before, "after": after},
            )
            db.commit()
            db.refresh(row)
            result = self._announcement_to_dict(row)
            if not result:
                raise HTTPException(status_code=404, detail="Announcement not found")
            return result

    def list_credit_rules(self) -> dict:
        rules = get_credit_service().list_rules()
        return {"total": len(rules), "rules": rules}

    def update_credit_rule(
        self,
        *,
        admin: AdminUser,
        action: str,
        amount: int,
        enabled: bool,
    ) -> dict:
        try:
            rule = get_credit_service().upsert_rule(
                action=action,
                amount=amount,
                enabled=enabled,
                metadata={},
            )
        except CreditError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with SessionLocal() as db:
            self._audit(
                db,
                admin_user_id=admin.id,
                action="credit_rule.update",
                target_type="credit_rule",
                target_id=action,
                payload={"rule": rule},
            )
            db.commit()
        return rule

    def list_provider_configs(self) -> dict:
        configs = list_provider_configs()
        return {"total": len(configs), "configs": configs}

    def upsert_provider_config(
        self,
        *,
        admin: AdminUser,
        provider: str,
        name: str,
        model: str,
        base_url: str | None,
        api_key: str | None,
        status: str,
        config_id: str | None = None,
    ) -> dict:
        try:
            config = upsert_provider_config(
                provider=provider,
                name=name,
                model=model,
                base_url=base_url,
                api_key=api_key,
                status=status,
                metadata={},
                config_id=config_id,
            )
        except ProviderConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        with SessionLocal() as db:
            audit_payload = dict(config)
            audit_payload.pop("api_key_masked", None)
            self._audit(
                db,
                admin_user_id=admin.id,
                action="provider_config.upsert",
                target_type="provider_config",
                target_id=config["id"],
                payload=audit_payload,
            )
            db.commit()
        return config

    def get_dashboard_stats(self) -> dict:
        with SessionLocal() as db:
            status_rows = db.execute(
                select(GenerationRun.status, func.count()).group_by(GenerationRun.status)
            ).all()
            credit_rows = db.execute(
                select(CreditLedger.reason, func.coalesce(func.sum(CreditLedger.amount), 0))
                .group_by(CreditLedger.reason)
                .order_by(func.coalesce(func.sum(CreditLedger.amount), 0).desc())
                .limit(12)
            ).all()
            return {
                "users": {
                    "total": int(db.scalar(select(func.count()).select_from(User)) or 0),
                    "active": int(
                        db.scalar(select(func.count()).select_from(User).where(User.status == "active"))
                        or 0
                    ),
                    "disabled": int(
                        db.scalar(
                            select(func.count()).select_from(User).where(User.status == "disabled")
                        )
                        or 0
                    ),
                },
                "projects": {
                    "total": int(db.scalar(select(func.count()).select_from(Session)) or 0),
                },
                "generation_runs": {
                    "total": int(db.scalar(select(func.count()).select_from(GenerationRun)) or 0),
                    "by_status": {status: int(count) for status, count in status_rows},
                },
                "credits": {
                    "total_balance": int(
                        db.scalar(select(func.coalesce(func.sum(User.points_balance), 0))) or 0
                    ),
                    "by_reason": [
                        {"reason": reason, "amount": int(amount)} for reason, amount in credit_rows
                    ],
                },
            }

    def list_generation_runs(
        self,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict:
        if status is not None and status not in RUN_STATUSES:
            raise HTTPException(status_code=400, detail="Invalid run status")
        limit = max(1, min(limit, 200))
        offset = max(0, offset)
        with SessionLocal() as db:
            statement = select(GenerationRun, Session).join(Session, Session.id == GenerationRun.session_id)
            count_statement = select(func.count()).select_from(GenerationRun)
            if status:
                statement = statement.where(GenerationRun.status == status)
                count_statement = count_statement.where(GenerationRun.status == status)
            total = int(db.scalar(count_statement) or 0)
            rows = db.execute(
                statement.order_by(GenerationRun.updated_at.desc()).offset(offset).limit(limit)
            ).all()
            return {
                "total": total,
                "runs": [self._generation_run_summary(run, session) for run, session in rows],
            }

    def cancel_generation_run(
        self,
        *,
        admin: AdminUser,
        run_id: str,
        reason: str,
    ) -> dict:
        clean_reason = reason.strip()[:160] or "Cancelled by admin"
        store = get_session_store()
        with SessionLocal() as db:
            row = db.scalar(select(GenerationRun).where(GenerationRun.id == run_id).with_for_update())
            if not row:
                raise HTTPException(status_code=404, detail="Generation run not found")
            if row.status not in {"queued", "running"}:
                raise HTTPException(status_code=400, detail=f"Cannot cancel run with status {row.status}")
            previous_status = row.status
            session = db.get(Session, row.session_id)
            row.status = "cancelled"
            row.error = clean_reason
            if session:
                session.status = "cancelled"
            self._audit(
                db,
                admin_user_id=admin.id,
                action="generation.cancel",
                target_type="generation_run",
                target_id=row.id,
                payload={"reason": clean_reason, "previous_status": previous_status},
            )
            db.commit()

        run = store.update_run(run_id, {"status": "cancelled", "error": clean_reason})
        if run.get("session_id"):
            try:
                store.update_session(run["session_id"], {"status": "cancelled"})
            except Exception:
                pass
        store.add_run_event(
            run_id,
            {
                "progress": int(run.get("progress") or 100),
                "message": f"Generation cancelled by admin: {clean_reason}",
                "type": "cancelled",
            },
        )
        refunded = self._refund_generation_run_if_needed(run)
        with SessionLocal() as db:
            db_run = db.get(GenerationRun, run_id)
            db_session = db.get(Session, db_run.session_id) if db_run else None
            if not db_run or not db_session:
                raise HTTPException(status_code=404, detail="Generation run not found after cancellation")
            summary = self._generation_run_summary(db_run, db_session)
        summary["refunded_credits"] = refunded
        return summary

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

    def _generation_run_summary(self, run: GenerationRun, session: Session) -> dict:
        run_metadata = self._read_json(run.metadata_json)
        session_metadata = self._read_json(session.metadata_json)
        charge = run_metadata.get("usage", {}).get("charge", {})
        generation = run_metadata.get("usage", {}).get("generation", {})
        failure = generation.get("failure") or {}
        return {
            "id": run.id,
            "session_id": run.session_id,
            "user_id": run.user_id,
            "user_email": self._user_email(run.user_id),
            "topic": session.topic,
            "page_count": session.page_count,
            "status": run.status,
            "progress": run.progress,
            "error": run.error,
            "failure_category": failure.get("category"),
            "failure_title": failure.get("title"),
            "failure_detail": failure.get("detail"),
            "duration_ms": int(generation.get("duration_ms") or 0),
            "charge_amount": int(charge.get("amount") or 0),
            "charge_settled": bool(charge.get("settled", True)),
            "anonymous": bool(charge.get("anonymous")),
            "session_status": session.status,
            "slide_count": int(session_metadata.get("slide_count") or 0),
            "created_at": run.created_at.isoformat(),
            "updated_at": run.updated_at.isoformat(),
            "refunded_credits": 0,
        }

    def _refund_generation_run_if_needed(self, run: dict) -> int:
        charge_data = (run.get("metadata") or {}).get("charge") or {}
        charge = UsageCharge(
            enabled=bool(charge_data.get("enabled")),
            user_id=charge_data.get("user_id"),
            action=str(charge_data.get("action") or "deck_generation"),
            amount=int(charge_data.get("amount") or 0),
            reference_type=charge_data.get("reference_type"),
            reference_id=charge_data.get("reference_id"),
            idempotency_key=charge_data.get("idempotency_key"),
            anonymous=bool(charge_data.get("anonymous")),
            settled=bool(charge_data.get("settled", True)),
        )
        if not charge.charged or not charge.idempotency_key:
            return 0
        get_credit_service().grant(
            charge.user_id or "",
            amount=charge.amount,
            reason="admin_cancel_refund",
            reference_type=charge.reference_type,
            reference_id=charge.reference_id,
            idempotency_key=f"refund:{charge.idempotency_key}",
            metadata={
                "original_action": charge.action,
                "original_idempotency_key": charge.idempotency_key,
            },
        )
        return charge.amount

    def _user_email(self, user_id: str | None) -> str | None:
        if not user_id:
            return None
        with SessionLocal() as db:
            user = db.get(User, user_id)
            return user.email if user else None

    def _read_json(self, value: str) -> dict:
        try:
            parsed = json.loads(value or "{}")
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

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

    def _announcement_to_dict(self, row: Announcement | None) -> dict | None:
        if not row:
            return None
        return {
            "id": row.id,
            "title": row.title,
            "body": row.body,
            "status": row.status,
            "published_at": row.published_at.isoformat() if row.published_at else None,
            "created_by_user_id": row.created_by_user_id,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
        }


def get_admin_service() -> AdminService:
    return AdminService()
