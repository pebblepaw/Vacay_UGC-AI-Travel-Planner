from types import SimpleNamespace
from unittest.mock import AsyncMock
import asyncio
import sys
import types
from urllib.parse import parse_qs, urlparse

fake_supabase = types.ModuleType("supabase")
fake_supabase.create_client = lambda *args, **kwargs: SimpleNamespace()
fake_supabase.Client = object
sys.modules.setdefault("supabase", fake_supabase)

from fastapi.testclient import TestClient
from fastapi import FastAPI

import backend.services.browser_takeover as browser_takeover_module
from backend.routers.browser import router as browser_router
from backend.config import settings
from backend.services.automation.live_booking_sessions import live_booking_sessions

app = FastAPI()
app.include_router(browser_router)


def test_browser_takeover_endpoint_returns_session_details():
    token = live_booking_sessions.make_takeover_token(
        session_id="trip_session_demo",
        workspace_id="telegram:-100:main",
    )

    client = TestClient(app)
    response = client.get("/api/browser/takeover", params={"token": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == "trip_session_demo"
    assert payload["workspace_id"] == "telegram:-100:main"
    assert "embed_url" in payload


def test_browser_takeover_endpoint_uses_durable_workspace_state_when_live_session_is_gone(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PUBLIC_REMOTE_BROWSER_URL",
        "https://demo.example/remote-browser/vnc.html?autoconnect=true&resize=scale",
    )
    monkeypatch.setattr(
        browser_takeover_module,
        "workspace_runtime",
        SimpleNamespace(
            load_runtime_state=AsyncMock(
                return_value={
                    "booking_result": {
                        "confirmation_url": "https://www.trip.com/flights/passenger?booking=123",
                        "status": "needs_user_payment",
                    }
                }
            )
        ),
        raising=False,
    )

    token = live_booking_sessions.make_takeover_token(
        session_id="trip_session_missing",
        workspace_id="telegram:-200:main",
    )

    client = TestClient(app)
    response = client.get("/api/browser/takeover", params={"token": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["workspace_id"] == "telegram:-200:main"
    assert payload["active"] is False
    assert payload["current_url"] == "https://www.trip.com/flights/passenger?booking=123"
    parsed_embed = urlparse(payload["embed_url"])
    params = parse_qs(parsed_embed.query)
    assert params["path"] == ["remote-browser/websockify"]


def test_browser_takeover_endpoint_recovers_last_known_url_from_signed_token_when_session_is_gone(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://demo.vacay.ai")
    monkeypatch.setattr(
        settings,
        "PUBLIC_REMOTE_BROWSER_URL",
        "https://demo.example/remote-browser/vnc.html?autoconnect=true&resize=scale",
    )
    monkeypatch.setattr(
        browser_takeover_module,
        "workspace_runtime",
        SimpleNamespace(load_runtime_state=AsyncMock(return_value={})),
        raising=False,
    )

    fake_page = SimpleNamespace(url="https://www.trip.com/flights/passenger?booking=recover-123")
    fake_browser = AsyncMock()
    fake_playwright = AsyncMock()

    session = asyncio.run(
        live_booking_sessions.register(
            provider="trip.com",
            playwright=fake_playwright,
            browser=fake_browser,
            page=fake_page,
            query_summary="Singapore to Tokyo",
        )
    )

    takeover_url = asyncio.run(
        browser_takeover_module.browser_takeover_service.create_takeover_url(
            session_id=session.session_id,
            workspace_id=None,
        )
    )
    token = parse_qs(urlparse(takeover_url).query)["token"][0]

    asyncio.run(live_booking_sessions.close(session.session_id))

    client = TestClient(app)
    response = client.get("/api/browser/takeover", params={"token": token})

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == session.session_id
    assert payload["workspace_id"] is None
    assert payload["active"] is False
    assert payload["current_url"] == "https://www.trip.com/flights/passenger?booking=recover-123"


def test_browser_takeover_endpoint_adds_remote_browser_websockify_path(monkeypatch):
    monkeypatch.setattr(
        settings,
        "PUBLIC_REMOTE_BROWSER_URL",
        "https://demo.example/remote-browser/vnc.html?autoconnect=true&resize=scale",
    )
    monkeypatch.setattr(
        browser_takeover_module,
        "workspace_runtime",
        SimpleNamespace(load_runtime_state=AsyncMock(return_value={})),
        raising=False,
    )

    token = live_booking_sessions.make_takeover_token(
        session_id="trip_session_embed_path",
        workspace_id="telegram:-300:main",
    )

    client = TestClient(app)
    response = client.get("/api/browser/takeover", params={"token": token})

    assert response.status_code == 200
    payload = response.json()
    parsed = urlparse(payload["embed_url"])
    params = parse_qs(parsed.query)
    assert params["autoconnect"] == ["true"]
    assert params["resize"] == ["scale"]
    assert params["path"] == ["remote-browser/websockify"]


def test_create_takeover_url_omits_huge_recovery_url_when_workspace_is_available(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://demo.vacay.ai")

    fake_page = SimpleNamespace(
        url="https://www.trip.com/flights/passenger?" + "x=" + ("1234567890" * 200)
    )
    fake_browser = AsyncMock()
    fake_playwright = AsyncMock()

    session = asyncio.run(
        live_booking_sessions.register(
            provider="trip.com",
            playwright=fake_playwright,
            browser=fake_browser,
            page=fake_page,
            query_summary="Singapore to Sydney",
        )
    )

    takeover_url = asyncio.run(
        browser_takeover_module.browser_takeover_service.create_takeover_url(
            session_id=session.session_id,
            workspace_id="telegram:-5289526650:main",
        )
    )
    token = parse_qs(urlparse(takeover_url).query)["token"][0]
    payload = live_booking_sessions.verify_takeover_token(token)

    assert payload is not None
    assert payload["workspace_id"] == "telegram:-5289526650:main"
    assert "recovery" not in payload
    assert len(takeover_url) < 600

    asyncio.run(live_booking_sessions.close(session.session_id))
