from fastapi import APIRouter

from app.core.settings import get_settings
from app.services.db_mirror import get_db_mirror

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict[str, str]:
    settings = get_settings()
    return {
        "status": "ok",
        "app": settings.app_name,
        "env": settings.app_env,
    }


@router.get("/health/db")
def database_health_check() -> dict[str, object]:
    counts = get_db_mirror().counts()
    return {
        "status": "ok",
        "counts": counts,
    }
