"""Shared LLM factory for backend agents."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.app_config import get_provider_preference, resolve_profile_model
from backend.config import settings


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
        f"Unsupported provider_preference='{provider}' in {settings.APP_CONFIG_PATH}. "
        "Expected 'auto', 'dashscope', 'qwen', 'aliyun', or 'gemini'."
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
    return normalized or "default"


def normalize_model_name(model: str | None) -> str:
    normalized = (model or "").strip()
    if normalized.startswith("models/"):
        return normalized.removeprefix("models/")
    return normalized


def resolve_role_model(role: str, *, provider: str) -> str:
    return normalize_model_name(resolve_profile_model(_normalize_role(role), provider))


def resolve_agent_llm_config(*, role: str = "default") -> AgentLLMConfig:
    preferred = _normalize_provider(get_provider_preference())

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


def get_agent_llm(*, role: str = "default", temperature: float = 0) -> Any:
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
