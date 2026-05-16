from typing import Annotated

from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.services.asset_store import (
    AssetNotFoundError,
    AssetValidationError,
    get_asset_store,
)
from app.services.access_control import require_session_access
from app.services.session_store import SessionNotFoundError

router = APIRouter(prefix="/assets", tags=["assets"])


class AssetResponse(BaseModel):
    id: str
    session_id: str
    file_name: str
    mime_type: str
    file_size: int
    kind: str
    source: str = "uploaded"
    notes: str = ""
    required: bool = False
    text: str = ""
    text_char_count: int = 0
    ai_image: dict = {}
    url: str
    created_at: str


class AssetListResponse(BaseModel):
    assets: list[AssetResponse]


class UpdateAssetRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=1200)
    required: bool | None = None


@router.get("/{session_id}", response_model=AssetListResponse)
def list_assets(session_id: str, request: Request) -> AssetListResponse:
    try:
        require_session_access(session_id, request)
        assets = get_asset_store().list_assets(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AssetListResponse(assets=assets)


@router.post("/{session_id}", response_model=AssetResponse)
async def upload_asset(
    session_id: str,
    request: Request,
    file: Annotated[UploadFile, File()],
) -> AssetResponse:
    try:
        require_session_access(session_id, request)
        asset = await get_asset_store().save_upload(session_id, file)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssetValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AssetResponse(**asset)


@router.patch("/{session_id}/{asset_id}", response_model=AssetResponse)
def update_asset(
    session_id: str,
    asset_id: str,
    payload: UpdateAssetRequest,
    request: Request,
) -> AssetResponse:
    try:
        require_session_access(session_id, request)
        asset = get_asset_store().update_asset_metadata(
            session_id,
            asset_id,
            notes=payload.notes,
            required=payload.required,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return AssetResponse(**asset)


@router.get("/{asset_id}/file")
def get_asset_file(asset_id: str, request: Request) -> FileResponse:
    try:
        asset = get_asset_store().get_asset_by_id(asset_id)
        require_session_access(asset["session_id"], request)
        path = get_asset_store().get_asset_file_path(asset_id)
    except (AssetNotFoundError, SessionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(path)
