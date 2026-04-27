"""Telegram webhook ingestion for workspace-scoped runtime."""
from __future__ import annotations

from datetime import datetime
import logging
import re

from fastapi import APIRouter, Header, HTTPException

from backend.config import settings
from backend.models.schemas import ChatMessage, ChatResponse, TelegramWebhookRequest, VideoProcessRequest
from backend.routers.workspaces import (
    _build_workspace_reply_sections,
    _invoke_workspace_agent,
    _pack_telegram_sections,
    process_workspace_videos,
)
from backend.services.telegram_bot import telegram_bot
from backend.services.workspace_runtime import workspace_runtime

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/telegram", tags=["telegram"])
URL_RE = re.compile(r"https?://[^\s,]+", re.IGNORECASE)
FOLLOWUP_IMPORT_ACTION_RE = re.compile(
    r"\b(add|include|insert|put|swap|replace|move|remove|drop|schedule|pin|use)\b",
    re.IGNORECASE,
)
FOLLOWUP_IMPORT_REFERENCE_RE = re.compile(r"\b(this|these|that|those|it)\b", re.IGNORECASE)


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


def _should_run_followup_agent_after_import(prompt: str) -> bool:
    normalized = (prompt or "").strip()
    if not normalized:
        return False
    return bool(
        FOLLOWUP_IMPORT_ACTION_RE.search(normalized)
        and FOLLOWUP_IMPORT_REFERENCE_RE.search(normalized)
    )


@router.post("/webhook")
async def ingest_telegram_webhook(
    request: TelegramWebhookRequest,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    expected = settings.TELEGRAM_WEBHOOK_SECRET
    if expected and expected != x_telegram_bot_api_secret_token:
        raise HTTPException(status_code=403, detail="Invalid Telegram secret token")

    if request.edited_message and not request.message:
        return {"status": "ignored", "reason": "edited_message"}

    message = request.message
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
    message_id = message.get("message_id")

    workspace_id = workspace_runtime.workspace_id_for_telegram(chat_id, thread_id)
    await workspace_runtime.ensure_workspace(workspace_id, title=chat.get("title") or "Telegram Workspace")
    claimed = await workspace_runtime.claim_telegram_update(
        update_id=request.update_id,
        chat_id=chat_id,
        message_id=message_id,
        workspace_id=workspace_id,
    )
    if not claimed:
        return {"status": "ignored", "reason": "duplicate_update"}

    cleaned_text = _strip_bot_mention(text, bot_username)
    urls, prompt = _extract_urls_and_prompt(cleaned_text)
    imported = None
    import_summary_text = ""
    if urls:
        imported = await _ingest_workspace_urls(workspace_id, urls)
        imported_count = int((imported or {}).get("imported_count") or 0)
        failed_count = int((imported or {}).get("failed_count") or 0)
        import_summary_text = (
            f"Imported {imported_count} media link(s)"
            + (f", {failed_count} failed." if failed_count else ".")
        )

    if urls:
        if _should_run_followup_agent_after_import(prompt):
            response = await _invoke_workspace_agent(
                workspace_id=workspace_id,
                message=prompt,
                user_id=user_id,
                source="telegram",
            )
        else:
            response = ChatResponse(
                messages=[
                    ChatMessage(
                        id="telegram_import_summary",
                        type="agent",
                        content=import_summary_text or "Imported media link(s).",
                        timestamp=datetime.now(),
                    )
                ],
                updated_trip=None,
            )
    elif prompt:
        response = await _invoke_workspace_agent(
            workspace_id=workspace_id,
            message=prompt,
            user_id=user_id,
            source="telegram",
        )
    else:
        response = ChatResponse(
            messages=[
                ChatMessage(
                    id="telegram_empty_prompt_summary",
                    type="agent",
                    content="Imported media link(s).",
                    timestamp=datetime.now(),
                )
            ],
            updated_trip=None,
        )

    agent_text = ""
    for msg in response.messages:
        if msg.type == "agent":
            agent_text = msg.content

    outbound_sections: list[str] = []
    if import_summary_text:
        outbound_sections.append(import_summary_text)
    reply_sections = _build_workspace_reply_sections(
        workspace_id,
        response,
        default_text=None if import_summary_text else "Done.",
    )
    if import_summary_text:
        reply_sections = [
            section
            for section in reply_sections
            if section.strip() != import_summary_text.strip()
        ]
    outbound_sections.extend(reply_sections)
    outbound_text_chunks = _pack_telegram_sections(outbound_sections)
    outbound_text = "\n\n".join(outbound_text_chunks)

    sent = False
    if telegram_bot.enabled:
        try:
            for chunk in outbound_text_chunks:
                await telegram_bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
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
