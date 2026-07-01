import base64
import hashlib
import json
from dataclasses import dataclass
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select

from app.core.settings import get_settings
from app.db.session import SessionLocal
from app.models.admin import ProviderConfig


class ProviderConfigError(ValueError):
    pass


@dataclass(frozen=True)
class EffectiveProviderConfig:
    provider: str
    model: str
    api_key: str
    base_url: str
    enabled: bool
    source: str
    metadata: dict


def provider_config_to_dict(row: ProviderConfig) -> dict:
    metadata = _read_json(row.metadata_json)
    api_key = decrypt_api_key(row.encrypted_api_key)
    return {
        "id": row.id,
        "provider": row.provider,
        "name": row.name,
        "base_url": row.base_url,
        "model": row.model,
        "status": row.status,
        "api_key_masked": mask_api_key(api_key),
        "has_api_key": bool(api_key),
        "metadata": metadata,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def list_provider_configs() -> list[dict]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ProviderConfig).order_by(ProviderConfig.provider.asc(), ProviderConfig.updated_at.desc())
        ).all()
        return [provider_config_to_dict(row) for row in rows]


def upsert_provider_config(
    *,
    provider: str,
    name: str,
    model: str,
    base_url: str | None,
    api_key: str | None,
    status: str,
    metadata: dict | None = None,
    config_id: str | None = None,
) -> dict:
    clean_provider = provider.strip().lower()
    if clean_provider not in {"llm", "ai_image"}:
        raise ProviderConfigError("Invalid provider config type")
    if status not in {"active", "disabled"}:
        raise ProviderConfigError("Invalid provider config status")
    clean_model = model.strip()
    if not clean_model:
        raise ProviderConfigError("Model is required")
    with SessionLocal() as db:
        row = db.get(ProviderConfig, config_id) if config_id else None
        if not row:
            row = ProviderConfig(
                id=uuid4().hex,
                provider=clean_provider,
                name=name.strip()[:120] or clean_provider,
                base_url=(base_url or "").strip() or None,
                model=clean_model[:160],
                encrypted_api_key=None,
                status=status,
                metadata_json="{}",
            )
            db.add(row)
        if row.provider != clean_provider:
            raise ProviderConfigError("Cannot change provider config type")
        row.name = name.strip()[:120] or clean_provider
        row.base_url = (base_url or "").strip() or None
        row.model = clean_model[:160]
        row.status = status
        row.metadata_json = json.dumps(metadata or {}, ensure_ascii=False)
        if api_key is not None and api_key.strip():
            row.encrypted_api_key = encrypt_api_key(api_key.strip())
        if status == "active":
            others = db.scalars(
                select(ProviderConfig).where(
                    ProviderConfig.provider == clean_provider,
                    ProviderConfig.id != row.id,
                    ProviderConfig.status == "active",
                )
            ).all()
            for other in others:
                other.status = "disabled"
        db.commit()
        db.refresh(row)
        return provider_config_to_dict(row)


def get_effective_llm_config() -> EffectiveProviderConfig:
    settings = get_settings()
    db_config = _get_active_config("llm")
    if db_config:
        return db_config
    return EffectiveProviderConfig(
        provider=settings.llm_provider,
        model=settings.llm_model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        enabled=bool(settings.llm_api_key.strip() and settings.llm_model.strip()),
        source="env",
        metadata={},
    )


def get_effective_ai_image_config() -> EffectiveProviderConfig:
    settings = get_settings()
    db_config = _get_active_config("ai_image")
    if db_config:
        return db_config
    return EffectiveProviderConfig(
        provider=settings.ai_image_provider,
        model=settings.ai_image_model,
        api_key=settings.ai_image_api_key,
        base_url=settings.ai_image_base_url,
        enabled=bool(
            settings.ai_image_enabled
            and settings.ai_image_api_key.strip()
            and settings.ai_image_model.strip()
        ),
        source="env",
        metadata={"enabled": settings.ai_image_enabled},
    )


def _get_active_config(provider: str) -> EffectiveProviderConfig | None:
    with SessionLocal() as db:
        row = db.scalar(
            select(ProviderConfig)
            .where(ProviderConfig.provider == provider, ProviderConfig.status == "active")
            .order_by(ProviderConfig.updated_at.desc())
            .limit(1)
        )
        if not row:
            return None
        api_key = decrypt_api_key(row.encrypted_api_key)
        return EffectiveProviderConfig(
            provider="openai",
            model=row.model,
            api_key=api_key,
            base_url=row.base_url or "",
            enabled=bool(api_key and row.model.strip()),
            source="database",
            metadata=_read_json(row.metadata_json),
        )


def encrypt_api_key(api_key: str) -> str:
    return _fernet().encrypt(api_key.encode("utf-8")).decode("utf-8")


def decrypt_api_key(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return ""


def mask_api_key(api_key: str) -> str:
    if not api_key:
        return ""
    if len(api_key) <= 8:
        return "*" * len(api_key)
    return f"{api_key[:4]}...{api_key[-4:]}"


def _fernet() -> Fernet:
    settings = get_settings()
    secret = settings.provider_config_secret.strip() or settings.ip_hash_secret.strip()
    if not secret:
        raise ProviderConfigError(
            "TOKENVIZPPT_PROVIDER_CONFIG_SECRET or TOKENVIZPPT_IP_HASH_SECRET is required"
        )
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode("utf-8")).digest())
    return Fernet(key)


def _read_json(value: str) -> dict:
    try:
        data = json.loads(value or "{}")
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}
