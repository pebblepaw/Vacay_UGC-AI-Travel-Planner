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
async def test_build_workspace_snapshot_rewrites_media_urls_to_public_api_base(
    monkeypatch: pytest.MonkeyPatch,
):
    trip = Trip(
        trip_id="trip_public_media_base",
        title="Public Media Base Trip",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/1",
                title="Demo Clip",
                preview_url="http://127.0.0.1:8000/media/demo.mp4",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    POI(
                        id="poi_public_media",
                        name="Demo Place",
                        category="Culture",
                        coords=(151.2, -33.8),
                        img="https://example.com/demo.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Demo vibe",
                        priority="high",
                        intensity="normal",
                        visit_duration=90,
                        media_urls=["https://www.tiktok.com/@demo/video/1"],
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
    monkeypatch.setattr("backend.services.workspace_runtime.settings.PUBLIC_API_BASE_URL", "https://demo.vacayclaw.test")

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

    assert snapshot["trip"]["source_videos"][0]["preview_url"] == "https://demo.vacayclaw.test/media/demo.mp4"
    assert snapshot["media_by_place"]["poi_public_media"][0]["url"] == "https://demo.vacayclaw.test/media/demo.mp4"


@pytest.mark.asyncio
async def test_restart_workspace_preserves_metadata_and_filters_old_runtime_records(
    monkeypatch: pytest.MonkeyPatch,
):
    stored_workspace = {
        "id": "telegram:-100:main",
        "title": "Existing Workspace",
        "trip_id": "trip_old",
        "source": "telegram",
        "data": {
            "created_at": "2026-04-24T00:00:00+00:00",
            "started_at": "2026-04-24T00:00:00+00:00",
            "updated_at": "2026-04-24T00:00:00+00:00",
        },
    }
    stored_events = [
        {
            "role": "agent",
            "content": "old event",
            "metadata": {},
            "created_at": "2026-04-24T01:00:00+00:00",
        },
        {
            "role": "agent",
            "content": "fresh event",
            "metadata": {},
            "created_at": "2026-04-26T01:00:00+00:00",
        },
    ]
    stored_memory = [
        {
            "memory_key": "old_key",
            "memory_value": "old value",
            "updated_at": "2026-04-24T01:00:00+00:00",
        },
        {
            "memory_key": "fresh_key",
            "memory_value": "fresh value",
            "updated_at": "2026-04-26T01:00:00+00:00",
        },
    ]
    runtime_state_row = {"state": {"booking_context": {"destination": "Tokyo"}}}
    class _FakeTable:
        def __init__(self, name: str) -> None:
            self.name = name
            self.filters: list[tuple[str, str, object]] = []
            self._mode = "select"
            self.payload = None

        def select(self, *_args, **_kwargs):
            self._mode = "select"
            return self

        def eq(self, key, value):
            self.filters.append(("eq", key, value))
            return self

        def gte(self, key, value):
            self.filters.append(("gte", key, value))
            return self

        def is_(self, key, value):
            self.filters.append(("is", key, value))
            return self

        def limit(self, *_args, **_kwargs):
            return self

        def order(self, *_args, **_kwargs):
            return self

        def upsert(self, payload):
            self._mode = "upsert"
            self.payload = payload
            if self.name == "workspaces":
                stored_workspace.update(payload)
            elif self.name == "workspace_runtime_state":
                runtime_state_row.update(payload)
            return self

        def delete(self):
            self._mode = "delete"
            return self

        def execute(self):
            if self.name == "workspaces":
                return SimpleNamespace(data=[stored_workspace.copy()])
            if self.name == "workspace_runtime_state":
                return SimpleNamespace(data=[runtime_state_row.copy()])
            if self.name == "conversation_events":
                data = stored_events
                for op, key, value in self.filters:
                    if op == "gte":
                        data = [row for row in data if row.get(key, "") >= value]
                return SimpleNamespace(data=data)
            if self.name == "memory_entries":
                data = stored_memory
                for op, key, value in self.filters:
                    if op == "gte":
                        data = [row for row in data if row.get(key, "") >= value]
                return SimpleNamespace(data=data)
            return SimpleNamespace(data=[])

    monkeypatch.setattr(
        "backend.services.workspace_runtime.supabase_storage",
        SimpleNamespace(client=SimpleNamespace(table=lambda name: _FakeTable(name))),
    )

    restarted = await workspace_runtime.restart_workspace("telegram:-100:main", title="Fresh Workspace")
    started_at = restarted["data"]["started_at"]
    stored_events[1]["created_at"] = started_at
    stored_memory[1]["updated_at"] = started_at

    events = await workspace_runtime.list_events("telegram:-100:main")
    memory = await workspace_runtime.list_memory("telegram:-100:main")

    assert restarted["trip_id"].startswith("trip_")
    assert restarted["data"]["created_at"] == "2026-04-24T00:00:00+00:00"
    assert runtime_state_row["state"] == {}
    assert [event["content"] for event in events] == ["fresh event"]
    assert memory == {"fresh_key": "fresh value"}


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
