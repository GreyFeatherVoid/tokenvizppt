import base64
from dataclasses import dataclass

import httpx

from app.core.settings import get_settings
from app.services.provider_config_service import get_effective_ai_image_config


class AIImageGenerationUnavailableError(Exception):
    pass


@dataclass(frozen=True)
class GeneratedImage:
    data: bytes
    mime_type: str
    model: str
    prompt: str
    size: str


def ai_image_is_configured() -> bool:
    return get_effective_ai_image_config().enabled


async def generate_ai_image(prompt: str, *, size: str | None = None) -> GeneratedImage:
    settings = get_settings()
    config = get_effective_ai_image_config()
    if not ai_image_is_configured():
        raise AIImageGenerationUnavailableError("AI image generation is not configured")
    if config.provider.strip().lower() != "openai":
        raise AIImageGenerationUnavailableError(
            f'Unsupported AI image provider "{config.provider}". Use openai-compatible.'
        )

    image_size = size or settings.ai_image_default_size
    base_url = config.base_url.strip() or "https://api.openai.com/v1"
    url = f"{base_url.rstrip('/')}/images/generations"
    payload = {
        "model": config.model,
        "prompt": prompt,
        "n": 1,
        "size": image_size,
        "response_format": "b64_json",
    }

    async with httpx.AsyncClient(timeout=settings.ai_image_timeout_seconds) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
    if not response.is_success:
        raise ValueError(f"AI image request failed: {response.status_code} {response.text}")

    data = response.json()
    items = data.get("data")
    if not isinstance(items, list) or not items:
        raise ValueError("AI image response does not contain data")
    b64 = items[0].get("b64_json")
    if not b64:
        raise ValueError("AI image response does not contain b64_json")
    return GeneratedImage(
        data=base64.b64decode(b64),
        mime_type="image/png",
        model=config.model,
        prompt=prompt,
        size=image_size,
    )
