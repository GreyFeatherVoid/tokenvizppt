import json
from functools import lru_cache
from pathlib import Path
from typing import Any

DEFAULT_STYLE_ID = "executive"
DEFAULT_LOCALE = "en-US"
SUPPORTED_LOCALES = {"en-US", "zh-CN"}
STYLE_SKILL_ROOT = Path(__file__).resolve().parents[1] / "skills" / "styles"
STYLE_ORDER = [
    "executive",
    "tech",
    "academic",
    "magazine",
    "pitch",
    "minimal-white",
    "bauhaus",
    "swiss-grid",
    "neo-brutal",
    "cyber-neon",
    "japanese-minimal",
    "luxury-dark",
    "data-studio",
    "newsroom",
    "memphis-pop",
]


class StyleSkillError(Exception):
    pass


def resolve_style_preset(
    style_id: str | None,
    prompt_override: str | None = None,
    locale: str = DEFAULT_LOCALE,
) -> dict[str, str]:
    styles = load_style_skills()
    resolved = (style_id or DEFAULT_STYLE_ID).strip()
    if resolved not in styles:
        resolved = DEFAULT_STYLE_ID
    preset = localize_style(styles[resolved], normalize_locale(locale))
    prompt = (prompt_override or "").strip() or preset["prompt"]
    return {
        **preset,
        "prompt": prompt,
    }


def list_style_presets(locale: str = DEFAULT_LOCALE) -> list[dict[str, str]]:
    normalized = normalize_locale(locale)
    styles = load_style_skills()
    ordered_ids = [style_id for style_id in STYLE_ORDER if style_id in styles]
    ordered_ids.extend(style_id for style_id in styles if style_id not in ordered_ids)
    return [localize_style(styles[style_id], normalized) for style_id in ordered_ids]


@lru_cache
def load_style_skills() -> dict[str, dict[str, Any]]:
    if not STYLE_SKILL_ROOT.exists():
        raise StyleSkillError(f"Style skill root not found: {STYLE_SKILL_ROOT}")
    styles: dict[str, dict[str, Any]] = {}
    for directory in sorted(path for path in STYLE_SKILL_ROOT.iterdir() if path.is_dir()):
        style = load_style_skill(directory)
        styles[style["id"]] = style
    if DEFAULT_STYLE_ID not in styles:
        raise StyleSkillError(f"Default style {DEFAULT_STYLE_ID} is missing")
    return styles


def load_style_skill(directory: Path) -> dict[str, Any]:
    meta_path = directory / "meta.json"
    if not meta_path.exists():
        raise StyleSkillError(f"Missing style meta: {meta_path}")
    try:
        metadata = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise StyleSkillError(f"Invalid style meta JSON: {meta_path}") from exc

    style_id = str(metadata.get("id") or directory.name).strip()
    if not style_id:
        raise StyleSkillError(f"Style id is empty in {meta_path}")
    prompts = {
        locale: read_skill_prompt(directory, locale)
        for locale in SUPPORTED_LOCALES
    }
    return {
        "id": style_id,
        "label": normalize_localized_field(metadata.get("label"), style_id),
        "description": normalize_localized_field(metadata.get("description"), ""),
        "visual_language": normalize_localized_field(metadata.get("visual_language"), ""),
        "prompts": prompts,
    }


def read_skill_prompt(directory: Path, locale: str) -> str:
    path = directory / f"skill.{locale}.md"
    if not path.exists():
        if locale != DEFAULT_LOCALE:
            return read_skill_prompt(directory, DEFAULT_LOCALE)
        raise StyleSkillError(f"Missing style skill prompt: {path}")
    prompt = path.read_text(encoding="utf-8").strip()
    if not prompt:
        raise StyleSkillError(f"Empty style skill prompt: {path}")
    shared_protocol = read_shared_protocol(locale)
    return f"{prompt}\n\n{shared_protocol}".strip()


@lru_cache
def read_shared_protocol(locale: str) -> str:
    path = STYLE_SKILL_ROOT / f"_shared-protocol.{locale}.md"
    if not path.exists() and locale != DEFAULT_LOCALE:
        return read_shared_protocol(DEFAULT_LOCALE)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def localize_style(style: dict[str, Any], locale: str) -> dict[str, str]:
    return {
        "id": str(style["id"]),
        "label": localized_value(style["label"], locale),
        "description": localized_value(style["description"], locale),
        "visual_language": localized_value(style["visual_language"], locale),
        "prompt": str(style["prompts"].get(locale) or style["prompts"][DEFAULT_LOCALE]),
    }


def normalize_localized_field(value: object, fallback: str) -> dict[str, str]:
    if isinstance(value, dict):
        result = {
            locale: str(value.get(locale) or value.get(DEFAULT_LOCALE) or fallback)
            for locale in SUPPORTED_LOCALES
        }
        return result
    text = str(value or fallback)
    return {locale: text for locale in SUPPORTED_LOCALES}


def localized_value(value: dict[str, str], locale: str) -> str:
    return value.get(locale) or value.get(DEFAULT_LOCALE) or ""


def normalize_locale(locale: str | None) -> str:
    normalized = str(locale or DEFAULT_LOCALE).strip()
    return normalized if normalized in SUPPORTED_LOCALES else DEFAULT_LOCALE
