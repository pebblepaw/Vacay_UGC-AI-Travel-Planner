"""Shared LLM factory for backend agents.

This keeps provider-specific setup and role-based model resolution in one
place so agent nodes only ask for a ready-to-use chat model.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
from typing import Any

from backend.config import settings

logger = logging.getLogger(__name__)

DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_DASHSCOPE_MODEL = "qwen2.5-vl-3b-instruct"
DEFAULT_AGENT_ROLE = "default"
DEFAULT_ROLE_PROFILE = "cheap_tools"
_LEGACY_GEMINI_MODEL_MAP = {
    "gemini-2.0-flash": DEFAULT_GEMINI_MODEL,
}


@dataclass(frozen=True)
class AgentLLMConfig:
    provider: str
    model: str
    api_key: str
    base_url: str | None = None


def _normalize_provider(provider: str) -> str:
    lowered = (provider or "").strip().lower()
    if lowered in {"", "auto"}:
        return "auto"
    if lowered in {"aliyun", "dashscope", "qwen"}:
        return "dashscope"
    if lowered in {"gemini", "google"}:
        return "gemini"
    raise ValueError(
        f"Unsupported AGENT_LLM_PROVIDER='{settings.AGENT_LLM_PROVIDER}'. "
        "Expected 'auto', 'aliyun', 'dashscope', 'qwen', or 'gemini'."
    )


def _provider_candidates(preferred: str) -> list[str]:
    if preferred == "auto":
        return ["dashscope", "gemini"]
    if preferred == "dashscope":
        return ["dashscope", "gemini"]
    if preferred == "gemini":
        return ["gemini", "dashscope"]
    return [preferred]


def _normalize_role(role: str | None) -> str:
    normalized = (role or "").strip()
    return normalized or DEFAULT_AGENT_ROLE


def normalize_gemini_model(model: str | None) -> str:
    normalized = (model or "").strip()
    if normalized.startswith("models/"):
        normalized = normalized.removeprefix("models/")

    if not normalized:
        return DEFAULT_GEMINI_MODEL

    return _LEGACY_GEMINI_MODEL_MAP.get(normalized, normalized)


def _load_llm_profile_config() -> dict[str, Any]:
    path = Path(settings.AGENT_LLM_CONFIG_PATH)
    try:
        data = json.loads(path.read_text())
    except FileNotFoundError:
        logger.warning("LLM profile config not found at %s; falling back to env defaults", path)
        return {"roles": {}, "profiles": {}}
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Invalid JSON in LLM profile config: {path}") from exc

    if not isinstance(data, dict):
        raise RuntimeError(f"LLM profile config must be a JSON object: {path}")
    return data


def _default_model_for_provider(provider: str) -> str:
    if provider == "gemini":
        return normalize_gemini_model(settings.GEMINI_MODEL)
    if provider == "dashscope":
        normalized = (settings.DASHSCOPE_MODEL or "").strip()
        return normalized or DEFAULT_DASHSCOPE_MODEL
    raise RuntimeError(f"Unsupported provider '{provider}' for model resolution.")


def resolve_role_model(role: str, *, provider: str) -> str:
    """Resolve the model name for one role/provider pair.

    The config file is the source of truth. Environment defaults still act as a
    safety net when a role or provider entry is missing.
    """

    normalized_role = _normalize_role(role)
    config = _load_llm_profile_config()
    roles = config.get("roles") if isinstance(config.get("roles"), dict) else {}
    profiles = config.get("profiles") if isinstance(config.get("profiles"), dict) else {}

    profile_name = str(
        roles.get(normalized_role)
        or roles.get(DEFAULT_AGENT_ROLE)
        or DEFAULT_ROLE_PROFILE
    )
    profile = profiles.get(profile_name) if isinstance(profiles.get(profile_name), dict) else {}

    model = ""
    if isinstance(profile, dict):
        model = str(profile.get(provider) or "").strip()

    if not model:
        model = _default_model_for_provider(provider)

    if provider == "gemini":
        return normalize_gemini_model(model)

    return model


def resolve_agent_llm_config(*, role: str = DEFAULT_AGENT_ROLE) -> AgentLLMConfig:
    """Resolve the usable agent provider and model for one agent role."""

    preferred = _normalize_provider(settings.AGENT_LLM_PROVIDER)

    for provider in _provider_candidates(preferred):
        if provider == "dashscope" and settings.DASHSCOPE_API_KEY:
            return AgentLLMConfig(
                provider="dashscope",
                model=resolve_role_model(role, provider="dashscope"),
                api_key=settings.DASHSCOPE_API_KEY,
                base_url=settings.DASHSCOPE_BASE_URL,
            )
        if provider == "gemini" and settings.GEMINI_API_KEY:
            return AgentLLMConfig(
                provider="gemini",
                model=resolve_role_model(role, provider="gemini"),
                api_key=settings.GEMINI_API_KEY,
            )

    raise RuntimeError(
        "No compatible agent LLM is configured. Set DASHSCOPE_API_KEY for "
        "DashScope/Qwen or GEMINI_API_KEY for Gemini."
    )


def get_agent_llm(*, role: str = DEFAULT_AGENT_ROLE, temperature: float = 0) -> Any:
    """Return the configured chat model for one agent role.

    Supported providers:
    - dashscope: DashScope / Qwen via OpenAI-compatible endpoint
    - gemini: Google Gemini via langchain-google-genai
    """

    config = resolve_agent_llm_config(role=role)

    if config.provider == "dashscope":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=config.model,
            api_key=config.api_key,
            base_url=config.base_url,
            temperature=temperature,
        )

    if config.provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.model,
            api_key=config.api_key,
            temperature=temperature,
        )

    raise RuntimeError(f"Unsupported resolved provider '{config.provider}'.")
