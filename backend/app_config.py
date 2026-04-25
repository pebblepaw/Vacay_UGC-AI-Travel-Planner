"""User-editable runtime configuration loaded from config/config.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

from backend.config import settings


@dataclass(frozen=True)
class AssistantConfig:
    language: str
    language_instruction: str


@dataclass(frozen=True)
class LLMConfig:
    provider_preference: str
    roles: dict[str, str]
    profiles: dict[str, dict[str, str]]


@dataclass(frozen=True)
class AppConfig:
    assistant: AssistantConfig
    llm: LLMConfig
    copy: dict[str, Any]
    booking_defaults: dict[str, Any]


class _SafeDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _build_language_instruction(language: str) -> str:
    return f"Respond in {language} unless the user explicitly asks for another language."


def _read_config_file(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text())
    except FileNotFoundError as exc:
        raise RuntimeError(f"App config not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise RuntimeError(f"Invalid YAML in app config: {path}") from exc

    if not isinstance(raw, dict):
        raise RuntimeError(f"App config must be a YAML object: {path}")
    return raw


@lru_cache(maxsize=1)
def load_app_config() -> AppConfig:
    path = Path(settings.APP_CONFIG_PATH)
    data = _read_config_file(path)

    assistant_raw = data.get("assistant") if isinstance(data.get("assistant"), dict) else {}
    llm_raw = data.get("llm") if isinstance(data.get("llm"), dict) else {}
    copy_raw = data.get("copy") if isinstance(data.get("copy"), dict) else {}
    booking_defaults_raw = data.get("booking_defaults") if isinstance(data.get("booking_defaults"), dict) else {}

    language = str(assistant_raw.get("language") or "English").strip() or "English"
    assistant = AssistantConfig(
        language=language,
        language_instruction=_build_language_instruction(language),
    )

    llm = LLMConfig(
        provider_preference=str(llm_raw.get("provider_preference") or "auto"),
        roles=dict(llm_raw.get("roles") or {}),
        profiles={
            str(name): dict(profile or {})
            for name, profile in dict(llm_raw.get("profiles") or {}).items()
        },
    )

    return AppConfig(
        assistant=assistant,
        llm=llm,
        copy=dict(copy_raw),
        booking_defaults=dict(booking_defaults_raw),
    )


def get_assistant_language() -> str:
    return load_app_config().assistant.language


def get_assistant_language_instruction() -> str:
    return load_app_config().assistant.language_instruction


def resolve_role_profile(role: str) -> str:
    config = load_app_config().llm
    return str(config.roles.get(role) or config.roles.get("default") or "default")


def resolve_profile_model(role: str, provider: str) -> str:
    config = load_app_config().llm
    profile_name = resolve_role_profile(role)
    profile = config.profiles.get(profile_name) or {}
    model = str(profile.get(provider) or "").strip()
    if not model:
        raise RuntimeError(
            f"No model configured for role '{role}' and provider '{provider}' in {settings.APP_CONFIG_PATH}."
        )
    return model


def get_provider_preference() -> str:
    return load_app_config().llm.provider_preference


def _lookup_copy(path: str) -> str:
    current: Any = load_app_config().copy
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            raise KeyError(f"Copy path '{path}' not found in {settings.APP_CONFIG_PATH}.")
        current = current[part]
    if not isinstance(current, str):
        raise KeyError(f"Copy path '{path}' must point to a string template.")
    return current


def render_copy(path: str, **kwargs: Any) -> str:
    template = _lookup_copy(path)
    return template.format_map(_SafeDict(**kwargs))


def get_default_flight_origin() -> dict[str, str]:
    raw = load_app_config().booking_defaults.get("flight_origin")
    if not isinstance(raw, dict):
        return {}
    return {
        "name": str(raw.get("name") or "").strip(),
        "airport_code": str(raw.get("airport_code") or "").strip(),
        "city_code": str(raw.get("city_code") or "").strip(),
    }
