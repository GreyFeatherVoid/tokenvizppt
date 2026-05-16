from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_STORAGE_ROOT = Path(__file__).resolve().parents[3] / "storage"


class Settings(BaseSettings):
    app_name: str = "tokenvizPPT"
    app_env: str = "development"
    api_prefix: str = "/api"
    cors_origins: list[str] = ["http://localhost:6080"]

    database_url: str = "postgresql+psycopg://tokenvizppt:tokenvizppt@localhost:15432/tokenvizppt"
    redis_url: str = "redis://localhost:16379/0"

    storage_root: Path = Field(default=DEFAULT_STORAGE_ROOT)
    public_base_url: str = "http://127.0.0.1:6001"

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

    auth_enabled: bool = False
    allowed_email_domains: list[str] = []
    auth_code_ttl_seconds: int = Field(default=600, ge=60, le=3600)
    auth_code_resend_seconds: int = Field(default=60, ge=10, le=600)
    auth_session_ttl_days: int = Field(default=30, ge=1, le=365)
    auth_cookie_name: str = "tokenvizppt_session"
    auth_cookie_secure: bool = False
    signup_credits: int = Field(default=200, ge=0)
    daily_checkin_credits: int = Field(default=30, ge=0)
    deck_generation_page_credits: int = Field(default=1, ge=0)
    slide_edit_credits: int = Field(default=1, ge=0)
    ai_image_generation_credits: int = Field(default=5, ge=0)
    referral_inviter_credits: int = Field(default=50, ge=0)
    referral_invitee_credits: int = Field(default=20, ge=0)
    anon_daily_generation_limit: int = Field(default=1, ge=0)
    anon_daily_edit_limit: int = Field(default=1, ge=0)
    ip_hash_secret: str = ""
    admin_emails: list[str] = []

    smtp_host: str = ""
    smtp_port: int = Field(default=465, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="TOKENVIZPPT_",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
