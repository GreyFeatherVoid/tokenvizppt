from fastapi import APIRouter

from app.api import (
    admin,
    announcements,
    assets,
    auth,
    credits,
    exports,
    generation,
    health,
    invites,
    sessions,
    slides,
    styles,
)

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(announcements.router)
api_router.include_router(admin.router)
api_router.include_router(auth.router)
api_router.include_router(credits.router)
api_router.include_router(invites.router)
api_router.include_router(sessions.router)
api_router.include_router(generation.router)
api_router.include_router(slides.router)
api_router.include_router(assets.router)
api_router.include_router(exports.router)
api_router.include_router(styles.router)
