from celery import Celery

from app.core.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "tokenvizppt",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)
celery_app.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_default_queue="generation",
    task_routes={
        "generation.run": {"queue": "generation"},
        "export.pptx": {"queue": "export"},
    },
    worker_prefetch_multiplier=1,
)
