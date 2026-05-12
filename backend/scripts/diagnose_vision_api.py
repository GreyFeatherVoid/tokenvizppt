import argparse
import asyncio
import base64
import json
import mimetypes
import time
from pathlib import Path

import httpx

from app.core.settings import get_settings


def image_to_data_url(path: Path) -> str:
    if not path.exists() or not path.is_file():
        raise SystemExit(f"Image file not found: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime_type};base64,{data}"


async def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test whether the configured OpenAI-compatible chat API supports image input."
    )
    parser.add_argument("image", type=Path, help="Local image path, e.g. ./sample.png")
    parser.add_argument("--prompt", default="Describe this image in 3 concise bullet points.")
    parser.add_argument("--timeout", type=float, default=None)
    parser.add_argument("--body-limit", type=int, default=3000)
    args = parser.parse_args()

    settings = get_settings()
    if not settings.llm_api_key or not settings.llm_model:
        raise SystemExit("TOKENVIZPPT_LLM_API_KEY and TOKENVIZPPT_LLM_MODEL are required.")

    base_url = settings.llm_base_url.strip() or "https://api.openai.com/v1"
    url = base_url.rstrip("/") + "/chat/completions"
    timeout = args.timeout or settings.llm_timeout_seconds
    payload = {
        "model": settings.llm_model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": args.prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": image_to_data_url(args.image)},
                    },
                ],
            }
        ],
    }

    print("Vision API diagnostics")
    print(
        json.dumps(
            {
                "url": url,
                "model": settings.llm_model,
                "image": str(args.image),
                "timeout": timeout,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    print("-" * 88)

    started = time.perf_counter()
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.llm_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    elapsed = time.perf_counter() - started
    print(f"status={response.status_code} elapsed={elapsed:.2f}s")
    body = response.text
    if len(body) > args.body_limit:
        body = body[: args.body_limit] + "\n...[truncated]"
    print(body)
    if response.is_success:
        try:
            data = response.json()
            content = data["choices"][0]["message"].get("content")
            print("-" * 88)
            print("vision_supported=true")
            print(content)
        except Exception:
            print("-" * 88)
            print("vision_supported=unknown_success_response")
    else:
        print("-" * 88)
        print("vision_supported=false_or_model_rejected_image")


if __name__ == "__main__":
    asyncio.run(main())
