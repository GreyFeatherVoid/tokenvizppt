import asyncio
import json

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from app.services.session_store import SessionNotFoundError, get_session_store
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
def start_generation(payload: StartGenerationRequest) -> StartGenerationResponse:
    store = get_session_store()
    try:
        run = store.create_run(payload.session_id, payload.prompt)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    run_generation_task.delay(run["id"])
    return StartGenerationResponse(run_id=run["id"], status=run["status"])


@router.get("/{run_id}/state", response_model=GenerationStateResponse)
def get_generation_state(run_id: str) -> GenerationStateResponse:
    store = get_session_store()
    try:
        run = store.get_run(run_id)
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
async def stream_generation_events(run_id: str) -> EventSourceResponse:
    async def event_generator():
        store = get_session_store()
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

            await asyncio.sleep(0.75)

    return EventSourceResponse(event_generator())
