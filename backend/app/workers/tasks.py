from app.services.export_runner import run_pptx_export_sync
from app.services.generation_runner import run_generation_sync
from app.workers.celery_app import celery_app


@celery_app.task(name="generation.run")
def run_generation_task(run_id: str) -> dict[str, str]:
    run_generation_sync(run_id)
    return {"run_id": run_id, "status": "completed"}


@celery_app.task(name="export.pptx")
def run_pptx_export_task(export_run_id: str) -> dict[str, str]:
    run_pptx_export_sync(export_run_id)
    return {"export_run_id": export_run_id, "status": "completed"}
