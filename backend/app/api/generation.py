import asyncio
import json

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.core.settings import get_settings
from app.services.access_control import require_session_access
from app.services.session_store import SessionNotFoundError, get_session_store
from app.services.usage_service import (
    UsageActiveGenerationLimitError,
    UsageCreditsInsufficientError,
    UsageQuotaExceededError,
    get_usage_service,
)
from app.workers.tasks import run_generation_task

router = APIRouter(prefix="/generation", tags=["generation"])


class StartGenerationRequest(BaseModel):
    session_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1, max_length=12000)


class StartGenerationResponse(BaseModel):
    run_id: str
    status: str


class GenerationStateResponse(BaseModel):
    run_id: str
    session_id: str
    status: str
    progress: int
    events: list[dict]
    error: str | None = None


@router.post("/start", response_model=StartGenerationResponse)
def start_generation(payload: StartGenerationRequest, request: Request) -> StartGenerationResponse:
    store = get_session_store()
    try:
        session = require_session_access(payload.session_id, request)
        usage_service = get_usage_service()
        user_id = usage_service.current_user_id(request.cookies.get(get_settings().auth_cookie_name))
        charge = usage_service.reserve_deck_generation(
            user_id=user_id,
            ip_address=request.client.host if request.client else None,
            session_id=payload.session_id,
            page_count=int(session.get("page_count") or 1),
        )
        run = store.create_run(
            payload.session_id,
            payload.prompt,
            metadata={
                "charge": {
                    "enabled": charge.enabled,
                    "user_id": charge.user_id,
                    "action": charge.action,
                    "amount": charge.amount,
                    "reference_type": charge.reference_type,
                    "reference_id": charge.reference_id,
                    "idempotency_key": charge.idempotency_key,
                    "anonymous": charge.anonymous,
                    "settled": charge.settled,
                }
            },
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except UsageQuotaExceededError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except UsageActiveGenerationLimitError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except UsageCreditsInsufficientError as exc:
        raise HTTPException(status_code=402, detail=str(exc)) from exc
    store.add_run_event(
        run["id"],
        {
            "progress": 1,
            "message": "Generation task queued",
            "type": "queued",
        },
    )
    run_generation_task.delay(run["id"])
    return StartGenerationResponse(run_id=run["id"], status=run["status"])


@router.get("/{run_id}/state", response_model=GenerationStateResponse)
def get_generation_state(run_id: str, request: Request) -> GenerationStateResponse:
    store = get_session_store()
    try:
        run = store.get_run(run_id)
        require_session_access(run["session_id"], request)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return GenerationStateResponse(
        run_id=run["id"],
        session_id=run["session_id"],
        status=run["status"],
        progress=int(run.get("progress") or 0),
        events=run.get("events") or [],
        error=run.get("error"),
    )


@router.get("/{run_id}/events")
async def stream_generation_events(run_id: str, request: Request) -> EventSourceResponse:
    store = get_session_store()
    try:
        run = store.get_run(run_id)
        require_session_access(run["session_id"], request)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    async def event_generator():
        last_index = 0
        while True:
            try:
                run = store.get_run(run_id)
            except SessionNotFoundError as exc:
                yield {
                    "event": "error",
                    "data": json.dumps({"run_id": run_id, "message": str(exc)}),
                }
                return

            events = run.get("events") or []
            for event in events[last_index:]:
                yield {
                    "event": "progress",
                    "data": json.dumps({"run_id": run_id, **event}),
                }
            last_index = len(events)

            if run.get("status") == "completed":
                yield {
                    "event": "complete",
                    "data": json.dumps({"run_id": run_id, "status": "completed"}),
                }
                return
            if run.get("status") == "failed":
                yield {
                    "event": "error",
                    "data": json.dumps(
                        {
                            "run_id": run_id,
                            "status": "failed",
                            "message": run.get("error") or "Generation failed",
                        }
                    ),
                }
                return
            if run.get("status") == "cancelled":
                yield {
                    "event": "cancelled",
                    "data": json.dumps(
                        {
                            "run_id": run_id,
                            "status": "cancelled",
                            "message": run.get("error") or "Generation cancelled",
                        }
                    ),
                }
                return

            await asyncio.sleep(0.75)

    return EventSourceResponse(event_generator())
