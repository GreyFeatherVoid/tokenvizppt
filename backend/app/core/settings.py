from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"


class Settings(BaseSettings):
    app_name: str = "tokenvizPPT"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:5173"]

    database_url: str = "postgresql+psycopg://tokenvizppt:tokenvizppt@localhost:15432/tokenvizppt"
    redis_url: str = "redis://localhost:16379/0"

    storage_root: Path = Field(default=DEFAULT_STORAGE_ROOT)
    public_base_url: str = "http://127.0.0.1:8000"

    llm_provider: str = "openai"
    llm_model: str = ""
    llm_api_key: str = ""
    llm_base_url: str = ""
    llm_temperature: float = 0.7
    llm_timeout_seconds: float = 60
    generation_slide_concurrency: int = Field(default=3, ge=1, le=8)
    image_analysis_concurrency: int = Field(default=3, ge=1, le=8)

    ai_image_enabled: bool = False
    ai_image_provider: str = "openai"
    ai_image_model: str = "gpt-image-2"
    ai_image_api_key: str = ""
    ai_image_base_url: str = ""
    ai_image_timeout_seconds: float = 220
    ai_image_default_size: str = "1536x1024"
    ai_image_max_per_deck: int = Field(default=2, ge=0, le=8)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TOKENVIZPPT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
