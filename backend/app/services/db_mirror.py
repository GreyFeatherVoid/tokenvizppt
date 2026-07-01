import json
import logging
from collections.abc import Callable

from sqlalchemy import func, select

from app.db.session import SessionLocal
from app.models.generation import GenerationEvent, GenerationRun
from app.models.session import Session
from app.models.slide import Slide

logger = logging.getLogger(__name__)


def safe_db_write(operation: str, writer: Callable[[], None]) -> None:
    try:
        writer()
    except Exception as exc:
        logger.warning("DB mirror failed for %s: %s", operation, exc)


class DbMirror:
    def create_session(self, session: dict) -> None:
        def write() -> None:
            with SessionLocal() as db:
                db.merge(
                    Session(
                        id=session["id"],
                        user_id=session.get("user_id"),
                        topic=session["topic"],
                        brief=session["brief"],
                        page_count=int(session["page_count"]),
                        style_id=session["style_id"],
                        status=session["status"],
                        latest_run_id=session.get("latest_run_id"),
                        metadata_json=json.dumps(
                            {
                                "created_at": session.get("created_at"),
                                "style_prompt": session.get("style_prompt") or "",
                                "enable_ai_images": bool(session.get("enable_ai_images")),
                                "output_language": session.get("output_language") or "auto",
                                "user_id": session.get("user_id"),
                                "anonymous_ip_hash": session.get("anonymous_ip_hash"),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                db.commit()

        safe_db_write("create_session", write)

    def update_session(self, session: dict) -> None:
        def write() -> None:
            with SessionLocal() as db:
                row = db.get(Session, session["id"])
                if not row:
                    return
                try:
                    metadata = json.loads(row.metadata_json or "{}")
                except json.JSONDecodeError:
                    metadata = {}
                row.status = session["status"]
                row.user_id = session.get("user_id")
                row.latest_run_id = session.get("latest_run_id")
                metadata.update(
                    {
                        "updated_at": session.get("updated_at"),
                        "slide_count": len(session.get("slides") or []),
                        "enable_ai_images": bool(session.get("enable_ai_images")),
                        "output_language": session.get("output_language") or "auto",
                        "user_id": session.get("user_id"),
                        "anonymous_ip_hash": session.get("anonymous_ip_hash"),
                    }
                )
                row.metadata_json = json.dumps(
                    metadata,
                    ensure_ascii=False,
                )
                db.commit()

        safe_db_write("update_session", write)

    def create_run(self, run: dict) -> None:
        def write() -> None:
            metadata = run.get("metadata") or {}
            charge = metadata.get("charge") or {}
            with SessionLocal() as db:
                db.merge(
                    GenerationRun(
                        id=run["id"],
                        session_id=run["session_id"],
                        user_id=charge.get("user_id"),
                        prompt=run["prompt"],
                        status=run["status"],
                        progress=int(run.get("progress") or 0),
                        metadata_json=json.dumps(
                            {
                                "created_at": run.get("created_at"),
                                "usage": run.get("metadata") or {},
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                db.commit()

        safe_db_write("create_run", write)

    def update_run(self, run: dict) -> None:
        def write() -> None:
            metadata = run.get("metadata") or {}
            charge = metadata.get("charge") or {}
            with SessionLocal() as db:
                row = db.get(GenerationRun, run["id"])
                if not row:
                    return
                row.user_id = charge.get("user_id")
                row.status = run["status"]
                row.progress = int(run.get("progress") or 0)
                row.error = run.get("error")
                row.metadata_json = json.dumps(
                    {
                        "updated_at": run.get("updated_at"),
                        "event_count": len(run.get("events") or []),
                        "usage": run.get("metadata") or {},
                    },
                    ensure_ascii=False,
                )
                db.commit()

        safe_db_write("update_run", write)

    def add_run_event(self, run_id: str, event: dict) -> None:
        def write() -> None:
            with SessionLocal() as db:
                db.add(
                    GenerationEvent(
                        run_id=run_id,
                        event_type=str(event.get("type") or "progress"),
                        progress=int(event.get("progress") or 0),
                        message=str(event.get("message") or ""),
                        payload_json=json.dumps(event, ensure_ascii=False),
                    )
                )
                db.commit()

        safe_db_write("add_run_event", write)

    def upsert_slide(self, session_id: str, slide: dict) -> None:
        def write() -> None:
            with SessionLocal() as db:
                db.merge(
                    Slide(
                        id=f"{session_id}:{slide['id']}",
                        session_id=session_id,
                        page_number=int(slide["page_number"]),
                        title=slide["title"],
                        html_path=slide["html_path"],
                        status="completed",
                        metadata_json=json.dumps(
                            {
                                "html_size": len(slide.get("html") or ""),
                                "spec_path": slide.get("spec_path"),
                            },
                            ensure_ascii=False,
                        ),
                    )
                )
                db.commit()

        safe_db_write("upsert_slide", write)

    def counts(self) -> dict[str, int]:
        with SessionLocal() as db:
            return {
                "sessions": db.scalar(select(func.count()).select_from(Session)) or 0,
                "generation_runs": db.scalar(select(func.count()).select_from(GenerationRun)) or 0,
                "generation_events": db.scalar(select(func.count()).select_from(GenerationEvent))
                or 0,
                "slides": db.scalar(select(func.count()).select_from(Slide)) or 0,
            }


def get_db_mirror() -> DbMirror:
    return DbMirror()
