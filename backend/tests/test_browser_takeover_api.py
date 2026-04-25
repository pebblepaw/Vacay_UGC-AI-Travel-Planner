from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

import backend.services.browser_takeover as browser_takeover_module
from backend.config import settings
from backend.main import app
from backend.services.automation.live_booking_sessions import live_booking_sessions


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
    assert payload["active"] is True
    assert payload["current_url"] == "https://www.trip.com/flights/passenger?booking=123"
