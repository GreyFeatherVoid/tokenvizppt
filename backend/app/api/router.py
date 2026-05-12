from fastapi import APIRouter

from app.api import assets, exports, generation, health, sessions, slides, styles

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(sessions.router)
api_router.include_router(generation.router)
api_router.include_router(slides.router)
api_router.include_router(assets.router)
api_router.include_router(exports.router)
api_router.include_router(styles.router)
