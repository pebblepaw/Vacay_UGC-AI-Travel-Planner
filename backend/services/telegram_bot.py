"""Telegram outbound bot helper for demo webhook flow."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)


class TelegramBotService:
    def __init__(self) -> None:
        self._timeout = 20.0

    @property
    def enabled(self) -> bool:
        return bool(settings.TELEGRAM_BOT_TOKEN)

    async def send_message(
        self,
        *,
        chat_id: int | str,
        text: str,
        message_thread_id: int | None = None,
    ) -> dict[str, Any]:
        if not settings.TELEGRAM_BOT_TOKEN:
            raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

        url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
            "disable_web_page_preview": True,
        }
        if message_thread_id is not None:
            payload["message_thread_id"] = message_thread_id

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        if not data.get("ok"):
            raise RuntimeError(f"Telegram sendMessage failed: {data}")
        return data


telegram_bot = TelegramBotService()
