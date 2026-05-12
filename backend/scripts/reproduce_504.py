import argparse
import asyncio
import json
import time
from dataclasses import dataclass

import httpx

from app.core.settings import get_settings
from app.services.llm_deck_generator import build_slide_html_prompt


@dataclass
class AttemptResult:
    index: int
    ok: bool
    status_code: int | None
    elapsed: float
    body: str


def build_business_html_payload(model: str, temperature: float) -> dict:
    prompt = build_slide_html_prompt(
        {
            "page_number": 1,
            "total_pages": 5,
            "outline": {
                "deck_title": "AI Product Launch Strategy",
                "narrative": (
                    "Show executives how the product can move from market signal to launch "
                    "execution with measurable confidence."
                ),
                "design_contract": {
                    "theme": "Executive technology briefing",
                    "palette": ["#f6eddd", "#243426", "#b45c30", "#6f7a5f", "#fff9ec"],
                    "typography": (
                        "Editorial serif headlines with compact sans-serif labels and strong "
                        "numeric emphasis."
                    ),
                    "layout_rules": [
                        "Use a centered 16:9 canvas",
                        "Create asymmetric editorial hierarchy",
                        "Use strong contrast blocks",
                        "Keep text readable and inside bounds",
                    ],
                    "visual_motifs": [
                        "signal lines",
                        "executive memo cards",
                        "market map",
                    ],
                },
            },
            "slide": {
                "title": "Market Signal Creates a Narrow Launch Window",
                "role": "Frame why the product launch matters now.",
                "main_message": (
                    "Customer urgency, competitor movement, and internal readiness align into "
                    "a time-sensitive launch opportunity."
                ),
                "content": [
                    "Priority accounts are asking for workflow automation now.",
                    (
                        "Competitors are still feature-led, leaving room for a narrative-led "
                        "launch."
                    ),
                    "Internal platform readiness is sufficient for a focused first release.",
                    (
                        "The decision is no longer whether to launch, but how tightly to scope it."
                    ),
                ],
                "layout_intent": (
                    "Create a polished executive slide with a large title, one bold takeaway, "
                    "three evidence cards, and a small timeline marker."
                ),
            },
        }
    )
    return {
        "model": model,
        "temperature": temperature,
        "max_tokens":12000,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are an expert HTML presentation designer. Return only one complete "
                    "HTML document. No markdown fences. No explanations."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }


def compact_body(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "\n...[truncated]"


async def post_once(
    index: int,
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    payload: dict,
    body_limit: int,
) -> AttemptResult:
    started = time.perf_counter()
    try:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        elapsed = time.perf_counter() - started
        return AttemptResult(
            index=index,
            ok=response.is_success,
            status_code=response.status_code,
            elapsed=elapsed,
            body=compact_body(response.text, body_limit),
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return AttemptResult(
            index=index,
            ok=False,
            status_code=None,
            elapsed=elapsed,
            body=repr(exc),
        )


async def run_batch(
    start_index: int,
    concurrency: int,
    client: httpx.AsyncClient,
    url: str,
    api_key: str,
    payload: dict,
    body_limit: int,
) -> list[AttemptResult]:
    return await asyncio.gather(
        *[
            post_once(start_index + offset, client, url, api_key, payload, body_limit)
            for offset in range(concurrency)
        ]
    )


def print_result(result: AttemptResult) -> None:
    status = "OK" if result.ok else "FAIL"
    code = result.status_code if result.status_code is not None else "exception"
    print(f"[{status}] attempt={result.index} status={code} elapsed={result.elapsed:.2f}s")
    print(result.body)
    print("-" * 88)


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Reproduce 504s with the current business HTML generation prompt."
    )
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--body-limit", type=int, default=1600)
    parser.add_argument("--sleep", type=float, default=0)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise SystemExit("TOKENVIZPPT_LLM_API_KEY and TOKENVIZPPT_LLM_MODEL are required.")

    base_url = settings.llm_base_url.strip() or "https://api.openai.com/v1"
    url = base_url.rstrip("/") + "/chat/completions"
    timeout = args.timeout or settings.llm_timeout_seconds
    payload = build_business_html_payload(settings.llm_model, settings.llm_temperature)

    print("504 reproduction test")
    print(
        json.dumps(
            {
                "url": url,
                "model": settings.llm_model,
                "attempts": args.attempts,
                "concurrency": args.concurrency,
                "timeout": timeout,
                "prompt_chars": len(payload["messages"][1]["content"]),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("-" * 88)

    results: list[AttemptResult] = []
    async with httpx.AsyncClient(timeout=timeout) as client:
        current = 1
        while current <= args.attempts:
            batch_size = min(args.concurrency, args.attempts - current + 1)
            batch = await run_batch(
                start_index=current,
                concurrency=batch_size,
                client=client,
                url=url,
                api_key=settings.llm_api_key,
                payload=payload,
                body_limit=args.body_limit,
            )
            for result in batch:
                print_result(result)
            results.extend(batch)
            current += batch_size
            if args.sleep > 0 and current <= args.attempts:
                await asyncio.sleep(args.sleep)

    ok = sum(1 for item in results if item.ok)
    failed = len(results) - ok
    gateway_timeout = sum(1 for item in results if item.status_code == 504)
    print(
        json.dumps(
            {
                "ok": ok,
                "failed": failed,
                "gateway_timeout_504": gateway_timeout,
                "max_elapsed": max((item.elapsed for item in results), default=0),
                "avg_elapsed": (
                    sum(item.elapsed for item in results) / len(results) if results else 0
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
