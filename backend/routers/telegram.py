"""Telegram webhook ingestion for workspace-scoped runtime."""
from __future__ import annotations

from datetime import datetime
import logging
import re

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.models.schemas import ChatMessage, ChatResponse, TelegramWebhookRequest, VideoProcessRequest
from backend.routers.workspaces import _invoke_workspace_agent, process_workspace_videos
from backend.services.telegram_bot import telegram_bot
from backend.services.workspace_runtime import workspace_runtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])
URL_RE = re.compile(r"https?://[^\s,]+", re.IGNORECASE)


def _extract_urls_and_prompt(text: str) -> tuple[list[str], str]:
    urls = []
    seen = set()
    for match in URL_RE.findall(text):
        cleaned = match.strip().rstrip(".,)")
        if cleaned not in seen:
            urls.append(cleaned)
            seen.add(cleaned)

    prompt = text
    for url in urls:
        prompt = prompt.replace(url, " ")
    prompt = re.sub(r"\s+", " ", prompt).strip()
    return urls, prompt


async def _ingest_workspace_urls(workspace_id: str, urls: list[str]) -> dict:
    return await process_workspace_videos(workspace_id, VideoProcessRequest(urls=urls))


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


def _message_targets_bot(text: str, bot_username: str | None, chat_type: str | None) -> bool:
    if not text:
        return False

    lowered = text.lower()
    if chat_type not in {"group", "supergroup"}:
        return True

    if not bot_username:
        return False

    mention = f"@{bot_username.lower()}"
    return mention in lowered


def _strip_bot_mention(text: str, bot_username: str | None) -> str:
    if not bot_username:
        return text
    pattern = re.compile(rf"@{re.escape(bot_username)}\b", re.IGNORECASE)
    cleaned = pattern.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


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
    bot_username = await telegram_bot.get_username() if telegram_bot.enabled else None
    if not _message_targets_bot(text, bot_username, chat.get("type")):
        return {"status": "ignored", "reason": "bot_not_tagged"}

    chat_id = chat.get("id")
    if chat_id is None:
        return {"status": "ignored", "reason": "missing_chat_id"}

    thread_id = message.get("message_thread_id")
    user = message.get("from") or {}
    user_id = str(user.get("id")) if user.get("id") is not None else None

    workspace_id = workspace_runtime.workspace_id_for_telegram(chat_id, thread_id)
    await workspace_runtime.ensure_workspace(workspace_id, title=chat.get("title") or "Telegram Workspace")

    cleaned_text = _strip_bot_mention(text, bot_username)
    urls, prompt = _extract_urls_and_prompt(cleaned_text)
    imported = None
    if urls:
        imported = await _ingest_workspace_urls(workspace_id, urls)

    if prompt:
        response = await _invoke_workspace_agent(
            workspace_id=workspace_id,
            message=prompt,
            user_id=user_id,
            source="telegram",
        )
    else:
        imported_count = int((imported or {}).get("imported_count") or 0)
        failed_count = int((imported or {}).get("failed_count") or 0)
        response = ChatResponse(
            messages=[
                ChatMessage(
                    id="telegram_import_summary",
                    type="agent",
                    content=(
                        f"Imported {imported_count} media link(s)"
                        + (f", {failed_count} failed." if failed_count else ".")
                    ),
                    timestamp=datetime.now(),
                )
            ],
            updated_trip=None,
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
