"""Signed remote-browser takeover URLs for hosted booking sessions."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from backend.config import settings
from backend.services.automation.live_booking_sessions import live_booking_sessions
from backend.services.workspace_runtime import workspace_runtime


class BrowserTakeoverService:
    @property
    def enabled(self) -> bool:
        return bool(settings.PUBLIC_WEB_BASE_URL and settings.PUBLIC_REMOTE_BROWSER_URL)

    async def create_takeover_url(
        self,
        *,
        session_id: str,
        workspace_id: str | None = None,
    ) -> str:
        session = await live_booking_sessions.get(session_id)
        recovery: dict[str, Any] = {}
        if session is not None:
            try:
                recovery["current_url"] = str(session.page.url or "")
            except Exception:
                recovery["current_url"] = ""
            recovery["provider"] = str(session.provider or "")
            recovery["query_summary"] = str(session.query_summary or "")
        token = live_booking_sessions.make_takeover_token(
            session_id=session_id,
            workspace_id=workspace_id,
            recovery=recovery or None,
        )
        base = settings.PUBLIC_WEB_BASE_URL.rstrip("/")
        return f"{base}/browser?token={quote(token)}"

    async def get_takeover_payload(self, token: str) -> dict[str, Any] | None:
        payload = live_booking_sessions.verify_takeover_token(token)
        if payload is None:
            return None

        workspace_id = payload.get("workspace_id")
        session = await live_booking_sessions.get(payload.get("session_id"))
        recovery = payload.get("recovery") if isinstance(payload.get("recovery"), dict) else {}
        current_url = str(recovery.get("current_url") or "")
        active = session is not None
        if session is not None:
            try:
                current_url = str(session.page.url or "")
            except Exception:
                current_url = ""

        if workspace_id:
            runtime_state = await workspace_runtime.load_runtime_state(workspace_id)
            booking_result = dict(runtime_state.get("booking_result") or {})
            durable_url = str(
                booking_result.get("current_browser_url")
                or booking_result.get("confirmation_url")
                or ""
            )
            if durable_url:
                current_url = durable_url

        return {
            "session_id": payload.get("session_id"),
            "workspace_id": workspace_id,
            "active": active,
            "current_url": current_url,
            "embed_url": settings.PUBLIC_REMOTE_BROWSER_URL or "",
        }


browser_takeover_service = BrowserTakeoverService()
