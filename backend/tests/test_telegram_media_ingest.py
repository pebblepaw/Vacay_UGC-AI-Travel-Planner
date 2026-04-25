from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from backend.models.schemas import ChatMessage, ChatResponse, TelegramWebhookRequest
from backend.routers import telegram as telegram_router


def test_extract_urls_and_prompt_from_telegram_text():
    text = (
        "Plan a 3-day trip from these TikToks\n"
        "https://www.tiktok.com/@one/video/1\n"
        "https://www.instagram.com/reel/2"
    )

    urls, prompt = telegram_router._extract_urls_and_prompt(text)

    assert urls == [
        "https://www.tiktok.com/@one/video/1",
        "https://www.instagram.com/reel/2",
    ]
    assert prompt == "Plan a 3-day trip from these TikToks"


async def _chat_response() -> ChatResponse:
    return ChatResponse(
        messages=[
            ChatMessage(id="u1", type="user", content="hi", timestamp="2026-04-25T00:00:00Z"),
            ChatMessage(id="a1", type="agent", content="Done", timestamp="2026-04-25T00:00:01Z"),
        ],
        updated_trip=None,
    )


@pytest.mark.asyncio
async def test_telegram_webhook_imports_urls_before_agent_chat(monkeypatch):
    ingest_mock = AsyncMock(
        return_value={
            "workspace_id": "telegram:-100777:main",
            "trip_id": "trip_media",
            "snapshot": {"trip": {"trip_id": "trip_media"}},
            "imported_count": 2,
            "failed_count": 0,
        }
    )
    invoke_mock = AsyncMock(return_value=await _chat_response())
    send_mock = AsyncMock(return_value={"ok": True})

    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "sec")
    monkeypatch.setattr(telegram_router.settings, "PUBLIC_WEB_BASE_URL", "https://demo.vacay.ai")
    monkeypatch.setattr(telegram_router.telegram_bot, "get_username", AsyncMock(return_value="VacayClawBot"))
    monkeypatch.setattr(telegram_router.telegram_bot, "send_message", send_mock)
    monkeypatch.setattr(telegram_router, "_ingest_workspace_urls", ingest_mock)
    monkeypatch.setattr(telegram_router, "_invoke_workspace_agent", invoke_mock)
    monkeypatch.setattr(
        telegram_router,
        "workspace_runtime",
        SimpleNamespace(
            workspace_id_for_telegram=lambda chat_id, thread_id=None: f"telegram:{chat_id}:{thread_id or 'main'}",
            ensure_workspace=AsyncMock(return_value={}),
            make_share_token=lambda workspace_id: "signed-token",
        ),
    )

    req = TelegramWebhookRequest(
        update_id=1,
        message={
            "text": (
                "@VacayClawBot Plan a 3-day trip from these TikToks "
                "https://www.tiktok.com/@one/video/1 "
                "https://www.instagram.com/reel/2"
            ),
            "chat": {"id": -100777, "title": "Vacay", "type": "supergroup"},
            "from": {"id": 55},
        },
    )

    result = await telegram_router.ingest_telegram_webhook(req, x_telegram_bot_api_secret_token="sec")

    ingest_mock.assert_awaited_once_with(
        "telegram:-100777:main",
        [
            "https://www.tiktok.com/@one/video/1",
            "https://www.instagram.com/reel/2",
        ],
    )
    invoke_mock.assert_awaited_once_with(
        workspace_id="telegram:-100777:main",
        message="Plan a 3-day trip from these TikToks",
        user_id="55",
        source="telegram",
    )
    assert result["status"] == "processed"
    assert result["sent_to_telegram"] is True


@pytest.mark.asyncio
async def test_telegram_webhook_ignores_untagged_group_messages(monkeypatch):
    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "sec")
    monkeypatch.setattr(telegram_router.telegram_bot, "get_username", AsyncMock(return_value="VacayClawBot"))

    ingest_mock = AsyncMock()
    invoke_mock = AsyncMock()
    monkeypatch.setattr(telegram_router, "_ingest_workspace_urls", ingest_mock)
    monkeypatch.setattr(telegram_router, "_invoke_workspace_agent", invoke_mock)

    req = TelegramWebhookRequest(
        update_id=2,
        message={
            "text": "Plan a 3-day trip from these TikToks https://www.tiktok.com/@one/video/1",
            "chat": {"id": -100777, "title": "Vacay", "type": "supergroup"},
            "from": {"id": 55},
        },
    )

    result = await telegram_router.ingest_telegram_webhook(req, x_telegram_bot_api_secret_token="sec")

    assert result == {"status": "ignored", "reason": "bot_not_tagged"}
    ingest_mock.assert_not_awaited()
    invoke_mock.assert_not_awaited()
