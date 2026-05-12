import asyncio

from app.core.settings import get_settings
from app.services.ai_image_generator import (
    AIImageGenerationUnavailableError,
    ai_image_is_configured,
    generate_ai_image,
)
from app.services.asset_store import get_asset_store
from app.services.deck_spec import build_slide_spec, render_slide_spec_html
from app.services.image_analyzer import analyze_image_asset
from app.services.llm_deck_generator import (
    LLMDeckGeneratorUnavailableError,
    decide_slide_ai_image_need,
    generate_deck_outline,
    generate_slide_spec,
    place_required_image_in_deck,
)
from app.services.mock_slide_generator import build_slide_plan
from app.services.session_store import get_session_store
from app.services.style_presets import resolve_style_preset


async def run_generation(run_id: str) -> None:
    store = get_session_store()
    run = store.get_run(run_id)
    session = store.get_session(run["session_id"])
    asset_store = get_asset_store()

    try:
        store.update_run(run_id, {"status": "running"})
        asset_context = asset_store.build_generation_context(session["id"])
        analyzed_count = await analyze_generation_images(
            session_id=session["id"],
            asset_context=asset_context,
            run_id=run_id,
        )
        if analyzed_count:
            asset_context = asset_store.build_generation_context(session["id"])

        store.add_run_event(
            run_id,
            {
                "progress": 5,
                "message": "Preparing generation workspace",
                "type": "stage",
            },
        )

        store.add_run_event(
            run_id,
            {
                "progress": 12,
                "message": "Planning slide structure with backend LLM configuration",
                "type": "stage",
            },
        )

        outline, planner_message = await build_outline(session, asset_context)
        store.add_run_event(
            run_id,
            {
                "progress": 20,
                "message": planner_message,
                "type": "stage",
            },
        )

        total = max(1, len(outline["slides"]))
        concurrency = min(get_settings().generation_slide_concurrency, total)
        store.add_run_event(
            run_id,
            {
                "progress": 22,
                "message": f"Generating slides with concurrency {concurrency}",
                "type": "stage",
            },
        )
        ai_image_plan = await plan_ai_images_for_slides(
            session=session,
            outline=outline,
            total=total,
            asset_context=asset_context,
            run_id=run_id,
        )
        slide_payloads = await build_slides_from_specs_concurrently(
            session=session,
            outline=outline,
            total=total,
            asset_context=asset_context,
            concurrency=concurrency,
            ai_image_plan=ai_image_plan,
        )

        slides = []
        for index, payload in enumerate(slide_payloads, start=1):
            item = payload["item"]
            slide = store.write_slide(
                session["id"],
                index,
                item["title"],
                payload["html"],
                spec=payload["spec"],
            )
            slides.append(slide)
            progress = 20 + round((index / total) * 65)
            store.add_run_event(
                run_id,
                {
                    "progress": progress,
                    "message": payload["message"],
                    "type": "slide_generated",
                    "slide_id": slide["id"],
                },
            )

        slides = await retry_missing_required_images(
            session=session,
            slides=slides,
            asset_context=asset_context,
            run_id=run_id,
        )
        validate_required_images_used(slides, asset_context)
        store.add_run_event(
            run_id,
            {
                "progress": 94,
                "message": "Validated generated HTML slides",
                "type": "stage",
            },
        )

        store.update_session(session["id"], {"status": "completed", "slides": slides})
        store.update_run(run_id, {"status": "completed", "progress": 100})
        store.add_run_event(
            run_id,
            {
                "progress": 100,
                "message": "Generation complete",
                "type": "completed",
            },
        )
    except Exception as exc:
        store.update_run(run_id, {"status": "failed", "error": str(exc)})
        store.update_session(session["id"], {"status": "failed"})
        store.add_run_event(
            run_id,
            {
                "progress": 100,
                "message": f"Generation failed: {exc}",
                "type": "failed",
            },
        )
        raise


async def analyze_generation_images(
    session_id: str,
    asset_context: dict,
    run_id: str,
) -> int:
    images = [
        image
        for image in asset_context.get("images", [])
        if not (
            isinstance(image.get("vision"), dict)
            and image["vision"].get("status") == "completed"
        )
    ]
    if not images:
        return 0

    store = get_session_store()
    concurrency = min(get_settings().image_analysis_concurrency, len(images))
    store.add_run_event(
        run_id,
        {
            "progress": 8,
            "message": f"Analyzing {len(images)} uploaded image(s) with concurrency {concurrency}",
            "type": "stage",
        },
    )

    semaphore = asyncio.Semaphore(concurrency)

    async def analyze_one(image: dict) -> dict:
        async with semaphore:
            return await analyze_image_asset(session_id, image)

    analyzed = await asyncio.gather(*(analyze_one(image) for image in images))
    failures = [
        str(image.get("file_name") or image.get("id"))
        for image in analyzed
        if (image.get("vision") or {}).get("status") == "failed"
    ]
    if failures:
        store.add_run_event(
            run_id,
            {
                "progress": 10,
                "message": "Some images could not be analyzed: " + ", ".join(failures),
                "type": "warning",
            },
        )
    else:
        store.add_run_event(
            run_id,
            {
                "progress": 10,
                "message": f"Analyzed {len(analyzed)} uploaded image(s)",
                "type": "stage",
            },
        )
    return len(analyzed)


async def build_outline(session: dict, asset_context: dict) -> tuple[dict, str]:
    try:
        outline = await generate_deck_outline(
            {
                "topic": session["topic"],
                "brief": session["brief"],
                "page_count": session["page_count"],
                "style_id": session.get("style_id"),
                "style_prompt": session.get("style_prompt"),
                "output_language": session.get("output_language") or "auto",
                "asset_context": asset_context,
            }
        )
        return (
            outline,
            f"LLM planned {len(outline['slides'])} slides with "
            f"{outline['design_contract']['theme']}",
        )
    except LLMDeckGeneratorUnavailableError as exc:
        fallback_plan = build_slide_plan(
            session["topic"], session["brief"], int(session["page_count"])
        )
        style = resolve_style_preset(
            session.get("style_id"),
            session.get("style_prompt"),
            locale=language_to_locale(session.get("output_language")),
        )
        outline = {
            "deck_title": session["topic"],
            "narrative": session["brief"],
            "style": style,
            "design_contract": {
                "theme": style["label"],
                "palette": ["#f6eddd", "#243426", "#b45c30", "#6f7a5f", "#fff9ec"],
                "typography": "Editorial serif headlines with clean supporting text.",
                "layout_rules": ["Use strong hierarchy", "Keep content inside a 16:9 canvas"],
                "visual_motifs": [style["visual_language"], style["prompt"]],
            },
            "slides": [
                {
                    "title": item["title"],
                    "role": "Advance the presentation narrative",
                    "main_message": item["summary"],
                    "content": [item["detail"]],
                    "layout_intent": "concept",
                }
                for item in fallback_plan
            ],
        }
        return outline, f"Used fallback outline planner: {exc}"


async def build_slide_from_spec(
    session: dict,
    outline: dict,
    item: dict,
    index: int,
    total: int,
    asset_context: dict,
    ai_image_brief: dict | None = None,
) -> tuple[dict, str, str]:
    local_asset_context = asset_context
    ai_image_asset = None
    if ai_image_brief:
        ai_image_asset = await generate_ai_image_for_slide(
            session=session,
            slide=item,
            page_number=index,
            brief=ai_image_brief,
        )
        local_asset_context = append_image_to_asset_context(asset_context, ai_image_asset)
    args = {
        "topic": session["topic"],
        "outline": outline,
        "slide": item,
        "page_number": index,
        "total_pages": total,
        "asset_context": local_asset_context,
        "output_language": session.get("output_language") or "auto",
    }
    try:
        spec = await generate_slide_spec_with_retries(args)
        source = "LLM SlideSpec"
    except LLMDeckGeneratorUnavailableError:
        spec = build_slide_spec(args)
        source = "local template SlideSpec because LLM is not configured"
    html = render_slide_spec_html(spec)
    suffix = (
        f" with AI image {ai_image_asset['file_name']}"
        if ai_image_asset
        else ""
    )
    return spec, html, f"Rendered slide {index}/{total} from {source}{suffix}: {item['title']}"


async def build_slides_from_specs_concurrently(
    *,
    session: dict,
    outline: dict,
    total: int,
    asset_context: dict,
    concurrency: int,
    ai_image_plan: dict[int, dict],
) -> list[dict]:
    semaphore = asyncio.Semaphore(concurrency)

    async def build_one(index: int, item: dict) -> dict:
        async with semaphore:
            spec, html, message = await build_slide_from_spec(
                session,
                outline,
                item,
                index,
                total,
                asset_context,
                ai_image_plan.get(index),
            )
            return {
                "index": index,
                "item": item,
                "spec": spec,
                "html": html,
                "message": message,
            }

    tasks = [
        build_one(index, item)
        for index, item in enumerate(outline["slides"], start=1)
    ]
    results = await asyncio.gather(*tasks)
    return sorted(results, key=lambda item: int(item["index"]))


async def plan_ai_images_for_slides(
    *,
    session: dict,
    outline: dict,
    total: int,
    asset_context: dict,
    run_id: str,
) -> dict[int, dict]:
    settings = get_settings()
    if (
        not session.get("enable_ai_images")
        or not ai_image_is_configured()
        or settings.ai_image_max_per_deck <= 0
    ):
        return {}

    store = get_session_store()
    store.add_run_event(
        run_id,
        {
            "progress": 21,
            "message": "Evaluating whether any slide genuinely needs AI-generated imagery",
            "type": "stage",
        },
    )
    decisions = await asyncio.gather(
        *(
            decide_slide_ai_image_need(
                {
                    "topic": session["topic"],
                    "outline": outline,
                    "slide": item,
                    "page_number": index,
                    "total_pages": total,
                    "asset_context": asset_context,
                }
            )
            for index, item in enumerate(outline["slides"], start=1)
        ),
        return_exceptions=True,
    )

    plan: dict[int, dict] = {}
    for index, decision in enumerate(decisions, start=1):
        if isinstance(decision, Exception):
            continue
        if decision.get("decision") != "generate":
            continue
        plan[index] = decision
        if len(plan) >= settings.ai_image_max_per_deck:
            break

    if plan:
        store.add_run_event(
            run_id,
            {
                "progress": 21,
                "message": (
                    "Approved AI image generation for slide(s): "
                    + ", ".join(str(page) for page in plan)
                ),
                "type": "stage",
            },
        )
    return plan


async def generate_ai_image_for_slide(
    *,
    session: dict,
    slide: dict,
    page_number: int,
    brief: dict,
) -> dict:
    try:
        generated = await generate_ai_image(
            str(brief["prompt"]),
            size=str(brief.get("size") or get_settings().ai_image_default_size),
        )
    except AIImageGenerationUnavailableError:
        raise
    except Exception as exc:
        raise ValueError(f"AI image generation failed for slide {page_number}: {exc}") from exc

    asset = get_asset_store().save_generated_image(
        session["id"],
        data=generated.data,
        mime_type=generated.mime_type,
        metadata={
            "model": generated.model,
            "prompt": generated.prompt,
            "size": generated.size,
            "target_page": page_number,
            "target_slide_title": slide.get("title"),
            "visual_purpose": brief.get("visual_purpose"),
            "placement_guidance": brief.get("placement_guidance"),
            "reason": brief.get("reason"),
            "notes": (
                f"AI-generated for slide {page_number}: "
                f"{brief.get('visual_purpose') or slide.get('title')}"
            ),
        },
    )
    return await analyze_image_asset(session["id"], asset)


def append_image_to_asset_context(asset_context: dict, image: dict) -> dict:
    return {
        "documents": list(asset_context.get("documents") or []),
        "images": [*(asset_context.get("images") or []), image],
    }


def language_to_locale(output_language: str | None) -> str:
    return "zh-CN" if output_language == "zh-CN" else "en-US"


async def generate_slide_spec_with_retries(args: dict) -> dict:
    previous_error: str | None = None
    for attempt in range(1, 4):
        try:
            return await generate_slide_spec(args, previous_error=previous_error)
        except LLMDeckGeneratorUnavailableError:
            raise
        except Exception as exc:
            previous_error = f"Attempt {attempt} failed: {exc}"
    raise ValueError(f"SlideSpec generation failed after 3 attempts. {previous_error}")


async def retry_missing_required_images(
    *,
    session: dict,
    slides: list[dict],
    asset_context: dict,
    run_id: str,
) -> list[dict]:
    missing = find_missing_required_images(slides, asset_context)
    if not missing:
        return slides

    store = get_session_store()
    store.add_run_event(
        run_id,
        {
            "progress": 90,
            "message": (
                "Retrying semantic placement for required image(s): "
                + ", ".join(str(image.get("file_name") or image.get("id")) for image in missing)
            ),
            "type": "stage",
        },
    )

    updated_slides = list(slides)
    for image in missing:
        updated_slides = await place_required_image_with_retries(
            session=session,
            slides=updated_slides,
            image=image,
            run_id=run_id,
        )
    return updated_slides


async def place_required_image_with_retries(
    *,
    session: dict,
    slides: list[dict],
    image: dict,
    run_id: str,
) -> list[dict]:
    store = get_session_store()
    previous_error: str | None = None
    for attempt in range(1, 3):
        try:
            result = await place_required_image_in_deck(
                {
                    "topic": session["topic"],
                    "brief": session["brief"],
                    "slides": slides,
                    "image": image,
                },
                previous_error=previous_error,
            )
            page_number = int(result["page_number"])
            target = next(
                (slide for slide in slides if int(slide.get("page_number")) == page_number),
                None,
            )
            if not target:
                raise ValueError(f"Model selected unknown page_number {page_number}")
            spec = result["spec"]
            if not slide_spec_uses_image(spec, image):
                raise ValueError(
                    f"Returned SlideSpec does not include required image {image.get('url')}"
                )
            html = render_slide_spec_html(spec)
            updated = store.write_slide(
                session_id=session["id"],
                page_number=page_number,
                title=target["title"],
                html=html,
                spec=spec,
            )
            updated_slides = [
                updated if int(slide.get("page_number")) == page_number else slide
                for slide in slides
            ]
            store.add_run_event(
                run_id,
                {
                    "progress": 92,
                    "message": (
                        f"Placed required image {image.get('file_name') or image.get('id')} "
                        f"on slide {page_number}"
                    ),
                    "type": "required_image_placed",
                    "slide_id": updated["id"],
                },
            )
            return updated_slides
        except LLMDeckGeneratorUnavailableError:
            raise
        except Exception as exc:
            previous_error = f"Attempt {attempt} failed: {exc}"
    raise ValueError(
        "Required image semantic placement failed after 2 attempts: "
        f"{image.get('file_name') or image.get('id')}. {previous_error}"
    )


def validate_required_images_used(slides: list[dict], asset_context: dict) -> None:
    missing = find_missing_required_images(slides, asset_context)
    if not missing:
        return
    names = ", ".join(str(image.get("file_name") or image.get("id")) for image in missing)
    raise ValueError(
        "Required images were not placed by the model after semantic image analysis: "
        f"{names}. Adjust image notes or reduce required image count and retry."
    )


def find_missing_required_images(slides: list[dict], asset_context: dict) -> list[dict]:
    required = [
        image for image in asset_context.get("images", []) if image.get("required")
    ]
    if not required:
        return []
    used_sources = {
        element.get("src")
        for slide in slides
        for element in (slide.get("spec") or {}).get("elements", [])
        if element.get("kind") == "image"
    }
    return [image for image in required if image.get("url") not in used_sources]


def slide_spec_uses_image(spec: dict, image: dict) -> bool:
    return any(
        element.get("kind") == "image" and element.get("src") == image.get("url")
        for element in spec.get("elements", [])
    )


def run_generation_sync(run_id: str) -> None:
    asyncio.run(run_generation(run_id))
