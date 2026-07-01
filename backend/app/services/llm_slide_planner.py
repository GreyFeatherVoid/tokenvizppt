import json
import re

from openai import AsyncOpenAI

from app.core.settings import get_settings
from app.services.mock_slide_generator import build_slide_plan
from app.services.provider_config_service import get_effective_llm_config


class LLMPlannerUnavailableError(Exception):
    pass


def llm_is_configured() -> bool:
    return get_effective_llm_config().enabled


async def build_slide_plan_with_llm(
    topic: str, brief: str, page_count: int
) -> list[dict[str, str]]:
    settings = get_settings()
    config = get_effective_llm_config()
    if not llm_is_configured():
        raise LLMPlannerUnavailableError("LLM is not configured")
    if config.provider.strip().lower() != "openai":
        raise LLMPlannerUnavailableError(
            f'Unsupported LLM provider "{config.provider}". Currently use openai-compatible.'
        )

    client = AsyncOpenAI(
        api_key=config.api_key,
        base_url=config.base_url.strip() or None,
        timeout=settings.llm_timeout_seconds,
    )
    try:
        response = await client.chat.completions.create(
            model=config.model,
            temperature=settings.llm_temperature,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a senior presentation strategist. Return only valid JSON. "
                        "Do not wrap the JSON in markdown."
                    ),
                },
                {
                    "role": "user",
                    "content": build_planner_prompt(topic, brief, page_count),
                },
            ],
        )
        content = response.choices[0].message.content or ""
        return parse_slide_plan(content, topic, brief, page_count)
    finally:
        await client.close()


def build_planner_prompt(topic: str, brief: str, page_count: int) -> str:
    return f"""
Create a {page_count}-slide presentation plan.

Topic:
{topic}

Brief:
{brief}

Return JSON with this exact shape:
{{
  "slides": [
    {{
      "title": "short slide title",
      "summary": "one strong sentence for the main visual idea",
      "detail": "supporting content, 1-2 concise sentences"
    }}
  ]
}}

Rules:
- Return exactly {page_count} slides.
- Match the language of the user's topic and brief.
- Keep titles concise.
- Avoid generic filler.
- Do not mention that you are an AI.
""".strip()


def parse_slide_plan(content: str, topic: str, brief: str, page_count: int) -> list[dict[str, str]]:
    data = json.loads(extract_json_object(content))
    raw_slides = data.get("slides")
    if not isinstance(raw_slides, list):
        raise ValueError("LLM response does not contain a slides array")

    slides: list[dict[str, str]] = []
    fallback = build_slide_plan(topic, brief, page_count)
    for index in range(page_count):
        raw = (
            raw_slides[index]
            if index < len(raw_slides) and isinstance(raw_slides[index], dict)
            else {}
        )
        fb = fallback[index]
        slides.append(
            {
                "title": normalize_text(raw.get("title"), fb["title"], 140),
                "summary": normalize_text(raw.get("summary"), fb["summary"], 320),
                "detail": normalize_text(raw.get("detail"), fb["detail"], 700),
            }
        )
    return slides


def extract_json_object(content: str) -> str:
    text = content.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fenced:
        return fenced.group(1)
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1]
    raise ValueError("LLM response did not include a JSON object")


def normalize_text(value: object, fallback: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        text = fallback
    return text[:max_length]
