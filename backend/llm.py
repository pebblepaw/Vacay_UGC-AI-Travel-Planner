"""Shared LLM factory for backend agents.

This keeps provider-specific setup in one place so agent nodes only ask for a
ready-to-use chat model.
"""

from __future__ import annotations

from typing import Any

from backend.config import settings


def get_agent_llm(*, temperature: float = 0) -> Any:
    """Return the configured chat model for agent nodes.

    Supported providers:
    - aliyun: DashScope / Qwen via OpenAI-compatible endpoint
    - gemini: Google Gemini via langchain-google-genai
    """

    provider = settings.AGENT_LLM_PROVIDER.strip().lower()

    if provider in {"aliyun", "dashscope", "qwen"}:
        if not settings.DASHSCOPE_API_KEY:
            raise RuntimeError(
                "DASHSCOPE_API_KEY is not set. Add it to your .env before using the agent."
            )

        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.DASHSCOPE_MODEL,
            api_key=settings.DASHSCOPE_API_KEY,
            base_url=settings.DASHSCOPE_BASE_URL,
            temperature=temperature,
        )

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            api_key=settings.GEMINI_API_KEY,
            temperature=temperature,
        )

    raise ValueError(
        f"Unsupported AGENT_LLM_PROVIDER='{settings.AGENT_LLM_PROVIDER}'. "
        "Expected 'aliyun' or 'gemini'."
    )