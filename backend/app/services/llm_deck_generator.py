import json
from typing import Any

from openai import AsyncOpenAI

from app.core.settings import get_settings
from app.services.deck_spec import normalize_slide_spec
from app.services.html_validation import extract_html_document, validate_slide_html
from app.services.llm_slide_planner import (
    extract_json_object,
    llm_is_configured,
    normalize_text,
)
from app.services.mock_slide_generator import render_slide_html
from app.services.style_presets import resolve_style_preset


class LLMDeckGeneratorUnavailableError(Exception):
    pass


def create_client() -> AsyncOpenAI:
    settings = get_settings()
    if not llm_is_configured():
        raise LLMDeckGeneratorUnavailableError("LLM is not configured")
    if settings.llm_provider.strip().lower() != "openai":
        raise LLMDeckGeneratorUnavailableError(
            f'Unsupported LLM provider "{settings.llm_provider}". Use openai-compatible.'
        )
    return AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url.strip() or None,
        timeout=settings.llm_timeout_seconds,
    )


async def generate_deck_outline(args: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        output_language = str(args.get("output_language") or "auto")
        style = resolve_style_preset(
            args.get("style_id"),
            args.get("style_prompt"),
            locale=output_language_to_locale(output_language),
        )
        page_count = int(args["page_count"])
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=min(1.0, settings.llm_temperature),
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation strategist and information architect. "
                        "Return only valid JSON. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": build_outline_prompt(
                        topic=str(args["topic"]),
                        brief=str(args["brief"]),
                        page_count=page_count,
                        style=style,
                        asset_context=args.get("asset_context"),
                        output_language=output_language,
                    ),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return parse_outline(content, args, style)
    finally:
        await client.close()


async def generate_slide_html(args: dict[str, Any]) -> str:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert HTML presentation designer. Return only one complete "
                        "HTML document. No markdown fences. No explanations."
                    ),
                },
                {"role": "user", "content": build_slide_html_prompt(args)},
            ],
        )
        html = extract_html_document(response.choices[0].message.content or "")
        valid, errors = validate_slide_html(html)
        if not valid:
            raise ValueError(f"Invalid slide HTML: {'; '.join(errors)}")
        return html
    finally:
        await client.close()


async def generate_slide_spec(
    args: dict[str, Any], previous_error: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation visual designer. Return only valid JSON "
                        "matching the SlideSpec schema. No markdown."
                    ),
                },
                {"role": "user", "content": build_slide_spec_prompt(args, previous_error)},
            ],
        )
        data = json.loads(extract_json_object(response.choices[0].message.content or ""))
        return normalize_slide_spec(data)
    finally:
        await client.close()


async def edit_slide_spec(
    args: dict[str, Any], previous_error: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation visual designer editing an existing "
                        "SlideSpec. Return only valid JSON matching the SlideSpec schema. "
                        "No markdown."
                    ),
                },
                {"role": "user", "content": build_edit_slide_spec_prompt(args, previous_error)},
            ],
        )
        data = json.loads(extract_json_object(response.choices[0].message.content or ""))
        return normalize_slide_spec(data)
    finally:
        await client.close()


async def place_asset_in_slide_spec(
    args: dict[str, Any], previous_error: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation visual designer integrating an uploaded "
                        "image into an existing SlideSpec. Return only valid JSON matching the "
                        "SlideSpec schema. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": build_place_asset_slide_spec_prompt(args, previous_error),
                },
            ],
        )
        data = json.loads(extract_json_object(response.choices[0].message.content or ""))
        return normalize_slide_spec(data)
    finally:
        await client.close()


async def place_required_image_in_deck(
    args: dict[str, Any], previous_error: str | None = None
) -> dict[str, Any]:
    settings = get_settings()
    client = create_client()
    try:
        response = await client.chat.completions.create(
            model=settings.llm_model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation visual designer fixing a generated deck. "
                        "Choose the best slide for one required uploaded image and return only "
                        "valid JSON. No markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": build_required_image_deck_placement_prompt(
                        args,
                        previous_error,
                    ),
                },
            ],
        )
        data = json.loads(extract_json_object(response.choices[0].message.content or ""))
        page_number = int(data.get("page_number") or 0)
        spec = normalize_slide_spec(data.get("spec") or {})
        return {
            "page_number": page_number,
            "reason": normalize_text(data.get("reason"), "", 500),
            "spec": spec,
        }
    finally:
        await client.close()


async def decide_slide_ai_image_need(args: dict[str, Any]) -> dict[str, Any]:
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
                        "You decide whether one presentation slide truly needs an AI-generated "
                        "image. Be conservative. Return only valid JSON. No markdown."
                    ),
                },
                {"role": "user", "content": build_ai_image_need_prompt(args)},
            ],
        )
        data = json.loads(extract_json_object(response.choices[0].message.content or ""))
        return normalize_ai_image_decision(data)
    finally:
        await client.close()


def build_outline_prompt(
    topic: str,
    brief: str,
    page_count: int,
    style: dict[str, str],
    asset_context: dict | None = None,
    output_language: str = "auto",
) -> str:
    asset_prompt = build_asset_context_prompt(asset_context)
    language_rule = build_output_language_rule(output_language)
    return f"""
Create a high-quality {page_count}-slide presentation blueprint.

Topic:
{topic}

User brief:
{brief}

Uploaded source material:
{asset_prompt}

Style preset:
- Name: {style["label"]}
- Description: {style["description"]}
- Visual language: {style["visual_language"]}
- Style skill prompt:
{style["prompt"]}

Return JSON with this exact shape:
{{
  "deck_title": "short title",
  "narrative": "one-sentence narrative arc",
  "design_contract": {{
    "theme": "visual theme",
    "palette": ["#hex", "#hex", "#hex", "#hex"],
    "typography": "font and type hierarchy direction",
    "layout_rules": ["rule", "rule", "rule"],
    "visual_motifs": ["motif", "motif"]
  }},
  "slides": [
    {{
      "title": "slide title",
      "role": "what this slide accomplishes",
      "main_message": "one sharp takeaway",
      "content": ["specific point", "specific point", "specific point"],
      "layout_intent": "visual layout direction"
    }}
  ]
}}

Rules:
- Return exactly {page_count} slides.
- {language_rule}
- Titles should be concise, hierarchical, and aligned with the narrative.
- The first slide is usually a cover; the last slide is usually a conclusion, summary, thank-you,
  or next-steps slide.
- Content points must be short phrases, not long paragraphs. Provide 1-5 points per slide.
- Keep each point compact and focused on one information type: data, structure, conclusion,
  comparison, decision, or action.
- Make each slide visually distinct but consistent.
- Prefer concrete, specific content over generic headings.
- layout_intent must be one of:
  cover, data-focus, comparison, timeline, concept, process, summary, quote, image-focus.
- Assign layout_intent based on the slide content type:
  cover = opening or section divider;
  data-focus = metrics, KPIs, trends, or quantitative evidence;
  comparison = 2+ options, alternatives, or before/after;
  timeline = phases, stages, roadmap, or historical progression;
  concept = ideas, frameworks, principles, or viewpoints;
  process = steps, flow, mechanism, or cause-and-effect;
  summary = conclusion, key takeaways, synthesis, thank-you, or next steps;
  quote = one statement as the main visual anchor;
  image-focus = products, scenes, people, or places where visuals dominate.
- Do not use placeholder text.
- If uploaded documents are provided, ground the outline in their content instead of inventing
  unsupported claims.
- If image assets are provided, use their vision analysis to decide whether they are evidence,
  decoration, screenshot, chart/table, or narrative material.
- If image assets are marked required, plan natural slide roles for them. Required images must
  be used semantically, not pasted as decoration.
""".strip()


def parse_outline(content: str, args: dict[str, Any], style: dict[str, str]) -> dict[str, Any]:
    data = json.loads(extract_json_object(content))
    page_count = int(args["page_count"])
    raw_contract = data.get("design_contract") if isinstance(data, dict) else {}
    raw_slides = data.get("slides") if isinstance(data, dict) else []
    if not isinstance(raw_contract, dict):
        raw_contract = {}
    if not isinstance(raw_slides, list):
        raise ValueError("Outline response does not contain slides")

    slides = []
    for index in range(page_count):
        raw = (
            raw_slides[index]
            if index < len(raw_slides) and isinstance(raw_slides[index], dict)
            else {}
        )
        content_points = raw.get("content")
        if not isinstance(content_points, list):
            content_points = []
        slides.append(
            {
                "title": normalize_text(raw.get("title"), f"Slide {index + 1}", 140),
                "role": normalize_text(raw.get("role"), "Advance the narrative", 240),
                "main_message": normalize_text(raw.get("main_message"), str(args["brief"]), 420),
                "content": [
                    normalize_text(point, "", 180)
                    for point in content_points[:5]
                    if str(point).strip()
                ],
                "layout_intent": normalize_text(
                    raw.get("layout_intent"),
                    "Create a clear editorial 16:9 slide with strong hierarchy.",
                    320,
                ),
            }
        )

    return {
        "deck_title": normalize_text(data.get("deck_title"), str(args["topic"]), 160),
        "narrative": normalize_text(data.get("narrative"), str(args["brief"]), 500),
        "style": style,
        "design_contract": {
            "theme": normalize_text(raw_contract.get("theme"), style["label"], 180),
            "palette": parse_palette(raw_contract.get("palette")),
            "typography": normalize_text(
                raw_contract.get("typography"),
                "Editorial serif headlines with clean sans-serif supporting text.",
                240,
            ),
            "layout_rules": parse_string_list(raw_contract.get("layout_rules"), 4),
            "visual_motifs": parse_string_list(raw_contract.get("visual_motifs"), 4)
            or [style["visual_language"], style["prompt"]],
        },
        "slides": slides,
    }


def parse_palette(value: object) -> list[str]:
    if isinstance(value, list):
        colors = [str(item).strip() for item in value if str(item).strip().startswith("#")]
        if len(colors) >= 3:
            return colors[:6]
    return ["#f6eddd", "#243426", "#b45c30", "#6f7a5f", "#fff9ec"]


def parse_string_list(value: object, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []
    return [normalize_text(item, "", 180) for item in value[:limit] if str(item).strip()]


def normalize_ai_image_decision(data: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(data, dict):
        return {"decision": "skip", "reason": "Invalid decision response"}
    decision = str(data.get("decision") or "skip").strip().lower()
    if decision != "generate":
        return {
            "decision": "skip",
            "reason": normalize_text(data.get("reason"), "No AI image needed", 300),
        }
    prompt = normalize_text(data.get("prompt"), "", 1200)
    visual_purpose = normalize_text(data.get("visual_purpose"), "", 300)
    placement_guidance = normalize_text(data.get("placement_guidance"), "", 400)
    if not prompt or not visual_purpose or not placement_guidance:
        return {
            "decision": "skip",
            "reason": "Image brief was incomplete",
        }
    return {
        "decision": "generate",
        "reason": normalize_text(data.get("reason"), "", 400),
        "visual_purpose": visual_purpose,
        "prompt": prompt,
        "size": normalize_ai_image_size(data.get("size")),
        "placement_guidance": placement_guidance,
    }


def normalize_ai_image_size(value: object) -> str:
    allowed = {"1024x1024", "1536x1024", "1024x1536", "2048x2048", "2560x1440"}
    size = str(value or "").strip()
    return size if size in allowed else get_settings().ai_image_default_size


def build_ai_image_need_prompt(args: dict[str, Any]) -> str:
    outline = args["outline"]
    slide = args["slide"]
    page_number = int(args["page_number"])
    total_pages = int(args["total_pages"])
    points = "\n".join(f"- {point}" for point in slide.get("content") or [])
    asset_context = build_asset_context_prompt(args.get("asset_context"))
    contract = outline["design_contract"]
    language_rule = build_output_language_rule(str(args.get("output_language") or "auto"))
    return f"""
Decide whether this specific slide genuinely needs a newly generated AI image before SlideSpec
generation.

Deck title: {outline["deck_title"]}
Narrative arc: {outline["narrative"]}
Slide {page_number}/{total_pages}
Slide title: {slide["title"]}
Slide role: {slide["role"]}
Main message: {slide["main_message"]}
Content points:
{points}
Layout intent: {slide["layout_intent"]}

Existing uploaded/generated assets:
{asset_context}

Design contract:
- Theme: {contract["theme"]}
- Typography: {contract["typography"]}
- Visual motifs: {"; ".join(contract["visual_motifs"])}

Return only JSON:
{{
  "decision": "skip|generate",
  "reason": "short reason",
  "visual_purpose": "only when decision is generate",
  "prompt": "only when decision is generate",
  "size": "1536x1024",
  "placement_guidance": "only when decision is generate"
}}

Rules:
- {language_rule}
- Be conservative. If text, shapes, or uploaded assets are enough, return skip.
- Generate only for cover, concept, scenario, process, mood, metaphor, or section-divider slides.
- Do not generate images for data evidence, screenshots, tables, charts, uploaded evidence,
  financial/legal/medical claims, real people, logos, copyrighted characters, or factual proof.
- Do not duplicate a required uploaded image.
- The prompt must describe a presentation-safe original visual, not a generic stock photo.
- The prompt should match the deck language, style, palette, and slide message.
- Prefer wide 16:9-friendly images, usually 1536x1024.
""".strip()


def build_slide_spec_prompt(args: dict[str, Any], previous_error: str | None = None) -> str:
    outline = args["outline"]
    contract = outline["design_contract"]
    slide = args["slide"]
    page_number = int(args["page_number"])
    total_pages = int(args["total_pages"])
    points = "\n".join(f"- {point}" for point in slide["content"])
    asset_context = build_asset_context_prompt(args.get("asset_context"))
    language_rule = build_output_language_rule(str(args.get("output_language") or "auto"))
    retry_note = (
        f"\nPrevious invalid response error:\n{previous_error}\nFix it in the new JSON."
        if previous_error
        else ""
    )
    palette = ", ".join(contract["palette"])
    return f"""
Generate a polished editable PowerPoint slide as structured JSON.

Deck title: {outline["deck_title"]}
Narrative arc: {outline["narrative"]}
Slide {page_number}/{total_pages}
Slide title: {slide["title"]}
Slide role: {slide["role"]}
Main message: {slide["main_message"]}
Content points:
{points}
Layout intent: {slide["layout_intent"]}

Uploaded source material and image constraints:
{asset_context}

Design contract:
- Theme: {contract["theme"]}
- Palette: {palette}
- Typography: {contract["typography"]}
- Layout rules: {"; ".join(contract["layout_rules"])}
- Visual motifs: {"; ".join(contract["visual_motifs"])}

Return only JSON with this exact shape:
{{
  "version": 1,
  "title": "slide title",
  "layoutIntent": "cover|data-focus|comparison|timeline|concept|process|summary|quote|image-focus",
  "size": {{"width": 13.333, "height": 7.5}},
  "background": "#F6EFE4",
  "palette": {{
    "background": "#F6EFE4",
    "ink": "#26324A",
    "accent": "#B77A3B",
    "muted": "#5F6E63",
    "surface": "#FFFDF8",
    "card": "#FBF8F2",
    "line": "#D5C7B8",
    "wash": "#E8EEE5",
    "soft_accent": "#F1DDC7"
  }},
  "elements": [
    {{"id":"title","kind":"text","x":0.7,"y":0.8,"w":7.5,"h":0.8,"text":"...","fontSize":28,"fontFace":"Georgia","color":"#26324A","bold":true,"lineHeight":1.12}},
    {{"id":"panel","kind":"shape","x":0.7,"y":2.0,"w":5.0,"h":3.0,"fill":"#FFFDF8","border":"#D5C7B8","radius":0.12}}
  ]
}}

Coordinate system:
- Slide size is 13.333 x 7.5 inches.
- x/y/w/h are inches.
- Keep every element inside the slide bounds.
- Leave at least 0.35 inch outer safe margin except intentional background shapes.
- Use 8-26 elements total. Prefer 3-8 meaningful text elements.
- Avoid text overlap. Separate text boxes vertically and horizontally.
- Do not place dense text in the bottom 0.45 inch.

Visual quality rules:
- {language_rule}
- Make the slide look designed, not like a generic form.
- Use asymmetry, large focal areas, accent bands, cards, or side panels when appropriate.
- Vary layout by layoutIntent. Do not repeat the same grid on every slide.
- Keep text concise. One text element should usually be under 160 characters.
- Use only fontFace values: Aptos, Calibri, Arial, Georgia.
- Use only 6-digit hex colors.
- Shape elements cannot contain text; text elements are separate.
- Image elements are allowed only when using an uploaded asset URL from the provided image list.
- Only use an image when its vision analysis or user notes match this slide's message and layout.
- When using an uploaded image, place it intentionally with surrounding text adjusted around it.
- Do not create arrows, bullets, icons, lines, dividers, or ornaments as text elements. Use shape
  elements for decoration, or omit the decoration.
- Do not overlap text boxes, including small labels, years, arrows, icons, and page markers.
- If an image has source=ai_generated, it was generated specifically for this slide. Use it as a
  visual anchor exactly once unless it directly conflicts with the slide message.
- Required uploaded images must appear in at least one slide across the deck. Use the image's
  caption, OCR, key points, recommended usage, and placement guidance to choose the right slide.
- Do not place images as generic decoration or as an afterthought.
{retry_note}
""".strip()


def output_language_to_locale(output_language: str) -> str:
    return "zh-CN" if output_language == "zh-CN" else "en-US"


def build_output_language_rule(output_language: str) -> str:
    if output_language == "zh-CN":
        return "Write all user-facing slide content in Simplified Chinese."
    if output_language == "en-US":
        return "Write all user-facing slide content in English."
    return (
        "Match the language of the topic and brief. "
        "Do not infer output language from this prompt."
    )


def build_asset_context_prompt(asset_context: dict | None) -> str:
    if not asset_context:
        return "No uploaded source material."
    documents = asset_context.get("documents") or []
    images = asset_context.get("images") or []
    sections: list[str] = []
    if documents:
        sections.append("Documents:")
        for doc in documents[:8]:
            text = str(doc.get("text") or "").strip()
            if not text:
                continue
            sections.append(
                f"- {doc.get('file_name')} ({doc.get('text_char_count', len(text))} chars):\n"
                f"{text[:3500]}"
            )
    if images:
        sections.append("Images:")
        for image in images[:20]:
            required = "required" if image.get("required") else "optional"
            source = str(image.get("source") or "uploaded")
            notes = str(image.get("notes") or "").strip() or "No user notes."
            ai_image = image.get("ai_image") if isinstance(image.get("ai_image"), dict) else {}
            ai_details = ""
            if source == "ai_generated":
                ai_details = (
                    f"\n  source: ai_generated"
                    f"\n  target_page: {ai_image.get('target_page') or 'unknown'}"
                    f"\n  visual_purpose: {ai_image.get('visual_purpose') or 'none'}"
                    f"\n  placement_guidance_from_generation: "
                    f"{ai_image.get('placement_guidance') or 'none'}"
                    f"\n  generation_reason: {ai_image.get('reason') or 'none'}"
                )
            vision = image.get("vision") if isinstance(image.get("vision"), dict) else {}
            if vision.get("status") == "completed":
                key_points = "; ".join(str(point) for point in (vision.get("key_points") or []))
                roles = ", ".join(str(role) for role in (vision.get("suggested_slide_roles") or []))
                sections.append(
                    f"- asset_id={image.get('id')}, url={image.get('url')}, "
                    f"name={image.get('file_name')}, usage={required}, source={source}, "
                    f"notes={notes}{ai_details}\n"
                    f"  vision_caption: {vision.get('caption') or ''}\n"
                    f"  detected_type: {vision.get('detected_type') or 'other'}\n"
                    f"  key_points: {key_points or 'none'}\n"
                    f"  ocr_text: {str(vision.get('ocr_text') or '')[:1200] or 'none'}\n"
                    f"  recommended_usage: {vision.get('recommended_usage') or 'none'}\n"
                    f"  suggested_slide_roles: {roles or 'none'}\n"
                    f"  placement_guidance: {vision.get('placement_guidance') or 'none'}"
                )
            else:
                error = str(vision.get("analysis_error") or "").strip()
                sections.append(
                    f"- asset_id={image.get('id')}, url={image.get('url')}, "
                    f"name={image.get('file_name')}, usage={required}, source={source}, "
                    f"notes={notes}{ai_details}, "
                    f"vision_status={vision.get('status') or 'not_analyzed'}, "
                    f"analysis_error={error or 'none'}"
                )
    return "\n".join(sections) if sections else "No uploaded source material."


def build_edit_slide_spec_prompt(args: dict[str, Any], previous_error: str | None = None) -> str:
    retry_note = (
        f"\nPrevious invalid response error:\n{previous_error}\nFix it in the new JSON."
        if previous_error
        else ""
    )
    return f"""
Edit this PowerPoint slide by returning a complete updated SlideSpec JSON.

Deck topic:
{args["topic"]}

Slide title:
{args["title"]}

User instruction:
{args["instruction"]}

Current SlideSpec:
{json.dumps(args["current_spec"], ensure_ascii=False)}

Hard requirements:
- Return the full updated SlideSpec object, not a diff.
- Preserve the SlideSpec schema: version, title, layoutIntent, size, background, palette, elements.
- Keep coordinates in inches for a 13.333 x 7.5 slide.
- Preserve existing element ids when the element still represents the same content.
- Keep every element inside bounds and avoid text overlap.
- Keep text concise; summarize instead of shrinking into unreadable boxes.
- Preserve existing uploaded image src values unless the user explicitly asks to remove them.
- Do not invent image URLs. New image elements are not allowed in this edit path.
- Use only fontFace values: Aptos, Calibri, Arial, Georgia.
- Use only 6-digit hex colors.
{retry_note}
""".strip()


def build_place_asset_slide_spec_prompt(
    args: dict[str, Any], previous_error: str | None = None
) -> str:
    retry_note = (
        f"\nPrevious invalid response error:\n{previous_error}\nFix it in the new JSON."
        if previous_error
        else ""
    )
    return f"""
Integrate one uploaded image into this PowerPoint slide by returning a complete updated
SlideSpec JSON.

Deck topic:
{args["topic"]}

Slide title:
{args["title"]}

Uploaded image:
- URL: {args["image_url"]}
- Name: {args["image_name"]}

User placement instruction:
{args["instruction"]}

Current SlideSpec:
{json.dumps(args["current_spec"], ensure_ascii=False)}

Hard requirements:
- Return the full updated SlideSpec object, not a diff.
- Add or update exactly one image element using src "{args["image_url"]}".
- The image element id must start with "image-".
- Do not invent or reference any other image URL.
- Re-layout text and shapes as needed so the image feels intentional, not pasted on top.
- Keep every element inside the 13.333 x 7.5 slide bounds.
- Avoid text overlap and avoid dense text in the bottom 0.45 inch.
- Preserve existing element ids when the element still represents the same content.
- Use only fontFace values: Aptos, Calibri, Arial, Georgia.
- Use only 6-digit hex colors.
{retry_note}
""".strip()


def build_required_image_deck_placement_prompt(
    args: dict[str, Any],
    previous_error: str | None = None,
) -> str:
    image = args["image"]
    vision = image.get("vision") if isinstance(image.get("vision"), dict) else {}
    key_points = "; ".join(str(point) for point in (vision.get("key_points") or [])) or "none"
    suggested_roles = (
        ", ".join(str(role) for role in (vision.get("suggested_slide_roles") or [])) or "none"
    )
    slides = [
        {
            "page_number": slide.get("page_number"),
            "title": slide.get("title"),
            "spec": slide.get("spec"),
        }
        for slide in args.get("slides", [])
        if slide.get("spec")
    ]
    retry_note = (
        f"\nPrevious invalid response error:\n{previous_error}\nFix it in the new JSON."
        if previous_error
        else ""
    )
    return f"""
One required uploaded image was not used in the generated deck. Choose the single best slide
for this image and return that slide as a complete updated SlideSpec.

Deck topic:
{args["topic"]}

Deck brief:
{args["brief"]}

Required image:
- asset_id: {image.get("id")}
- exact URL to use as image src: {image.get("url")}
- file name: {image.get("file_name")}
- user notes: {image.get("notes") or "No user notes."}
- vision caption: {vision.get("caption") or "No caption available."}
- detected type: {vision.get("detected_type") or "other"}
- key points: {key_points}
- OCR text: {str(vision.get("ocr_text") or "")[:1500] or "none"}
- recommended usage: {vision.get("recommended_usage") or "none"}
- suggested slide roles: {suggested_roles}
- placement guidance: {vision.get("placement_guidance") or "none"}

Current generated slides:
{json.dumps(slides, ensure_ascii=False)}

Return only JSON with this exact shape:
{{
  "page_number": 2,
  "reason": "why this slide is the best semantic fit",
  "spec": {{
    "version": 1,
    "title": "...",
    "layoutIntent": "...",
    "size": {{"width": 13.333, "height": 7.5}},
    "background": "#FFFFFF",
    "palette": {{}},
    "elements": []
  }}
}}

Hard requirements:
- Choose exactly one existing page_number from the current slides.
- Return the full updated SlideSpec for that chosen slide, not a diff.
- Add exactly one image element with src "{image.get("url")}".
- Do not invent or reference any other image URL.
- Re-layout text and shapes so the image is semantically integrated, not pasted on top.
- If the image contains table/chart/screenshot information, include a concise textual takeaway.
- Keep every element inside the 13.333 x 7.5 slide bounds.
- Avoid text overlap and avoid dense text in the bottom 0.45 inch.
- Preserve the slide's core message and visual quality.
- Use only fontFace values: Aptos, Calibri, Arial, Georgia.
- Use only 6-digit hex colors.
{retry_note}
""".strip()


def build_slide_html_prompt(args: dict[str, Any]) -> str:
    outline = args["outline"]
    contract = outline["design_contract"]
    slide = args["slide"]
    page_number = int(args["page_number"])
    total_pages = int(args["total_pages"])
    palette = ", ".join(contract["palette"])
    points = "\n".join(f"- {point}" for point in slide["content"])
    return f"""
Generate one complete standalone HTML document for a 16:9 presentation slide.

Deck title: {outline["deck_title"]}
Narrative arc: {outline["narrative"]}
Slide {page_number}/{total_pages}
Slide title: {slide["title"]}
Slide role: {slide["role"]}
Main message: {slide["main_message"]}
Content points:
{points}
Layout intent: {slide["layout_intent"]}

Design contract:
- Theme: {contract["theme"]}
- Palette: {palette}
- Typography: {contract["typography"]}
- Layout rules: {"; ".join(contract["layout_rules"])}
- Visual motifs: {"; ".join(contract["visual_motifs"])}

Hard requirements:
- Return only HTML, no markdown, no commentary.
- Include <!doctype html>, <html>, <head>, <style>, and <body>.
- Use one 16:9 slide canvas centered in the viewport.
- Use inline CSS only.
- Do not use JavaScript, external CSS, external images, external fonts, iframe, object, or embed.
- Make the slide visually polished, not a generic card.
- Use purposeful typography, spacing, color blocks, and visual hierarchy.
- Keep all content readable inside the slide.
- Avoid text overlap, clipped text, and dense bottom strips. If content is long, summarize harder
  instead of shrinking everything.
- Prefer CSS grid/flex layouts with clear spacing over fragile absolute positioning.
- Keep every text block within its own visual container with enough line-height and padding.
- Avoid placing many small text boxes along the bottom edge; they are prone to overlap when exported
  to editable PPTX.
- Do not use tiny font sizes to fit content. Reduce copy and keep no more than 3 dense content
  regions per slide.
- Leave extra breathing room around text because PowerPoint font metrics differ from browser
  metrics.
- Add a small page number marker.
- Add data-edit-id attributes to meaningful editable text elements when practical.
""".strip()


def render_fallback_slide(args: dict[str, Any]) -> str:
    slide = args["slide"]
    return render_slide_html(
        {
            "page_number": args["page_number"],
            "total_pages": args["total_pages"],
            "topic": args["topic"],
            "title": slide["title"],
            "summary": slide["main_message"],
            "detail": " ".join(slide.get("content") or [slide["role"]]),
        }
    )
