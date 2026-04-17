"""In-process registry for visible booking browser sessions."""

from __future__ import annotations

from dataclasses import dataclass
import asyncio
import time
import uuid
from typing import Any


@dataclass
class LiveBookingSession:
    session_id: str
    provider: str
    playwright: Any
    browser: Any
    page: Any
    created_at: float
    query_summary: str = ""


class LiveBookingSessionRegistry:
    """Keep visible Playwright sessions alive between search and checkout."""

    def __init__(self) -> None:
        self._sessions: dict[str, LiveBookingSession] = {}
        self._lock = asyncio.Lock()

    async def register(
        self,
        *,
        provider: str,
        playwright: Any,
        browser: Any,
        page: Any,
        query_summary: str = "",
    ) -> LiveBookingSession:
        async with self._lock:
            session = LiveBookingSession(
                session_id=f"trip_session_{uuid.uuid4().hex[:10]}",
                provider=provider,
                playwright=playwright,
                browser=browser,
                page=page,
                created_at=time.time(),
                query_summary=query_summary,
            )
            self._sessions[session.session_id] = session
            return session

    async def get(self, session_id: str | None) -> LiveBookingSession | None:
        if not session_id:
            return None
        async with self._lock:
            return self._sessions.get(session_id)

    async def close(self, session_id: str | None) -> None:
        if not session_id:
            return

        async with self._lock:
            session = self._sessions.pop(session_id, None)

        if not session:
            return

        browser = session.browser
        playwright = session.playwright

        try:
            if browser is not None:
                await browser.close()
        finally:
            stop = getattr(playwright, "stop", None)
            if callable(stop):
                await stop()
            else:
                exit_fn = getattr(playwright, "__aexit__", None)
                if callable(exit_fn):
                    await exit_fn(None, None, None)


live_booking_sessions = LiveBookingSessionRegistry()
