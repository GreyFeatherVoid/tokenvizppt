from fastapi import APIRouter
from pydantic import BaseModel

from app.services.style_presets import DEFAULT_STYLE_ID, list_style_presets, normalize_locale

router = APIRouter(prefix="/styles", tags=["styles"])


class StylePresetResponse(BaseModel):
    id: str
    label: str
    description: str
    visual_language: str
    prompt: str


class StylePresetListResponse(BaseModel):
    default_style_id: str
    styles: list[StylePresetResponse]


@router.get("", response_model=StylePresetListResponse)
def get_styles(locale: str = "en-US") -> StylePresetListResponse:
    return StylePresetListResponse(
        default_style_id=DEFAULT_STYLE_ID,
        styles=list_style_presets(normalize_locale(locale)),
    )
