import json
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from app.core.settings import get_settings
from app.services.db_mirror import get_db_mirror
from app.services.editable_html import ensure_editable_ids


class SessionNotFoundError(Exception):
    pass


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


def safe_session_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        raise SessionNotFoundError("Session not found")
    return value


def safe_run_id(value: str) -> str:
    if not re.fullmatch(r"[a-zA-Z0-9_-]+", value):
        raise SessionNotFoundError("Run not found")
    return value


class SessionStore:
    def __init__(self, storage_root: Path | None = None) -> None:
        self.storage_root = storage_root or get_settings().storage_root
        self.sessions_root = self.storage_root / "sessions"
        self.runs_root = self.storage_root / "runs"
        self.export_runs_root = self.storage_root / "export_runs"
        self.sessions_root.mkdir(parents=True, exist_ok=True)
        self.runs_root.mkdir(parents=True, exist_ok=True)
        self.export_runs_root.mkdir(parents=True, exist_ok=True)

    def create_session(self, payload: dict) -> dict:
        session_id = uuid4().hex
        now = utc_now_iso()
        session = {
            "id": session_id,
            "topic": payload["topic"],
            "brief": payload["brief"],
            "page_count": payload["page_count"],
            "style_id": payload["style_id"],
            "style_prompt": (payload.get("style_prompt") or "").strip(),
            "enable_ai_images": bool(payload.get("enable_ai_images")),
            "output_language": payload.get("output_language") or "auto",
            "user_id": payload.get("user_id"),
            "anonymous_ip_hash": payload.get("anonymous_ip_hash"),
            "status": "created",
            "created_at": now,
            "updated_at": now,
            "slides": [],
        }
        session_dir = self.session_dir(session_id)
        (session_dir / "slides").mkdir(parents=True, exist_ok=True)
        self.write_json(session_dir / "session.json", session)
        get_db_mirror().create_session(session)
        return session

    def get_session(self, session_id: str) -> dict:
        session_id = safe_session_id(session_id)
        path = self.session_dir(session_id) / "session.json"
        if not path.exists():
            raise SessionNotFoundError("Session not found")
        return self.read_json(path)

    def update_session(self, session_id: str, patch: dict) -> dict:
        session = self.get_session(session_id)
        session.update(patch)
        session["updated_at"] = utc_now_iso()
        self.write_json(self.session_dir(session_id) / "session.json", session)
        get_db_mirror().update_session(session)
        return session

    def delete_session_files(self, session_id: str) -> None:
        session_id = safe_session_id(session_id)
        shutil.rmtree(self.session_dir(session_id), ignore_errors=True)
        shutil.rmtree(self.storage_root / "assets" / session_id, ignore_errors=True)

    def create_run(self, session_id: str, prompt: str, metadata: dict | None = None) -> dict:
        session = self.get_session(session_id)
        run_id = uuid4().hex
        now = utc_now_iso()
        run = {
            "id": run_id,
            "session_id": session["id"],
            "prompt": prompt,
            "status": "queued",
            "progress": 0,
            "events": [],
            "metadata": metadata or {},
            "created_at": now,
            "updated_at": now,
        }
        self.write_json(self.run_path(run_id), run)
        get_db_mirror().create_run(run)
        self.update_session(session_id, {"status": "generating", "latest_run_id": run_id})
        return run

    def get_run(self, run_id: str) -> dict:
        run_id = safe_run_id(run_id)
        path = self.run_path(run_id)
        if not path.exists():
            raise SessionNotFoundError("Run not found")
        return self.read_json(path)

    def update_run(self, run_id: str, patch: dict) -> dict:
        run = self.get_run(run_id)
        next_status = patch.get("status")
        if run.get("status") == "cancelled" and next_status in {"queued", "running"}:
            patch = {key: value for key, value in patch.items() if key != "status"}
        run.update(patch)
        run["updated_at"] = utc_now_iso()
        self.write_json(self.run_path(run_id), run)
        get_db_mirror().update_run(run)
        return run

    def add_run_event(self, run_id: str, event: dict) -> dict:
        run = self.get_run(run_id)
        event = {
            "timestamp": utc_now_iso(),
            **event,
        }
        run["events"] = [*run.get("events", []), event]
        run["progress"] = event.get("progress", run.get("progress", 0))
        run["updated_at"] = utc_now_iso()
        self.write_json(self.run_path(run_id), run)
        get_db_mirror().add_run_event(run_id, event)
        return event

    def create_export_run(self, session_id: str, export_format: str) -> dict:
        session = self.get_session(session_id)
        export_run_id = uuid4().hex
        now = utc_now_iso()
        run = {
            "id": export_run_id,
            "session_id": session["id"],
            "format": export_format,
            "status": "queued",
            "progress": 0,
            "file_name": None,
            "url": None,
            "error": None,
            "created_at": now,
            "updated_at": now,
        }
        self.write_json(self.export_run_path(export_run_id), run)
        return run

    def get_export_run(self, export_run_id: str) -> dict:
        export_run_id = safe_run_id(export_run_id)
        path = self.export_run_path(export_run_id)
        if not path.exists():
            raise SessionNotFoundError("Export run not found")
        return self.read_json(path)

    def update_export_run(self, export_run_id: str, patch: dict) -> dict:
        run = self.get_export_run(export_run_id)
        run.update(patch)
        run["updated_at"] = utc_now_iso()
        self.write_json(self.export_run_path(export_run_id), run)
        return run

    def write_slide(
        self,
        session_id: str,
        page_number: int,
        title: str,
        html: str,
        spec: dict | None = None,
    ) -> dict:
        session_id = safe_session_id(session_id)
        html = ensure_editable_ids(html)
        slides_dir = self.session_dir(session_id) / "slides"
        slides_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"slide-{page_number}.html"
        spec_file_name = f"slide-{page_number}.spec.json"
        (slides_dir / file_name).write_text(html, encoding="utf-8")
        if spec:
            self.write_json(slides_dir / spec_file_name, spec)
        else:
            (slides_dir / spec_file_name).unlink(missing_ok=True)
        slide = {
            "id": f"slide-{page_number}",
            "page_number": page_number,
            "title": title,
            "html_path": f"slides/{file_name}",
            "html": html,
        }
        if spec:
            slide["spec_path"] = f"slides/{spec_file_name}"
            slide["spec"] = spec
        get_db_mirror().upsert_slide(session_id, slide)
        return slide

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_root / safe_session_id(session_id)

    def run_path(self, run_id: str) -> Path:
        return self.runs_root / f"{safe_run_id(run_id)}.json"

    def export_run_path(self, export_run_id: str) -> Path:
        return self.export_runs_root / f"{safe_run_id(export_run_id)}.json"

    @staticmethod
    def read_json(path: Path) -> dict:
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def write_json(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_session_store() -> SessionStore:
    return SessionStore()
