from fastapi import APIRouter
from pydantic import BaseModel

from app.db.session import SessionLocal
from app.models.admin import Announcement
from sqlalchemy import select

router = APIRouter(prefix="/announcements", tags=["announcements"])


class AnnouncementResponse(BaseModel):
    id: str
    title: str
    body: str
    status: str
    published_at: str | None = None
    created_at: str
    updated_at: str


class AnnouncementListResponse(BaseModel):
    announcements: list[AnnouncementResponse]


@router.get("", response_model=AnnouncementListResponse)
def list_public_announcements(limit: int = 5) -> AnnouncementListResponse:
    with SessionLocal() as db:
        rows = db.scalars(
            select(Announcement)
            .where(Announcement.status == "published")
            .order_by(Announcement.published_at.desc().nullslast(), Announcement.updated_at.desc())
            .limit(max(1, min(limit, 20)))
        ).all()
        return AnnouncementListResponse(
            announcements=[
                AnnouncementResponse(
                    id=row.id,
                    title=row.title,
                    body=row.body,
                    status=row.status,
                    published_at=row.published_at.isoformat() if row.published_at else None,
                    created_at=row.created_at.isoformat(),
                    updated_at=row.updated_at.isoformat(),
                )
                for row in rows
            ]
        )
