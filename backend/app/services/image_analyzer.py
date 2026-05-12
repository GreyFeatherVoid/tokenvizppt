import base64
import json
import mimetypes
from pathlib import Path
from typing import Any

from app.core.settings import get_settings
from app.services.asset_store import get_asset_store
from app.services.llm_deck_generator import create_client
from app.services.llm_slide_planner import extract_json_object, normalize_text


def image_to_data_url(path: Path) -> str:
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


async def analyze_image_asset(session_id: str, image: dict[str, Any]) -> dict[str, Any]:
    existing = image.get("vision")
    if isinstance(existing, dict) and existing.get("status") == "completed":
        return image

    store = get_asset_store()
    path = store.get_asset_file_path(str(image["id"]))
    analysis: dict[str, Any]
    try:
        analysis = await request_image_analysis(image, path)
    except Exception as exc:
        analysis = {
            "status": "failed",
            "analysis_error": normalize_text(str(exc), "Image analysis failed", 500),
        }
    return store.update_asset_analysis(session_id, str(image["id"]), analysis)


async def request_image_analysis(image: dict[str, Any], path: Path) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You analyze uploaded images for presentation generation. "
                        "Return only valid JSON. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": build_image_analysis_prompt(image)},
                        {
                            "type": "image_url",
                            "image_url": {"url": image_to_data_url(path)},
                        },
                    ],
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return normalize_image_analysis(json.loads(extract_json_object(content)))
    finally:
        await client.close()


def build_image_analysis_prompt(image: dict[str, Any]) -> str:
    required = "required" if image.get("required") else "optional"
    notes = str(image.get("notes") or "").strip() or "No user notes."
    return f"""
Analyze this uploaded image for use in a generated PowerPoint deck.

Image metadata:
- asset_id: {image.get("id")}
- file_name: {image.get("file_name")}
- usage: {required}
- user notes: {notes}

Return JSON with this exact shape:
{{
  "caption": "one concise description of what the image shows",
  "detected_type": "table|chart|screenshot|photo|illustration|diagram|document|other",
  "key_points": ["specific visual/content point", "specific visual/content point"],
  "ocr_text": "important readable text or empty string",
  "recommended_usage": "how this image should be used in a slide",
  "suggested_slide_roles": ["data-focus", "comparison", "image-focus"],
  "placement_guidance": "specific placement guidance for slide composition"
}}

Rules:
- Focus on information useful for choosing the right slide and layout.
- If this is a table/chart/screenshot, extract the important message, not every cell.
- If the image is decorative, say so clearly.
- Keep key_points to 3-6 items.
- suggested_slide_roles must use only: cover, data-focus, comparison, timeline, concept,
  process, summary, quote, image-focus.
""".strip()


def normalize_image_analysis(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        raise ValueError("Image analysis response is not an object")
    roles = data.get("suggested_slide_roles")
    if not isinstance(roles, list):
        roles = []
    key_points = data.get("key_points")
    if not isinstance(key_points, list):
        key_points = []
    return {
        "status": "completed",
        "caption": normalize_text(data.get("caption"), "Uploaded image", 400),
        "detected_type": normalize_detected_type(data.get("detected_type")),
        "key_points": [
            normalize_text(point, "", 220) for point in key_points[:6] if str(point).strip()
        ],
        "ocr_text": normalize_text(data.get("ocr_text"), "", 1500),
        "recommended_usage": normalize_text(data.get("recommended_usage"), "", 500),
        "suggested_slide_roles": [
            role for role in (normalize_slide_role(item) for item in roles[:5]) if role
        ],
        "placement_guidance": normalize_text(data.get("placement_guidance"), "", 500),
    }


def normalize_detected_type(value: object) -> str:
    allowed = {
        "table",
        "chart",
        "screenshot",
        "photo",
        "illustration",
        "diagram",
        "document",
        "other",
    }
    detected = str(value or "").strip().lower()
    return detected if detected in allowed else "other"


def normalize_slide_role(value: object) -> str:
    allowed = {
        "cover",
        "data-focus",
        "comparison",
        "timeline",
        "concept",
        "process",
        "summary",
        "quote",
        "image-focus",
    }
    role = str(value or "").strip().lower()
    return role if role in allowed else ""
