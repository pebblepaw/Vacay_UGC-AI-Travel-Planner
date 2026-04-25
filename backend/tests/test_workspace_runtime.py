from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.models.schemas import Accommodation, Day, POI, SourceVideo, Trip
from backend.services.workspace_runtime import workspace_runtime


def test_workspace_id_for_telegram_topic():
    workspace_id = workspace_runtime.workspace_id_for_telegram(chat_id=-10012345, thread_id=77)
    assert workspace_id == "telegram:-10012345:77"


def test_share_token_roundtrip():
    workspace_id = "telegram:-100111:main"
    token = workspace_runtime.make_share_token(workspace_id, ttl_seconds=300)
    verified = workspace_runtime.verify_share_token(token)
    assert verified == workspace_id


@pytest.mark.asyncio
async def test_ensure_workspace_preserves_existing_trip_binding(monkeypatch: pytest.MonkeyPatch):
    stored = {
        "id": "telegram:-100200:main",
        "trip_id": "trip_real_binding",
        "title": "Existing Workspace",
        "source": "telegram",
        "data": {"created_at": "2026-04-25T00:00:00Z"},
    }

    class _FakeTable:
        def __init__(self) -> None:
            self._mode = "select"

        def select(self, *_args, **_kwargs):
            self._mode = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def upsert(self, payload):
            self._mode = "upsert"
            stored.update(payload)
            return self

        def execute(self):
            if self._mode == "select":
                return SimpleNamespace(data=[stored.copy()])
            return SimpleNamespace(data=[stored.copy()])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda _name: _FakeTable())),
    )

    await workspace_runtime.ensure_workspace("telegram:-100200:main", title="Renamed Workspace")
    trip_id = await workspace_runtime.get_workspace_trip_id("telegram:-100200:main")

    assert trip_id == "trip_real_binding"
    assert stored["title"] == "Renamed Workspace"


@pytest.mark.asyncio
async def test_build_workspace_snapshot_uses_poi_media_urls_over_title_guess(
    monkeypatch: pytest.MonkeyPatch,
):
    trip = Trip(
        trip_id="trip_media_links",
        title="Media Linked Trip",
        source_videos=[
            SourceVideo(
                platform="instagram",
                url="https://instagram.com/reel/abc",
                title="Clip A",
                preview_url="http://127.0.0.1:8000/media/clip-a.mp4",
            ),
            SourceVideo(
                platform="youtube",
                url="https://youtube.com/watch?v=tokyo123",
                title="Clip B",
            ),
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    POI(
                        id="poi_media_1",
                        name="Tokyo Tower",
                        category="Culture",
                        coords=(139.7454, 35.6586),
                        img="https://example.com/tower.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Iconic skyline",
                        priority="high",
                        intensity="normal",
                        visit_duration=90,
                        media_urls=["https://instagram.com/reel/abc", "https://youtube.com/watch?v=tokyo123"],
                    )
                ],
            )
        ],
        accommodation=Accommodation(
            name="Demo Hotel",
            price_per_night=200,
            status="Mock",
            img="https://example.com/hotel.jpg",
            coords=(139.7, 35.6),
        ),
    )

    monkeypatch.setattr(workspace_runtime, "load_runtime_state", AsyncMock(return_value={}))
    monkeypatch.setattr(workspace_runtime, "list_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(workspace_runtime, "list_events", AsyncMock(return_value=[]))

    class _FakeTable:
        def upsert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda _name: _FakeTable())),
    )

    snapshot = await workspace_runtime.build_workspace_snapshot("telegram:-100:main", trip)
    media = snapshot["media_by_place"]["poi_media_1"]

    assert [item["source_url"] for item in media] == [
        "https://instagram.com/reel/abc",
        "https://youtube.com/watch?v=tokyo123",
    ]
    assert media[0]["url"] == "http://127.0.0.1:8000/media/clip-a.mp4"
    assert media[1]["url"] == "https://youtube.com/watch?v=tokyo123"


@pytest.mark.asyncio
async def test_build_workspace_snapshot_notifies_subscribers(monkeypatch: pytest.MonkeyPatch):
    trip = Trip(
        trip_id="trip_live_updates",
        title="Live Updates Trip",
        source_videos=[],
        days=[],
        accommodation=Accommodation(
            name="Demo Hotel",
            price_per_night=200,
            status="Mock",
            img="https://example.com/hotel.jpg",
            coords=(139.7, 35.6),
        ),
    )

    monkeypatch.setattr(workspace_runtime, "load_runtime_state", AsyncMock(return_value={}))
    monkeypatch.setattr(workspace_runtime, "list_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(workspace_runtime, "list_events", AsyncMock(return_value=[]))

    class _FakeTable:
        def upsert(self, payload):
            self.payload = payload
            return self

        def execute(self):
            return SimpleNamespace(data=[])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda _name: _FakeTable())),
    )

    queue = workspace_runtime.subscribe("telegram:-100:main")
    snapshot = await workspace_runtime.build_workspace_snapshot("telegram:-100:main", trip)
    payload = await queue.get()
    workspace_runtime.unsubscribe("telegram:-100:main", queue)

    assert payload["type"] == "snapshot"
    assert payload["snapshot"]["trip"]["trip_id"] == snapshot["trip"]["trip_id"]


@pytest.mark.asyncio
async def test_save_runtime_state_preserves_existing_langgraph_payload(monkeypatch: pytest.MonkeyPatch):
    stored = {
        "booking_context": {"destination": "Tokyo"},
        "langgraph": {"checkpoints": {"": {"cp-1": {"checkpoint": {"type": "json", "payload": "e30="}}}}},
    }

    class _FakeTable:
        def __init__(self) -> None:
            self._mode = "select"

        def select(self, *_args, **_kwargs):
            self._mode = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def upsert(self, payload):
            self._mode = "upsert"
            stored.update(payload["state"])
            return self

        def execute(self):
            return SimpleNamespace(data=[{"state": stored.copy()}])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda _name: _FakeTable())),
    )

    await workspace_runtime.save_runtime_state("telegram:-100:main", {"pending_import_candidates": ["cinema"]})

    assert stored["booking_context"] == {"destination": "Tokyo"}
    assert stored["langgraph"] == {"checkpoints": {"": {"cp-1": {"checkpoint": {"type": "json", "payload": "e30="}}}}}
    assert stored["pending_import_candidates"] == ["cinema"]


@pytest.mark.asyncio
async def test_clear_langgraph_state_preserves_non_graph_runtime_fields(monkeypatch: pytest.MonkeyPatch):
    stored = {
        "booking_context": {"destination": "Tokyo"},
        "pending_import_candidates": ["cinema"],
        "langgraph": {"checkpoints": {"": {"cp-1": {"checkpoint": {"type": "json", "payload": "e30="}}}}},
    }

    class _FakeTable:
        def __init__(self) -> None:
            self._mode = "select"

        def select(self, *_args, **_kwargs):
            self._mode = "select"
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def upsert(self, payload):
            self._mode = "upsert"
            stored.clear()
            stored.update(payload["state"])
            return self

        def execute(self):
            return SimpleNamespace(data=[{"state": stored.copy()}])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda _name: _FakeTable())),
    )

    await workspace_runtime.clear_langgraph_state("telegram:-100:main")

    assert stored == {
        "booking_context": {"destination": "Tokyo"},
        "pending_import_candidates": ["cinema"],
    }


def test_workspace_websocket_streams_initial_snapshot(monkeypatch: pytest.MonkeyPatch):
    async def _no_seed():
        return None

    monkeypatch.setattr("backend.main.supabase_storage.seed_placeholder_if_empty", _no_seed)
    monkeypatch.setattr("backend.main.configure_graph_checkpointer", lambda: False)
    monkeypatch.setattr("backend.main.close_graph_checkpointer", lambda: None)

    snapshot = {
        "workspace_id": "telegram:-100:main",
        "trip": {
            "trip_id": "trip_ws_stream",
            "title": "Websocket Trip",
            "source_videos": [],
            "days": [],
            "accommodation": {
                "name": "Demo Hotel",
                "price_per_night": 120.0,
                "status": "Mock",
                "img": "https://example.com/hotel.jpg",
                "coords": [151.21, -33.87],
            },
        },
        "media_by_place": {},
        "runtime_state": {},
        "workspace_memory": {},
        "recent_events": [],
        "updated_at": "2026-04-25T00:00:00Z",
    }

    monkeypatch.setattr("backend.routers.workspaces.workspace_runtime.ensure_workspace", AsyncMock())
    monkeypatch.setattr("backend.routers.workspaces.workspace_runtime.get_workspace_snapshot", AsyncMock(return_value=snapshot))
    monkeypatch.setattr("backend.routers.workspaces.workspace_runtime.subscribe", lambda _workspace_id: __import__("asyncio").Queue())
    monkeypatch.setattr("backend.routers.workspaces.workspace_runtime.unsubscribe", lambda _workspace_id, _queue: None)

    with TestClient(app) as client:
        with client.websocket_connect("/api/workspaces/telegram%3A-100%3Amain/events/ws") as websocket:
            payload = websocket.receive_json()

    assert payload["type"] == "snapshot"
    assert payload["snapshot"]["workspace_id"] == "telegram:-100:main"
