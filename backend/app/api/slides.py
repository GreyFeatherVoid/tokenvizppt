from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.core.settings import get_settings
from app.services.asset_store import AssetNotFoundError, get_asset_store
from app.services.deck_spec import (
    SlideSpecValidationError,
    insert_image_into_spec,
    patch_element_in_spec,
    render_slide_spec_html,
)
from app.services.editable_html import (
    EditableElementNotFoundError,
    delete_editable_element,
    insert_image_element,
    patch_editable_element,
    patch_image_element,
)
from app.services.llm_deck_generator import edit_slide_spec, place_asset_in_slide_spec
from app.services.session_store import SessionNotFoundError, get_session_store
from app.services.slide_editor import (
    edit_slide_html,
    get_slide_from_session,
    place_asset_in_slide_html,
)
from app.services.slide_history import (
    SlideVersionNotFoundError,
    get_slide_history_store,
)

router = APIRouter(prefix="/slides", tags=["slides"])
SPEC_EDIT_RETRIES = 3


class EditSlideRequest(BaseModel):
    instruction: str = Field(min_length=1, max_length=4000)


class PatchSlideElementRequest(BaseModel):
    element_id: str = Field(min_length=1, max_length=120)
    text: str | None = Field(default=None, max_length=4000)
    color: str | None = Field(default=None, max_length=80)
    font_family: str | None = Field(default=None, max_length=160)
    font_size: str | None = Field(default=None, max_length=80)
    font_weight: str | None = Field(default=None, max_length=80)
    left: str | None = Field(default=None, max_length=80)
    top: str | None = Field(default=None, max_length=80)
    width: str | None = Field(default=None, max_length=80)
    height: str | None = Field(default=None, max_length=80)
    opacity: str | None = Field(default=None, max_length=80)
    border_radius: str | None = Field(default=None, max_length=80)
    z_index: str | None = Field(default=None, max_length=80)
    delete: bool = False


class InsertImageRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)


class PlaceImageRequest(BaseModel):
    asset_id: str = Field(min_length=1, max_length=64)
    instruction: str = Field(min_length=1, max_length=2000)


class EditSlideResponse(BaseModel):
    session_id: str
    slide_id: str
    title: str
    html: str


class SlideVersionResponse(BaseModel):
    id: str
    session_id: str
    slide_id: str
    page_number: int
    title: str
    instruction: str
    created_at: str


class SlideHistoryResponse(BaseModel):
    versions: list[SlideVersionResponse]


@router.post("/{session_id}/{slide_id}/edit", response_model=EditSlideResponse)
async def edit_slide(
    session_id: str,
    slide_id: str,
    payload: EditSlideRequest,
) -> EditSlideResponse:
    store = get_session_store()
    try:
        session = store.get_session(session_id)
        slide = get_slide_from_session(session_id, slide_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        spec = None
        if slide.get("spec"):
            spec = await edit_slide_spec_with_retries(
                {
                    "topic": session["topic"],
                    "title": slide["title"],
                    "instruction": payload.instruction,
                    "current_spec": slide["spec"],
                }
            )
            html = render_slide_spec_html(spec)
        else:
            settings = get_settings()
            html = await edit_slide_html(
                {
                    "model": settings.llm_model,
                    "temperature": settings.llm_temperature,
                    "topic": session["topic"],
                    "title": slide["title"],
                    "instruction": payload.instruction,
                    "current_html": slide["html"],
                }
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Slide edit failed: {exc}") from exc

    get_slide_history_store().create_snapshot(session_id, slide, payload.instruction)
    updated = store.write_slide(
        session_id=session_id,
        page_number=int(slide["page_number"]),
        title=slide["title"],
        html=html,
        spec=spec,
    )
    slides = [
        updated if item.get("id") == slide_id else item
        for item in session.get("slides") or []
    ]
    store.update_session(session_id, {"slides": slides, "status": "completed"})
    return EditSlideResponse(
        session_id=session_id,
        slide_id=slide_id,
        title=updated["title"],
        html=updated["html"],
    )


@router.patch("/{session_id}/{slide_id}/elements", response_model=EditSlideResponse)
async def patch_slide_element(
    session_id: str,
    slide_id: str,
    payload: PatchSlideElementRequest,
) -> EditSlideResponse:
    store = get_session_store()
    try:
        session = store.get_session(session_id)
        slide = get_slide_from_session(session_id, slide_id)
        spec = None
        if slide.get("spec"):
            spec = patch_element_in_spec(
                slide["spec"],
                payload.element_id,
                text=payload.text,
                delete=payload.delete,
                styles={
                    "color": payload.color,
                    "font_family": payload.font_family,
                    "font_size": payload.font_size,
                    "font_weight": payload.font_weight,
                    "left": payload.left,
                    "top": payload.top,
                    "width": payload.width,
                    "height": payload.height,
                    "opacity": payload.opacity,
                    "border_radius": payload.border_radius,
                    "z_index": payload.z_index,
                },
            )
            html = render_slide_spec_html(spec)
        elif payload.delete:
            html = delete_editable_element(slide["html"], payload.element_id)
        elif payload.element_id.startswith("image-"):
            html = patch_image_element(
                slide["html"],
                payload.element_id,
                styles={
                    "left": payload.left,
                    "top": payload.top,
                    "width": payload.width,
                    "height": payload.height,
                    "opacity": payload.opacity,
                    "border_radius": payload.border_radius,
                    "z_index": payload.z_index,
                },
            )
        else:
            html = patch_editable_element(
                slide["html"],
                payload.element_id,
                text=payload.text,
                styles={
                    "color": payload.color,
                    "font_family": payload.font_family,
                    "font_size": payload.font_size,
                    "font_weight": payload.font_weight,
                },
            )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except EditableElementNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except SlideSpecValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    get_slide_history_store().create_snapshot(
        session_id,
        slide,
        f"{'Delete' if payload.delete else 'Manual edit'}: {payload.element_id}",
    )
    updated = store.write_slide(
        session_id=session_id,
        page_number=int(slide["page_number"]),
        title=slide["title"],
        html=html,
        spec=spec,
    )
    slides = [
        updated if item.get("id") == slide_id else item
        for item in session.get("slides") or []
    ]
    store.update_session(session_id, {"slides": slides, "status": "completed"})
    return EditSlideResponse(
        session_id=session_id,
        slide_id=slide_id,
        title=updated["title"],
        html=updated["html"],
    )


@router.post("/{session_id}/{slide_id}/images", response_model=EditSlideResponse)
async def insert_slide_image(
    session_id: str,
    slide_id: str,
    payload: InsertImageRequest,
) -> EditSlideResponse:
    store = get_session_store()
    try:
        session = store.get_session(session_id)
        slide = get_slide_from_session(session_id, slide_id)
        asset = get_asset_store().get_asset(session_id, payload.asset_id)
        spec = None
        if slide.get("spec"):
            spec = insert_image_into_spec(slide["spec"], asset)
            html = render_slide_spec_html(spec)
        else:
            html = insert_image_element(
                slide["html"],
                image_url=asset["url"],
                alt_text=asset["file_name"],
            )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    get_slide_history_store().create_snapshot(
        session_id,
        slide,
        f"Insert image: {asset['file_name']}",
    )
    updated = store.write_slide(
        session_id=session_id,
        page_number=int(slide["page_number"]),
        title=slide["title"],
        html=html,
        spec=spec,
    )
    slides = [
        updated if item.get("id") == slide_id else item
        for item in session.get("slides") or []
    ]
    store.update_session(session_id, {"slides": slides, "status": "completed"})
    return EditSlideResponse(
        session_id=session_id,
        slide_id=slide_id,
        title=updated["title"],
        html=updated["html"],
    )


@router.post("/{session_id}/{slide_id}/images/place", response_model=EditSlideResponse)
async def place_slide_image(
    session_id: str,
    slide_id: str,
    payload: PlaceImageRequest,
) -> EditSlideResponse:
    store = get_session_store()
    try:
        session = store.get_session(session_id)
        slide = get_slide_from_session(session_id, slide_id)
        asset = get_asset_store().get_asset(session_id, payload.asset_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except AssetNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    try:
        spec = None
        if slide.get("spec"):
            spec = await place_asset_in_slide_spec_with_retries(
                {
                    "topic": session["topic"],
                    "title": slide["title"],
                    "instruction": payload.instruction,
                    "image_url": asset["url"],
                    "image_name": asset["file_name"],
                    "current_spec": slide["spec"],
                }
            )
            html = render_slide_spec_html(spec)
        else:
            settings = get_settings()
            html = await place_asset_in_slide_html(
                {
                    "model": settings.llm_model,
                    "temperature": settings.llm_temperature,
                    "topic": session["topic"],
                    "title": slide["title"],
                    "instruction": payload.instruction,
                    "image_url": asset["url"],
                    "image_name": asset["file_name"],
                    "current_html": slide["html"],
                }
            )
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Image placement failed: {exc}") from exc

    get_slide_history_store().create_snapshot(
        session_id,
        slide,
        f"AI place image: {asset['file_name']}",
    )
    updated = store.write_slide(
        session_id=session_id,
        page_number=int(slide["page_number"]),
        title=slide["title"],
        html=html,
        spec=spec,
    )
    slides = [
        updated if item.get("id") == slide_id else item
        for item in session.get("slides") or []
    ]
    store.update_session(session_id, {"slides": slides, "status": "completed"})
    return EditSlideResponse(
        session_id=session_id,
        slide_id=slide_id,
        title=updated["title"],
        html=updated["html"],
    )


@router.get("/{session_id}/{slide_id}/history", response_model=SlideHistoryResponse)
async def list_slide_history(session_id: str, slide_id: str) -> SlideHistoryResponse:
    try:
        get_session_store().get_session(session_id)
        versions = get_slide_history_store().list_versions(session_id, slide_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SlideHistoryResponse(versions=versions)


@router.post(
    "/{session_id}/{slide_id}/rollback/{version_id}",
    response_model=EditSlideResponse,
)
async def rollback_slide(
    session_id: str,
    slide_id: str,
    version_id: str,
) -> EditSlideResponse:
    store = get_session_store()
    history_store = get_slide_history_store()
    try:
        session = store.get_session(session_id)
        current_slide = get_slide_from_session(session_id, slide_id)
        version = history_store.get_version(session_id, version_id)
        if version["slide_id"] != slide_id:
            raise SlideVersionNotFoundError("Slide version not found")
        html = history_store.read_version_html(version)
    except (SessionNotFoundError, SlideVersionNotFoundError) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if history_store.html_digest(current_slide["html"]) == history_store.html_digest(html):
        return EditSlideResponse(
            session_id=session_id,
            slide_id=slide_id,
            title=current_slide["title"],
            html=current_slide["html"],
        )

    history_store.create_snapshot(
        session_id,
        current_slide,
        f"Before rollback to version {version_id}",
    )
    updated = store.write_slide(
        session_id=session_id,
        page_number=int(current_slide["page_number"]),
        title=current_slide["title"],
        html=html,
    )
    slides = [
        updated if item.get("id") == slide_id else item
        for item in session.get("slides") or []
    ]
    store.update_session(session_id, {"slides": slides, "status": "completed"})
    return EditSlideResponse(
        session_id=session_id,
        slide_id=slide_id,
        title=updated["title"],
        html=updated["html"],
    )


async def edit_slide_spec_with_retries(args: dict) -> dict:
    previous_error: str | None = None
    for attempt in range(1, SPEC_EDIT_RETRIES + 1):
        try:
            return await edit_slide_spec(args, previous_error=previous_error)
        except Exception as exc:
            previous_error = f"Attempt {attempt} failed: {exc}"
    raise ValueError(f"SlideSpec edit failed after {SPEC_EDIT_RETRIES} attempts. {previous_error}")


async def place_asset_in_slide_spec_with_retries(args: dict) -> dict:
    previous_error: str | None = None
    for attempt in range(1, SPEC_EDIT_RETRIES + 1):
        try:
            return await place_asset_in_slide_spec(args, previous_error=previous_error)
        except Exception as exc:
            previous_error = f"Attempt {attempt} failed: {exc}"
    raise ValueError(
        f"SlideSpec image placement failed after {SPEC_EDIT_RETRIES} attempts. {previous_error}"
    )
