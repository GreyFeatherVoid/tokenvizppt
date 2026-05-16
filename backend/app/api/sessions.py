from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.services.db_session_repository import get_db_session_repository
from app.services.access_control import request_access, require_session_access, stamp_session_owner
from app.services.session_store import SessionNotFoundError, get_session_store

router = APIRouter(prefix="/sessions", tags=["sessions"])


class CreateSessionRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=240)
    brief: str = Field(min_length=1, max_length=8000)
    page_count: int = Field(default=5, ge=1, le=40)
    style_id: str = Field(default="default", min_length=1, max_length=120)
    style_prompt: str | None = Field(default=None, max_length=6000)
    enable_ai_images: bool = False
    output_language: str = Field(default="auto", pattern="^(auto|zh-CN|en-US)$")


class CreateSessionResponse(BaseModel):
    session_id: str
    status: str


class SlideResponse(BaseModel):
    id: str
    page_number: int
    title: str
    html: str
    spec: dict | None = None


class SessionResponse(BaseModel):
    id: str
    topic: str
    brief: str
    page_count: int
    style_id: str
    style_prompt: str | None = None
    enable_ai_images: bool = False
    output_language: str = "auto"
    status: str
    latest_run_id: str | None = None
    slides: list[SlideResponse] = []


class SessionSummaryResponse(BaseModel):
    id: str
    topic: str
    brief: str
    page_count: int
    style_id: str
    status: str
    latest_run_id: str | None = None
    slide_count: int = 0
    output_language: str = "auto"
    enable_ai_images: bool = False
    created_at: str
    updated_at: str


class SessionListResponse(BaseModel):
    sessions: list[SessionSummaryResponse]


class ActiveRunResponse(BaseModel):
    session_id: str
    run_id: str | None = None
    status: str | None = None


@router.get("", response_model=SessionListResponse)
def list_sessions(request: Request, limit: int = 30) -> SessionListResponse:
    sessions = get_db_session_repository().list_sessions(limit, access=request_access(request))
    return SessionListResponse(sessions=sessions)


@router.post("", response_model=CreateSessionResponse)
def create_session(payload: CreateSessionRequest, request: Request) -> CreateSessionResponse:
    store = get_session_store()
    session = store.create_session(stamp_session_owner(payload.model_dump(), request))
    return CreateSessionResponse(session_id=session["id"], status=session["status"])


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(session_id: str, request: Request) -> SessionResponse:
    require_session_access(session_id, request)
    try:
        session = get_db_session_repository().get_session_detail(session_id)
    except SessionNotFoundError:
        store = get_session_store()
        try:
            session = store.get_session(session_id)
        except SessionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SessionResponse(**session)


@router.get("/{session_id}/active-run", response_model=ActiveRunResponse)
def get_active_run(session_id: str, request: Request) -> ActiveRunResponse:
    store = get_session_store()
    try:
        session = require_session_access(session_id, request)
        run_id = session.get("latest_run_id")
        status = None
        if run_id:
            status = store.get_run(run_id).get("status")
        return ActiveRunResponse(session_id=session_id, run_id=run_id, status=status)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.delete("/{session_id}")
def delete_session(session_id: str, request: Request) -> dict[str, str]:
    repository = get_db_session_repository()
    store = get_session_store()
    try:
        require_session_access(session_id, request)
        repository.delete_session(session_id)
        store.delete_session_files(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"status": "deleted"}
