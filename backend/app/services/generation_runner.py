import asyncio
from datetime import UTC, datetime

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
from app.services.referral_service import get_referral_service
from app.services.session_store import get_session_store
from app.services.style_presets import resolve_style_preset
from app.services.usage_service import UsageCharge, UsageCreditsInsufficientError, get_usage_service


class GenerationCancelledError(ValueError):
    pass


class GenerationTaskTimeoutError(TimeoutError):
    pass


async def run_generation(run_id: str) -> None:
    store = get_session_store()
    run = store.get_run(run_id)
    session = store.get_session(run["session_id"])
    asset_store = get_asset_store()
    deck_charge = charge_from_run_metadata(run)
    ai_image_charge = None

    try:
        if run.get("status") == "cancelled":
            store.update_session(session["id"], {"status": "cancelled"})
            return
        ensure_not_cancelled(run_id)
        store.update_run(run_id, {"status": "running"})
        store.add_run_event(
            run_id,
            {
                "progress": 3,
                "message": "Generation worker started",
                "type": "running",
            },
        )
        started_at = datetime.now(UTC)
        deck_charge, ai_image_charge = await run_generation_body(
            run=run,
            session=session,
            deck_charge=deck_charge,
            ai_image_charge=ai_image_charge,
            started_at=started_at,
        )
    except Exception as exc:
        if ai_image_charge:
            get_usage_service().refund(ai_image_charge, reason="refund")
        get_usage_service().refund(deck_charge, reason="refund")
        latest_run = store.get_run(run_id)
        if latest_run.get("status") == "cancelled" or isinstance(exc, GenerationCancelledError):
            store.update_session(session["id"], {"status": "cancelled"})
            if not any((event.get("type") == "cancelled") for event in latest_run.get("events") or []):
                store.add_run_event(
                    run_id,
                    {
                        "progress": int(latest_run.get("progress") or 100),
                        "message": "Generation cancelled",
                        "type": "cancelled",
                    },
                )
            return
        failure = classify_generation_failure(exc)
        mark_run_failed(run_id, failure)
        store.update_session(session["id"], {"status": "failed"})
        store.add_run_event(
            run_id,
            {
                "progress": 100,
                "message": f"{failure['title']}: {failure['detail']}",
                "type": "failed",
                "category": failure["category"],
            },
        )
        raise


async def run_generation_body(
    *,
    run: dict,
    session: dict,
    deck_charge: UsageCharge,
    ai_image_charge: UsageCharge | None,
    started_at: datetime,
) -> tuple[UsageCharge, UsageCharge | None]:
    timeout = get_settings().generation_task_timeout_seconds
    try:
        return await asyncio.wait_for(
            _run_generation_body(
                run=run,
                session=session,
                deck_charge=deck_charge,
                ai_image_charge=ai_image_charge,
                started_at=started_at,
            ),
            timeout=timeout,
        )
    except TimeoutError as exc:
        raise GenerationTaskTimeoutError(f"Generation exceeded {timeout} seconds") from exc


async def _run_generation_body(
    *,
    run: dict,
    session: dict,
    deck_charge: UsageCharge,
    ai_image_charge: UsageCharge | None,
    started_at: datetime,
) -> tuple[UsageCharge, UsageCharge | None]:
    store = get_session_store()
    asset_store = get_asset_store()
    run_id = run["id"]
    ensure_not_cancelled(run_id)
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

    ensure_not_cancelled(run_id)
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
    ensure_not_cancelled(run_id)
    ai_image_plan = await plan_ai_images_for_slides(
        session=session,
        outline=outline,
        total=total,
        asset_context=asset_context,
        run_id=run_id,
    )
    ensure_not_cancelled(run_id)
    if ai_image_plan:
        charge_data = (run.get("metadata") or {}).get("charge") or {}
        ai_image_charge = get_usage_service().reserve_ai_images(
            user_id=charge_data.get("user_id") or session.get("user_id"),
            run_id=run_id,
            count=len(ai_image_plan),
            pending_amount=deck_charge.amount if not deck_charge.settled else 0,
        )
    ensure_not_cancelled(run_id)
    slide_payloads = await build_slides_from_specs_concurrently(
        session=session,
        outline=outline,
        total=total,
        asset_context=asset_context,
        concurrency=concurrency,
        ai_image_plan=ai_image_plan,
    )

    slides = []
    ensure_not_cancelled(run_id)
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

    ensure_not_cancelled(run_id)
    slides = await retry_missing_required_images(
        session=session,
        slides=slides,
        asset_context=asset_context,
        run_id=run_id,
    )
    ensure_not_cancelled(run_id)
    validate_required_images_used(slides, asset_context)
    store.add_run_event(
        run_id,
        {
            "progress": 94,
            "message": "Validated generated HTML slides",
            "type": "stage",
        },
    )

    deck_charge = settle_generation_charge(
        run,
        page_count=int(session.get("page_count") or len(slides) or 1),
    )
    persist_charge_state(run_id, deck_charge)
    if ai_image_charge:
        ai_image_charge = get_usage_service().settle(
            ai_image_charge,
            metadata={"image_count": len(ai_image_plan)},
        )
    store.update_session(session["id"], {"status": "completed", "slides": slides})
    if deck_charge.charged:
        store.add_run_event(
            run_id,
            {
                "progress": 95,
                "message": f"Charged {deck_charge.amount} credit(s) for PPT generation",
                "type": "credits_charged",
            },
        )
    if ai_image_charge:
        store.add_run_event(
            run_id,
            {
                "progress": 96,
                "message": f"Charged {ai_image_charge.amount} credit(s) for AI image generation",
                "type": "credits_charged",
            },
        )
    get_referral_service().reward_first_generation(session.get("user_id"), run_id)
    elapsed_ms = elapsed_since_ms(started_at)
    store.update_run(run_id, {"status": "completed", "progress": 100})
    persist_generation_meta(run_id, {"completed_at": utc_now_iso(), "duration_ms": elapsed_ms})
    store.add_run_event(
        run_id,
        {
            "progress": 100,
            "message": "Generation complete",
            "type": "completed",
            "duration_ms": elapsed_ms,
        },
    )
    return deck_charge, ai_image_charge


def ensure_not_cancelled(run_id: str) -> None:
    run = get_session_store().get_run(run_id)
    if run.get("status") == "cancelled":
        raise GenerationCancelledError("Generation cancelled")


def classify_generation_failure(exc: Exception) -> dict:
    message = str(exc) or exc.__class__.__name__
    lower = message.lower()
    if isinstance(exc, GenerationTaskTimeoutError):
        category = "timeout"
        title = "Generation timed out"
        detail = message
    elif isinstance(exc, UsageCreditsInsufficientError) or "insufficient credits" in lower:
        category = "credits"
        title = "Insufficient credits"
        detail = "The account no longer has enough credits to finalize this generation."
    elif isinstance(exc, (LLMDeckGeneratorUnavailableError, AIImageGenerationUnavailableError)):
        category = "provider_config"
        title = "AI provider is not configured"
        detail = message
    elif "ai image generation failed" in lower or "ai image request failed" in lower:
        category = "ai_image"
        title = "AI image generation failed"
        detail = message
    elif "slidespec generation failed" in lower or "overlap" in lower:
        category = "layout"
        title = "Slide layout validation failed"
        detail = message
    elif "required image" in lower or "image placement" in lower:
        category = "asset_placement"
        title = "Required asset placement failed"
        detail = message
    elif "llm" in lower or "model" in lower or "provider" in lower:
        category = "model"
        title = "AI model request failed"
        detail = message
    else:
        category = "system"
        title = "Generation failed"
        detail = message
    return {
        "category": category,
        "title": title,
        "detail": detail[:1200],
        "exception_type": exc.__class__.__name__,
        "failed_at": utc_now_iso(),
    }


def mark_run_failed(run_id: str, failure: dict) -> None:
    store = get_session_store()
    persist_generation_meta(run_id, {"failure": failure})
    store.update_run(
        run_id,
        {
            "status": "failed",
            "error": f"{failure['title']}: {failure['detail']}",
        },
    )


def persist_generation_meta(run_id: str, generation_metadata: dict) -> None:
    store = get_session_store()
    run = store.get_run(run_id)
    metadata = dict(run.get("metadata") or {})
    generation = dict(metadata.get("generation") or {})
    generation.update(generation_metadata)
    metadata["generation"] = generation
    store.update_run(run_id, {"metadata": metadata})


def elapsed_since_ms(started_at: datetime) -> int:
    return max(0, round((datetime.now(UTC) - started_at).total_seconds() * 1000))


def utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    except ValueError as exc:
        spec = build_slide_spec(args)
        source = f"local template SlideSpec after invalid LLM layout ({exc})"
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
    if not session.get("enable_ai_images"):
        return {}

    store = get_session_store()
    if not ai_image_is_configured():
        store.add_run_event(
            run_id,
            {
                "progress": 21,
                "message": "AI image generation was requested but backend image generation is not configured",
                "type": "stage",
            },
        )
        return {}
    if settings.ai_image_max_per_deck <= 0:
        store.add_run_event(
            run_id,
            {
                "progress": 21,
                "message": "AI image generation was requested but the per-deck image limit is 0",
                "type": "stage",
            },
        )
        return {}

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
    skip_reasons: list[str] = []
    for index, decision in enumerate(decisions, start=1):
        if isinstance(decision, Exception):
            skip_reasons.append(f"slide {index}: decision failed")
            continue
        if decision.get("decision") != "generate":
            reason = str(decision.get("reason") or "not visually necessary")
            skip_reasons.append(f"slide {index}: {reason}")
            continue
        plan[index] = decision
        if len(plan) >= settings.ai_image_max_per_deck:
            break

    if not plan:
        fallback = _fallback_ai_image_plan(outline, total)
        if fallback:
            page_number, decision = fallback
            plan[page_number] = decision
            store.add_run_event(
                run_id,
                {
                    "progress": 21,
                    "message": (
                        "AI image planner skipped every slide; using the best-fit fallback "
                        f"slide {page_number} instead"
                    ),
                    "type": "stage",
                },
            )
        elif skip_reasons:
            store.add_run_event(
                run_id,
                {
                    "progress": 21,
                    "message": "AI image generation skipped: " + "; ".join(skip_reasons[:4]),
                    "type": "stage",
                },
            )

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


def _fallback_ai_image_plan(outline: dict, total: int) -> tuple[int, dict] | None:
    slides = outline.get("slides") or []
    if not slides:
        return None
    ranked_intents = {
        "image-focus": 0,
        "cover": 1,
        "concept": 2,
        "process": 3,
        "summary": 4,
        "quote": 5,
        "comparison": 6,
        "timeline": 7,
    }
    candidates: list[tuple[int, int, dict]] = []
    for index, slide in enumerate(slides, start=1):
        intent = str(slide.get("layout_intent") or "").strip().lower()
        if intent == "data-focus":
            continue
        rank = ranked_intents.get(intent, 8)
        candidates.append((rank, index, slide))
    if not candidates:
        return None
    _, page_number, slide = min(candidates, key=lambda item: (item[0], item[1]))
    content = "; ".join(str(point) for point in (slide.get("content") or [])[:3])
    title = str(slide.get("title") or f"Slide {page_number}")
    message = str(slide.get("main_message") or content or title)
    prompt = (
        "Create a polished, original 16:9 presentation visual with no text, no logos, "
        "and no UI screenshots. Use the deck's style and palette. "
        f"Slide title: {title}. Main message: {message}. Supporting ideas: {content}."
    )
    return page_number, {
        "decision": "generate",
        "reason": "User enabled AI visuals; fallback selected the best-fit non-data slide.",
        "visual_purpose": f"Support the slide message visually: {message}",
        "prompt": prompt,
        "size": get_settings().ai_image_default_size,
        "placement_guidance": "Use as a visual anchor while keeping all slide text editable and readable.",
        "fallback": True,
    }


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


def charge_from_run_metadata(run: dict) -> UsageCharge:
    charge_data = (run.get("metadata") or {}).get("charge") or {}
    return UsageCharge(
        enabled=bool(charge_data.get("enabled")),
        user_id=charge_data.get("user_id"),
        action=str(charge_data.get("action") or "deck_generation"),
        amount=int(charge_data.get("amount") or 0),
        reference_type=charge_data.get("reference_type"),
        reference_id=charge_data.get("reference_id"),
        idempotency_key=charge_data.get("idempotency_key"),
        anonymous=bool(charge_data.get("anonymous")),
        settled=bool(charge_data.get("settled", True)),
    )


def settle_generation_charge(run: dict, *, page_count: int) -> UsageCharge:
    charge = charge_from_run_metadata(run)
    try:
        return get_usage_service().settle(
            charge,
            metadata={"page_count": page_count},
        )
    except UsageCreditsInsufficientError as exc:
        raise ValueError("Insufficient credits when finalizing generation") from exc


def persist_charge_state(run_id: str, charge: UsageCharge) -> None:
    store = get_session_store()
    run = store.get_run(run_id)
    metadata = dict(run.get("metadata") or {})
    charge_data = dict(metadata.get("charge") or {})
    charge_data.update(
        {
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
    )
    metadata["charge"] = charge_data
    store.update_run(run_id, {"metadata": metadata})


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
