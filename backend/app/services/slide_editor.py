from typing import Any

from app.services.html_validation import extract_html_document, validate_slide_html
from app.services.llm_deck_generator import create_client
from app.services.session_store import SessionNotFoundError, get_session_store


async def edit_slide_html(args: dict[str, Any]) -> str:
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=args["model"],
            temperature=args["temperature"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert HTML slide editor. Return only one complete corrected "
                        "HTML document. No markdown fences. No explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": build_edit_prompt(
                        topic=args["topic"],
                        title=args["title"],
                        instruction=args["instruction"],
                        current_html=args["current_html"],
                    ),
                },
            ],
        )
        html = extract_html_document(response.choices[0].message.content or "")
        valid, errors = validate_slide_html(html)
        if not valid:
            raise ValueError(f"Invalid edited slide HTML: {'; '.join(errors)}")
        return html
    finally:
        await client.close()


async def place_asset_in_slide_html(args: dict[str, Any]) -> str:
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=args["model"],
            temperature=args["temperature"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert HTML presentation designer. Integrate the provided "
                        "uploaded image into the current slide with strong layout judgement. "
                        "Return only one complete corrected HTML document. No markdown fences. "
                        "No explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": build_asset_placement_prompt(
                        topic=args["topic"],
                        title=args["title"],
                        instruction=args["instruction"],
                        image_url=args["image_url"],
                        image_name=args["image_name"],
                        current_html=args["current_html"],
                    ),
                },
            ],
        )
        html = extract_html_document(response.choices[0].message.content or "")
        valid, errors = validate_slide_html(html)
        if not valid:
            raise ValueError(f"Invalid asset placement HTML: {'; '.join(errors)}")
        return html
    finally:
        await client.close()


def build_edit_prompt(topic: str, title: str, instruction: str, current_html: str) -> str:
    return f"""
Edit this generated presentation slide.

Deck topic:
{topic}

Slide title:
{title}

User instruction:
{instruction}

Current HTML:
{current_html}

Hard requirements:
- Return the full updated HTML document, not a diff.
- Preserve a standalone <!doctype html> document.
- Preserve existing data-edit-id attributes on edited text elements when practical.
- Keep the slide 16:9.
- Keep inline CSS only.
- Do not add JavaScript, external CSS, external images, iframe, object, or embed.
- Keep content readable and inside the slide bounds.
- Avoid overlapping text, clipped text, and dense bottom strips. Summarize or reduce content if
  necessary.
- Prefer grid/flex layout and adequate line-height/padding over fragile absolute positioning.
- Avoid tiny bottom labels or dense multi-column captions; they often overlap in editable PPTX
  export.
- Leave extra breathing room around text because PowerPoint font metrics differ from browser
  metrics.
- Apply the user's instruction directly and preserve unrelated design quality.
""".strip()


def build_asset_placement_prompt(
    topic: str,
    title: str,
    instruction: str,
    image_url: str,
    image_name: str,
    current_html: str,
) -> str:
    return f"""
Integrate one uploaded image into this generated presentation slide.

Deck topic:
{topic}

Slide title:
{title}

Uploaded image:
- URL: {image_url}
- Name: {image_name}

User placement instruction:
{instruction}

Current HTML:
{current_html}

Hard requirements:
- Return the full updated HTML document, not a diff.
- Preserve a standalone <!doctype html> document.
- Use the uploaded image exactly as <img src="{image_url}" ...>.
- Do not invent or reference any other image URL.
- Give the image a data-edit-id starting with "image-".
- Keep inline CSS only.
- Do not add JavaScript, external CSS, external fonts, iframe, object, embed, or link tags.
- Re-layout the slide if needed so the image feels intentional, not pasted on top.
- Keep all content readable inside the 16:9 slide bounds.
- Avoid overlapping text, clipped text, and dense bottom strips.
- Preserve existing data-edit-id attributes on edited text elements when practical.
""".strip()


def get_slide_from_session(session_id: str, slide_id: str) -> dict:
    session = get_session_store().get_session(session_id)
    for slide in session.get("slides") or []:
        if slide.get("id") == slide_id:
            return slide
    raise SessionNotFoundError("Slide not found")
