from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from app.services.pptx_exporter import get_export_file
from app.services.session_store import SessionNotFoundError, get_session_store
from app.workers.tasks import run_pptx_export_task

router = APIRouter(prefix="/exports", tags=["exports"])


class PptxExportResponse(BaseModel):
    session_id: str
    export_run_id: str
    status: str


class ExportRunResponse(BaseModel):
    export_run_id: str
    session_id: str
    status: str
    progress: int
    file_name: str | None = None
    url: str | None = None
    error: str | None = None


@router.post("/{session_id}/pptx", response_model=PptxExportResponse)
def export_pptx(session_id: str) -> PptxExportResponse:
    store = get_session_store()
    try:
        run = store.create_export_run(session_id, "pptx")
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run_pptx_export_task.delay(run["id"])
    return PptxExportResponse(
        session_id=session_id,
        export_run_id=run["id"],
        status=run["status"],
    )


@router.get("/runs/{export_run_id}", response_model=ExportRunResponse)
def get_export_run(export_run_id: str) -> ExportRunResponse:
    try:
        run = get_session_store().get_export_run(export_run_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return ExportRunResponse(
        export_run_id=run["id"],
        session_id=run["session_id"],
        status=run["status"],
        progress=int(run.get("progress") or 0),
        file_name=run.get("file_name"),
        url=run.get("url"),
        error=run.get("error"),
    )


@router.get("/{session_id}/{file_name}")
def download_export(session_id: str, file_name: str) -> FileResponse:
    try:
        path = get_export_file(session_id, file_name)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
        filename=file_name,
    )
