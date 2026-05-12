import argparse
import asyncio
import json
import time
from dataclasses import dataclass

import httpx
from openai import AsyncOpenAI

from app.core.settings import get_settings
from app.services.llm_deck_generator import build_slide_html_prompt


@dataclass
class CaseResult:
    name: str
    ok: bool
    elapsed: float
    detail: str


def build_messages(case: str) -> list[dict[str, str]]:
    if case == "minimal":
        return [{"role": "user", "content": "Reply with exactly: pong"}]
    if case == "json":
        return [
            {
                "role": "system",
                "content": "Return only valid JSON. No markdown.",
            },
            {
                "role": "user",
                "content": (
                    'Return {"slides":[{"title":"A","summary":"B","detail":"C"}]} '
                    "with no extra text."
                ),
            },
        ]
    if case == "html":
        return [
            {
                "role": "system",
                "content": "Return only one complete HTML document. No markdown.",
            },
            {
                "role": "user",
                "content": (
                    "Generate a simple standalone 16:9 HTML slide about API diagnostics. "
                    "Use inline CSS only. No JavaScript."
                ),
            },
        ]
    if case == "business-html":
        return [
            {
                "role": "system",
                "content": (
                    "You are an expert HTML presentation designer. Return only one complete "
                    "HTML document. No markdown fences. No explanations."
                ),
            },
            {
                "role": "user",
                "content": build_slide_html_prompt(
                    {
                        "page_number": 1,
                        "total_pages": 5,
                        "outline": {
                            "deck_title": "AI Product Launch Strategy",
                            "narrative": (
                                "Show executives how the product can move from market signal "
                                "to launch execution with measurable confidence."
                            ),
                            "design_contract": {
                                "theme": "Executive technology briefing",
                                "palette": [
                                    "#f6eddd",
                                    "#243426",
                                    "#b45c30",
                                    "#6f7a5f",
                                    "#fff9ec",
                                ],
                                "typography": (
                                    "Editorial serif headlines with compact sans-serif labels "
                                    "and strong numeric emphasis."
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
                                "Customer urgency, competitor movement, and internal readiness "
                                "align into a time-sensitive launch opportunity."
                            ),
                            "content": [
                                "Priority accounts are asking for workflow automation now.",
                                (
                                    "Competitors are still feature-led, leaving room for a "
                                    "narrative-led launch."
                                ),
                                (
                                    "Internal platform readiness is sufficient for a focused "
                                    "first release."
                                ),
                                (
                                    "The decision is no longer whether to launch, but how tightly "
                                    "to scope it."
                                ),
                            ],
                            "layout_intent": (
                                "Create a polished executive slide with a large title, one bold "
                                "takeaway, three evidence cards, and a small timeline marker."
                            ),
                        },
                    }
                ),
            },
        ]
    raise ValueError(f"Unknown case: {case}")


def short_text(value: object, limit: int = 600) -> str:
    text = str(value)
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


async def run_openai_case(
    client: AsyncOpenAI,
    model: str,
    case: str,
    temperature: float,
) -> CaseResult:
    started = time.perf_counter()
    try:
        response = await client.chat.completions.create(
            model=model,
            temperature=temperature,
            messages=build_messages(case),
        )
        elapsed = time.perf_counter() - started
        content = response.choices[0].message.content or ""
        return CaseResult(case, True, elapsed, short_text(content))
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return CaseResult(case, False, elapsed, repr(exc))


async def run_raw_case(
    base_url: str,
    api_key: str,
    model: str,
    case: str,
    temperature: float,
    timeout: float,
) -> CaseResult:
    started = time.perf_counter()
    url = base_url.rstrip("/") + "/chat/completions"
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "temperature": temperature,
                    "messages": build_messages(case),
                },
            )
        elapsed = time.perf_counter() - started
        body = response.text
        detail = f"status={response.status_code} body={short_text(body)}"
        return CaseResult(f"raw:{case}", response.is_success, elapsed, detail)
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return CaseResult(f"raw:{case}", False, elapsed, repr(exc))


async def run_concurrency(
    client: AsyncOpenAI,
    model: str,
    concurrency: int,
    temperature: float,
    case: str,
) -> list[CaseResult]:
    tasks = [
        run_openai_case(client, model, case, temperature)
        for _index in range(concurrency)
    ]
    results = await asyncio.gather(*tasks)
    return [
        CaseResult(
            name=f"concurrency-{index + 1}",
            ok=result.ok,
            elapsed=result.elapsed,
            detail=result.detail,
        )
        for index, result in enumerate(results)
    ]


def print_result(result: CaseResult) -> None:
    status = "OK" if result.ok else "FAIL"
    print(f"[{status}] {result.name} elapsed={result.elapsed:.2f}s")
    print(f"      {result.detail}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Diagnose OpenAI-compatible chat API behavior.")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--max-retries", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument(
        "--concurrency-case",
        default="minimal",
        choices=["minimal", "html", "business-html"],
    )
    parser.add_argument("--skip-concurrency", action="store_true")
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise SystemExit("TOKENVIZPPT_LLM_API_KEY and TOKENVIZPPT_LLM_MODEL are required.")

    base_url = settings.llm_base_url.strip() or "https://api.openai.com/v1"
    timeout = args.timeout or settings.llm_timeout_seconds
    print("LLM diagnostics")
    print(f"provider={settings.llm_provider}")
    print(f"base_url={base_url}")
    print(f"model={settings.llm_model}")
    print(f"timeout={timeout}")
    print(f"max_retries={args.max_retries}")
    print(f"concurrency={args.concurrency}")
    print()

    client = AsyncOpenAI(
        api_key=settings.llm_api_key,
        base_url=base_url,
        timeout=timeout,
        max_retries=args.max_retries,
    )

    try:
        raw = await run_raw_case(
            base_url=base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
            case="minimal",
            temperature=settings.llm_temperature,
            timeout=timeout,
        )
        print_result(raw)

        for case in ["minimal", "json", "html", "business-html"]:
            print_result(
                await run_openai_case(
                    client=client,
                    model=settings.llm_model,
                    case=case,
                    temperature=settings.llm_temperature,
                )
            )

        if not args.skip_concurrency:
            print()
            print("Concurrency test")
            results = await run_concurrency(
                client=client,
                model=settings.llm_model,
                concurrency=args.concurrency,
                temperature=settings.llm_temperature,
                case=args.concurrency_case,
            )
            for result in results:
                print_result(result)
            print(
                json.dumps(
                    {
                        "ok": sum(1 for item in results if item.ok),
                        "failed": sum(1 for item in results if not item.ok),
                        "max_elapsed": max((item.elapsed for item in results), default=0),
                    },
                    ensure_ascii=False,
                )
            )
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
