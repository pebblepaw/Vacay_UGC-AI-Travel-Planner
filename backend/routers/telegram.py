"""Telegram webhook ingestion for workspace-scoped runtime."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.models.schemas import TelegramWebhookRequest
from backend.routers.workspaces import _invoke_workspace_agent
from backend.services.telegram_bot import telegram_bot
from backend.services.workspace_runtime import workspace_runtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])


def _format_interrupt_options(response) -> str:
    lines: list[str] = []
    for msg in response.messages:
        if msg.type != "interrupt" or not msg.options:
            continue
        lines.append("\nOptions:")
        for idx, opt in enumerate(msg.options, start=1):
            lines.append(f"{idx}. {opt.name} — ${opt.price:.2f}")
    return "\n".join(lines)


def _workspace_share_url(workspace_id: str) -> str:
    token = workspace_runtime.make_share_token(workspace_id)
    base = settings.PUBLIC_WEB_BASE_URL.rstrip("/")
    return f"{base}/?workspace={workspace_id}&token={token}"


@router.post("/webhook")
async def ingest_telegram_webhook(
    request: TelegramWebhookRequest,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if expected and expected != x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    message = request.message or request.edited_message
    if not message:
        return {"status": "ignored", "reason": "no_message"}

    text = (message.get("text") or "").strip()
    if not text:
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

    agent_text = ""
    for msg in response.messages:
        if msg.type == "agent":
            agent_text = msg.content

    outbound_lines = [agent_text or "Done."]
    options_text = _format_interrupt_options(response)
    if options_text:
        outbound_lines.append(options_text)

    outbound_lines.append(f"\nWorkspace: {_workspace_share_url(workspace_id)}")
    outbound_text = "\n".join(outbound_lines)

    sent = False
    if telegram_bot.enabled:
        try:
            await telegram_bot.send_message(
                chat_id=chat_id,
                text=outbound_text,
                message_thread_id=thread_id,
            )
            sent = True
        except Exception as exc:
            logger.error("Telegram outbound send failed: %s", exc)

    return {
        "status": "processed",
        "workspace_id": workspace_id,
        "response_preview": outbound_text,
        "sent_to_telegram": sent,
    }
