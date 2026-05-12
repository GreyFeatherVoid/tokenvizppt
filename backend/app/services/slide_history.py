import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.slide import SlideVersion
from app.services.session_store import SessionNotFoundError, get_session_store, safe_session_id


class SlideVersionNotFoundError(Exception):
    pass


class SlideHistoryStore:
    def __init__(self) -> None:
        self.store = get_session_store()
        self.history_root = self.store.storage_root / "history"
        self.history_root.mkdir(parents=True, exist_ok=True)

    def create_snapshot(self, session_id: str, slide: dict, instruction: str) -> dict:
        session_id = safe_session_id(session_id)
        html = str(slide.get("html") or "")
        digest = self.html_digest(html)
        existing = self.find_version_by_digest(session_id, str(slide["id"]), digest)
        if existing:
            return existing

        version_id = uuid4().hex
        relative_path = Path("history") / session_id / f"{version_id}.html"
        absolute_path = self.store.storage_root / relative_path
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        absolute_path.write_text(html, encoding="utf-8")

        version = SlideVersion(
            id=version_id,
            session_id=session_id,
            slide_id=str(slide["id"]),
            page_number=int(slide["page_number"]),
            title=str(slide["title"]),
            html_path=relative_path.as_posix(),
            instruction=instruction,
            metadata_json=json.dumps(
                {"html_size": len(html), "html_sha256": digest},
                ensure_ascii=False,
            ),
        )
        with SessionLocal() as db:
            db.add(version)
            db.commit()
            db.refresh(version)
            return self._to_dict(version)

    def list_versions(self, session_id: str, slide_id: str) -> list[dict]:
        session_id = safe_session_id(session_id)
        with SessionLocal() as db:
            versions = db.scalars(
                select(SlideVersion)
                .where(
                    SlideVersion.session_id == session_id,
                    SlideVersion.slide_id == slide_id,
                )
                .order_by(SlideVersion.created_at.desc())
            ).all()
            return [self._to_dict(version) for version in versions]

    def find_version_by_digest(self, session_id: str, slide_id: str, digest: str) -> dict | None:
        session_id = safe_session_id(session_id)
        with SessionLocal() as db:
            versions = db.scalars(
                select(SlideVersion).where(
                    SlideVersion.session_id == session_id,
                    SlideVersion.slide_id == slide_id,
                )
            ).all()
            for version in versions:
                metadata = self._metadata(version)
                if metadata.get("html_sha256") == digest:
                    return self._to_dict(version)
                if "html_sha256" not in metadata:
                    try:
                        version_html = self.read_version_html(self._to_dict(version))
                        if self.html_digest(version_html) == digest:
                            return self._to_dict(version)
                    except SessionNotFoundError:
                        continue
        return None

    def get_version(self, session_id: str, version_id: str) -> dict:
        session_id = safe_session_id(session_id)
        with SessionLocal() as db:
            version = db.get(SlideVersion, version_id)
            if not version or version.session_id != session_id:
                raise SlideVersionNotFoundError("Slide version not found")
            return self._to_dict(version)

    def read_version_html(self, version: dict) -> str:
        path = self.store.storage_root / version["html_path"]
        if not path.exists():
            raise SessionNotFoundError("Slide version file not found")
        return path.read_text(encoding="utf-8")

    @staticmethod
    def html_digest(html: str) -> str:
        return hashlib.sha256(html.encode("utf-8")).hexdigest()

    @staticmethod
    def _metadata(version: SlideVersion) -> dict:
        try:
            return json.loads(version.metadata_json or "{}")
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _to_dict(version: SlideVersion) -> dict:
        return {
            "id": version.id,
            "session_id": version.session_id,
            "slide_id": version.slide_id,
            "page_number": version.page_number,
            "title": version.title,
            "html_path": version.html_path,
            "instruction": version.instruction,
            "created_at": version.created_at.isoformat(),
        }


def get_slide_history_store() -> SlideHistoryStore:
    return SlideHistoryStore()
