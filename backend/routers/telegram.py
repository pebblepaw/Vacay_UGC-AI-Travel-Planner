"""Telegram webhook ingestion for workspace-scoped runtime."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from backend.models.schemas import TelegramWebhookRequest, WorkspaceChatRequest
from backend.routers.workspaces import _invoke_workspace_agent
from backend.services.workspace_runtime import workspace_runtime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.post("/webhook")
async def ingest_telegram_webhook(
    request: TelegramWebhookRequest,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = None
    try:
        from backend.config import settings

        expected = getattr(settings, "TELEGRAM_WEBHOOK_SECRET", None)
    except Exception:
        expected = None

    if expected and expected != x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    message = request.message or request.edited_message
    if not message:
        return {"status": "ignored", "reason": "no_message"}

    text = message.get("text") or ""
    if not text.strip():
        return {"status": "ignored", "reason": "empty_text"}

    chat = message.get("chat") or {}
    chat_id = chat.get("id")
    if chat_id is None:
        return {"status": "ignored", "reason": "missing_chat_id"}

    thread_id = message.get("message_thread_id")
    user = message.get("from") or {}
    user_id = str(user.get("id")) if user.get("id") is not None else None

    workspace_id = workspace_runtime.workspace_id_for_telegram(chat_id, thread_id)
    await workspace_runtime.ensure_workspace(workspace_id, title=chat.get("title") or "Telegram Workspace")

    response = await _invoke_workspace_agent(
        workspace_id=workspace_id,
        message=text,
        user_id=user_id,
        source="telegram",
    )

    # This endpoint currently only ingests + processes; outbound send happens in bot worker.
    return {
        "status": "processed",
        "workspace_id": workspace_id,
        "response_preview": response.messages[-1].content if response.messages else "",
    }
