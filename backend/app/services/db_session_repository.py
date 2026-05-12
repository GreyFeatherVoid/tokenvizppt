import json

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.session import Session
from app.models.slide import Slide
from app.services.session_store import SessionNotFoundError, safe_session_id


class DbSessionRepository:
    def list_sessions(self, limit: int = 30) -> list[dict]:
        with SessionLocal() as db:
            sessions = db.scalars(
                select(Session)
                .order_by(Session.updated_at.desc())
                .limit(max(1, min(limit, 100)))
            ).all()
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
        payload = {
            "id": slide.id.split(":")[-1],
            "page_number": slide.page_number,
            "title": slide.title,
            "html": self.read_slide_html(session_id, slide.html_path),
        }
        spec = self.read_slide_spec(session_id, slide.metadata_json)
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
