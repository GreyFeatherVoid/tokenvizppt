import json

from sqlalchemy import or_, select
from sqlalchemy.orm import selectinload

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.session import Session
from app.models.slide import Slide
from app.services.access_control import RequestAccess
from app.services.deck_spec import render_slide_spec_html
from app.services.session_store import SessionNotFoundError, safe_session_id


class DbSessionRepository:
    def list_sessions(self, limit: int = 30, access: RequestAccess | None = None) -> list[dict]:
        with SessionLocal() as db:
            statement = select(Session).order_by(Session.updated_at.desc())
            if access and access.auth_enabled:
                if access.user_id:
                    statement = statement.where(
                        or_(Session.user_id == access.user_id, Session.user_id.is_(None))
                    )
                else:
                    statement = statement.where(Session.user_id.is_(None))
            sessions = db.scalars(statement.limit(max(1, min(limit, 100)))).all()
            if access and access.auth_enabled:
                sessions = [
                    session
                    for session in sessions
                    if session.user_id == access.user_id
                    or (
                        session.user_id is None
                        and self.read_session_metadata(session.metadata_json).get("anonymous_ip_hash")
                        == access.ip_hash
                    )
                ]
            return [self.build_session_summary(session) for session in sessions]

    def get_session_detail(self, session_id: str) -> dict:
        session_id = safe_session_id(session_id)
        with SessionLocal() as db:
            session = db.scalar(
                select(Session)
                .options(selectinload(Session.slides))
                .where(Session.id == session_id)
            )
            if not session:
                raise SessionNotFoundError("Session not found in database")
            slides = sorted(session.slides, key=lambda slide: slide.page_number)
            metadata = self.read_session_metadata(session.metadata_json)
            return {
                "id": session.id,
                "topic": session.topic,
                "brief": session.brief,
                "page_count": session.page_count,
                "style_id": session.style_id,
                "style_prompt": metadata.get("style_prompt", ""),
                "enable_ai_images": bool(metadata.get("enable_ai_images")),
                "output_language": metadata.get("output_language") or "auto",
                "status": session.status,
                "latest_run_id": session.latest_run_id,
                "slides": [self.build_slide_payload(session.id, slide) for slide in slides],
            }

    def delete_session(self, session_id: str) -> None:
        session_id = safe_session_id(session_id)
        with SessionLocal() as db:
            session = db.get(Session, session_id)
            if not session:
                raise SessionNotFoundError("Session not found in database")
            db.delete(session)
            db.commit()

    def build_session_summary(self, session: Session) -> dict:
        metadata = self.read_session_metadata(session.metadata_json)
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

    def build_slide_payload(self, session_id: str, slide: Slide) -> dict:
        spec = self.read_slide_spec(session_id, slide.metadata_json)
        payload = {
            "id": slide.id.split(":")[-1],
            "page_number": slide.page_number,
            "title": slide.title,
            "html": render_slide_spec_html(spec) if spec else self.read_slide_html(session_id, slide.html_path),
        }
        if spec:
            payload["spec"] = spec
        return payload

    def read_slide_html(self, session_id: str, html_path: str) -> str:
        safe_id = safe_session_id(session_id)
        root = get_settings().storage_root / "sessions" / safe_id
        path = (root / html_path).resolve()
        allowed_root = root.resolve()
        if allowed_root not in [path, *path.parents]:
            raise SessionNotFoundError("Slide path is outside session storage")
        if not path.exists():
            raise SessionNotFoundError("Slide HTML file not found")
        return path.read_text(encoding="utf-8")

    def read_session_metadata(self, metadata_json: str) -> dict:
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError:
            return {}
        return metadata if isinstance(metadata, dict) else {}

    def read_slide_spec(self, session_id: str, metadata_json: str) -> dict | None:
        try:
            metadata = json.loads(metadata_json or "{}")
        except json.JSONDecodeError:
            return None
        spec_path = metadata.get("spec_path")
        if not spec_path:
            return None
        safe_id = safe_session_id(session_id)
        root = get_settings().storage_root / "sessions" / safe_id
        path = (root / str(spec_path)).resolve()
        allowed_root = root.resolve()
        if allowed_root not in [path, *path.parents] or not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None


def get_db_session_repository() -> DbSessionRepository:
    return DbSessionRepository()
