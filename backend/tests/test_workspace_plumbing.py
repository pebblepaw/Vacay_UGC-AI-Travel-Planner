from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langchain_core.messages import AIMessage

from backend.models.schemas import (
    Accommodation,
    ChatMessage,
    ChatOption,
    ChatResponse,
    Day,
    POI,
    SourceVideo,
    TelegramWebhookRequest,
    Trip,
    VideoProcessRequest,
    WorkspaceChatRequest,
)
from backend.routers import telegram as telegram_router
from backend.routers import workspaces as workspaces_router
from backend.services.workspace_runtime import workspace_runtime


@pytest.fixture(autouse=True)
def _reset_runtime_state():
    workspace_runtime._memory_events.clear()
    workspace_runtime._memory_state.clear()


def _make_trip(trip_id: str = "trip_ws_bind") -> Trip:
    return Trip(
        trip_id=trip_id,
        title="Workspace Bound Trip",
        source_videos=[
            SourceVideo(
                platform="youtube",
                url="https://youtube.com/watch?v=abc123",
                title="Tokyo Clip",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    POI(
                        id="poi1",
                        name="Tokyo Tower",
                        category="Culture",
                        coords=(139.7454, 35.6586),
                        img="https://example.com/tower.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Iconic skyline",
                        priority="high",
                        intensity="normal",
                        visit_duration=90,
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


def _make_empty_trip(trip_id: str = "trip_ws_empty") -> Trip:
    return Trip(
        trip_id=trip_id,
        title="Workspace Shell Trip",
        source_videos=[],
        days=[],
        accommodation=Accommodation(
            name="Add media or ask for flights to begin",
            price_per_night=0,
            status="Pending",
            img="https://placehold.co/600x400/f5ede8/372f2f?text=VacayClaw",
            coords=(0.0, 0.0),
        ),
    )


@pytest.mark.asyncio
async def test_workspace_import_binds_real_trip_then_snapshot(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10011:main"
    trip = _make_trip("trip_import_bound")

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://youtube.com/watch?v=abc123",
                        "file_path": "/tmp/video.mp4",
                        "title": "Clip",
                        "platform": "youtube",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(analyze_multiple_videos=AsyncMock(return_value=[SimpleNamespace(locations=[{"name": "Tokyo Tower"}], metadata={})])),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(return_value=trip)),
    )

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )

    await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://youtube.com/watch?v=abc123"]),
    )
    snapshot = await workspaces_router.get_workspace_snapshot(workspace_id, token=None)

    assert snapshot.trip.trip_id == trip.trip_id


@pytest.mark.asyncio
async def test_workspace_chat_attach_binds_real_trip_then_snapshot(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10022:main"
    trip = _make_trip("trip_chat_bound")

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "app",
        SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "messages": [AIMessage(content="Done")],
                    "trip": trip,
                    "chat_interrupt": None,
                    "booking_context": None,
                    "booking_offers": None,
                    "selected_offer": None,
                    "booking_result": None,
                }
            )
        ),
    )

    await workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(workspace_id, "plan flights", user_id="1", source="telegram")
    snapshot = await workspaces_router.get_workspace_snapshot(workspace_id, token=None)

    assert snapshot.trip.trip_id == trip.trip_id


@pytest.mark.asyncio
async def test_workspace_restart_command_starts_fresh_trip(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10088:main"

    saved_trips: list[Trip] = []

    async def _save_trip(trip: Trip):
        saved_trips.append(trip)
        return True

    async def _load_trip(trip_id: str):
        for trip in reversed(saved_trips):
            if trip.trip_id == trip_id:
                return trip
        return None

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )

    response = await workspaces_router._invoke_workspace_agent(
        workspace_id,
        "start over with a fresh trip",
        user_id="1",
        source="telegram",
    )
    snapshot = await workspaces_router.get_workspace_snapshot(workspace_id, token=None)

    assert response.messages[0].content.startswith("Started a fresh trip workspace")
    assert saved_trips
    assert snapshot.trip.trip_id == saved_trips[-1].trip_id


@pytest.mark.asyncio
async def test_workspace_restart_endpoint_returns_new_snapshot(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10089:main"
    saved_trips: list[Trip] = []

    async def _save_trip(trip: Trip):
        saved_trips.append(trip)
        return True

    async def _load_trip(trip_id: str):
        for trip in reversed(saved_trips):
            if trip.trip_id == trip_id:
                return trip
        return None

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )

    response = await workspaces_router.restart_workspace_trip(workspace_id)

    assert response["workspace_id"] == workspace_id
    assert response["trip_id"] == saved_trips[-1].trip_id
    assert response["snapshot"]["trip"]["trip_id"] == saved_trips[-1].trip_id


@pytest.mark.asyncio
async def test_workspace_chat_rebuilds_snapshot_after_agent_run(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10044:main"
    trip = _make_trip("trip_snapshot_refresh")

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    snapshot_builder = AsyncMock(
        return_value={
            "workspace_id": workspace_id,
            "trip": trip.model_dump(mode="json"),
            "media_by_place": {},
            "runtime_state": {},
            "workspace_memory": {},
            "recent_events": [],
            "updated_at": "2026-04-25T00:00:00Z",
        }
    )

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "app",
        SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "messages": [AIMessage(content="Done")],
                    "trip": trip,
                    "chat_interrupt": None,
                    "booking_context": None,
                    "booking_offers": None,
                    "selected_offer": None,
                    "booking_result": None,
                }
            )
        ),
    )
    monkeypatch.setattr(workspaces_router.workspace_runtime, "build_workspace_snapshot", snapshot_builder)
    monkeypatch.setattr(workspaces_router.workspace_runtime, "ensure_workspace", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "get_workspace_trip_id", AsyncMock(return_value=trip.trip_id))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "load_runtime_state", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "save_runtime_state", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "append_event", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "list_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "list_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "bind_workspace_to_trip", AsyncMock(return_value=None))

    await workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(workspace_id, "plan flights", user_id="1", source="telegram")

    snapshot_builder.assert_awaited_once_with(workspace_id, trip)
    workspaces_router.app.ainvoke.assert_awaited_once()
    _, kwargs = workspaces_router.app.ainvoke.await_args
    thread_id = kwargs["config"]["configurable"]["thread_id"]
    assert thread_id.startswith(f"{workspace_id}:turn_")
    assert thread_id != workspace_id


@pytest.mark.asyncio
async def test_workspace_chat_clears_stale_langgraph_state_before_agent_run(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10045:main"
    trip = _make_trip("trip_clear_langgraph")

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    clear_mock = AsyncMock(return_value=None)

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(workspaces_router.workspace_runtime, "clear_langgraph_state", clear_mock)
    monkeypatch.setattr(
        workspaces_router,
        "app",
        SimpleNamespace(
            ainvoke=AsyncMock(
                return_value={
                    "messages": [AIMessage(content="Done")],
                    "trip": trip,
                    "chat_interrupt": None,
                    "booking_context": None,
                    "booking_offers": None,
                    "selected_offer": None,
                    "booking_result": None,
                }
            )
        ),
    )

    await workspaces_router.workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(workspace_id, "book flights", user_id="1", source="telegram")

    clear_mock.assert_awaited_once_with(workspace_id)


@pytest.mark.asyncio
async def test_workspace_chat_uses_fresh_langgraph_thread_per_turn(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10045:main"
    trip = _make_trip("trip_fresh_thread")
    seen_thread_ids: list[str] = []

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    async def _ainvoke(initial_state, config):
        seen_thread_ids.append(config["configurable"]["thread_id"])
        return {
            "messages": [AIMessage(content="Done")],
            "trip": trip,
            "chat_interrupt": None,
            "booking_context": None,
            "booking_offers": None,
            "selected_offer": None,
            "booking_result": None,
        }

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(workspaces_router, "app", SimpleNamespace(ainvoke=AsyncMock(side_effect=_ainvoke)))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "ensure_workspace", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "get_workspace_trip_id", AsyncMock(return_value=trip.trip_id))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "load_runtime_state", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "save_runtime_state", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "append_event", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "build_workspace_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "list_events", AsyncMock(return_value=[]))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "list_memory", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "bind_workspace_to_trip", AsyncMock(return_value=None))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "clear_langgraph_state", AsyncMock(return_value=None))

    await workspaces_router.workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(workspace_id, "plan flights", user_id="1", source="telegram")
    await workspaces_router._invoke_workspace_agent(workspace_id, "shrink it to 2 days", user_id="1", source="telegram")

    assert len(seen_thread_ids) == 2
    assert seen_thread_ids[0] != seen_thread_ids[1]
    assert all(thread_id.startswith(f"{workspace_id}:turn_") for thread_id in seen_thread_ids)


@pytest.mark.asyncio
async def test_workspace_chat_clears_stale_booking_retry_state_for_fresh_search(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10046:main"
    trip = _make_trip("trip_clear_booking_retry")
    captured: dict[str, dict] = {}

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    async def _ainvoke(initial_state, config):
        captured["initial_state"] = initial_state
        return {
            "messages": [AIMessage(content="Done")],
            "trip": trip,
            "chat_interrupt": None,
            "booking_context": initial_state.get("booking_context"),
            "booking_offers": initial_state.get("booking_offers"),
            "selected_offer": initial_state.get("selected_offer"),
            "booking_result": initial_state.get("booking_result"),
        }

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "load_runtime_state",
        AsyncMock(
            return_value={
                "booking_context": {"checkout_status": "failed", "selected_offer_id": "offer_4"},
                "booking_offers": [{"id": "offer_4"}],
                "selected_offer": {"id": "offer_4"},
                "booking_result": {"status": "failed"},
            }
        ),
    )
    monkeypatch.setattr(workspaces_router, "app", SimpleNamespace(ainvoke=AsyncMock(side_effect=_ainvoke)))

    await workspaces_router.workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(
        workspace_id,
        "Book a flight to Sydney for 2 pax, on the weekend of 2nd to 4th May",
        user_id="1",
        source="telegram",
    )

    assert captured["initial_state"]["booking_context"] == {}
    assert captured["initial_state"]["booking_offers"] == []
    assert captured["initial_state"]["selected_offer"] == {}
    assert captured["initial_state"]["booking_result"] == {}


@pytest.mark.asyncio
async def test_workspace_chat_creates_fresh_trip_when_workspace_is_unbound(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10055:main"
    saved: dict[str, Trip] = {}
    captured: dict[str, Trip] = {}

    async def _load_trip(trip_id: str):
        return saved.get(trip_id)

    async def _save_trip(trip: Trip):
        saved[trip.trip_id] = trip
        return True

    async def _ainvoke(initial_state, config):
        captured["trip"] = initial_state["trip"]
        return {
            "messages": [AIMessage(content="Done")],
            "trip": initial_state["trip"],
            "chat_interrupt": None,
            "booking_context": None,
            "booking_offers": None,
            "selected_offer": None,
            "booking_result": None,
        }

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(
                return_value=[
                    _make_trip("placeholder-welcome"),
                ]
            ),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(workspaces_router, "app", SimpleNamespace(ainvoke=AsyncMock(side_effect=_ainvoke)))

    await workspace_runtime.ensure_workspace(workspace_id)
    await workspaces_router._invoke_workspace_agent(workspace_id, "hello", user_id="1", source="telegram")

    assert captured["trip"].trip_id != "placeholder-welcome"
    assert captured["trip"].source_videos == []
    assert captured["trip"].days == []


@pytest.mark.asyncio
async def test_workspace_ingest_preserves_original_url_after_partial_failure(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10033:main"

    capture: dict = {}

    async def _build(video_data, analysis_results, trip_title):
        capture["video_data"] = video_data
        return _make_trip("trip_url_preserve").model_copy(
            update={
                "source_videos": [
                    SourceVideo(platform="youtube", url=video_data[0]["url"], title="Saved URL")
                ]
            }
        )

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": False,
                        "url": "https://bad.example/video1",
                        "error": "boom",
                        "title": "Bad",
                        "platform": "youtube",
                    },
                    {
                        "success": True,
                        "url": "https://youtube.com/watch?v=good2",
                        "file_path": "/tmp/good2.mp4",
                        "title": "Good",
                        "platform": "youtube",
                    },
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(analyze_multiple_videos=AsyncMock(return_value=[SimpleNamespace(locations=[{"name": "Tokyo Tower"}], metadata={})])),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(side_effect=_build)),
    )

    saved = {}

    async def _save_trip(trip: Trip):
        saved["trip"] = trip
        return True

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(return_value=None),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )

    await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://bad.example/video1", "https://youtube.com/watch?v=good2"]),
    )

    assert capture["video_data"][0]["url"] == "https://youtube.com/watch?v=good2"
    assert saved["trip"].source_videos[0].url == "https://youtube.com/watch?v=good2"


@pytest.mark.asyncio
async def test_workspace_existing_trip_ingest_stashes_pending_candidates_without_appending_days(
    monkeypatch: pytest.MonkeyPatch,
):
    workspace_id = "telegram:-10066:main"
    existing_trip = _make_trip("trip_existing_workspace")
    imported_trip = Trip(
        trip_id="trip_pending_candidate",
        title="Imported Candidate Trip",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/cinema",
                title="Cinema clip",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-02",
                pois=[
                    POI(
                        id="poi_pending_cinema",
                        name="Golden Age Cinema",
                        category="Culture",
                        coords=(151.2093, -33.8688),
                        img="https://example.com/cinema.jpg",
                        time_slot="19:00 - 21:00",
                        vibe="Art deco cinema from the caption",
                        priority="normal",
                        intensity="low",
                        visit_duration=120,
                        media_urls=["https://www.tiktok.com/@demo/video/cinema"],
                    )
                ],
            )
        ],
        accommodation=existing_trip.accommodation,
    )

    saved_trip: dict[str, Trip] = {}
    saved_runtime_state: dict[str, dict] = {}

    async def _load_trip(trip_id: str):
        if trip_id == existing_trip.trip_id:
            return existing_trip
        return None

    async def _save_trip(trip: Trip):
        saved_trip["trip"] = trip
        return True

    async def _save_runtime_state(_workspace_id: str, state: dict):
        saved_runtime_state["state"] = state

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://www.tiktok.com/@demo/video/cinema",
                        "file_path": "/tmp/cinema.mp4",
                        "title": "Cinema clip",
                        "platform": "tiktok",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(
            analyze_multiple_videos=AsyncMock(
                return_value=[SimpleNamespace(locations=[{"name": "Golden Age Cinema"}], metadata={})]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(return_value=imported_trip)),
    )
    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[existing_trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=_save_runtime_state),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "get_workspace_trip_id",
        AsyncMock(return_value=existing_trip.trip_id),
    )

    result = await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://www.tiktok.com/@demo/video/cinema"]),
    )

    assert result["trip_id"] == existing_trip.trip_id
    assert len(saved_trip["trip"].days) == len(existing_trip.days)
    assert saved_trip["trip"].days[0].pois[0].name == existing_trip.days[0].pois[0].name
    assert any(video.url == "https://www.tiktok.com/@demo/video/cinema" for video in saved_trip["trip"].source_videos)
    assert saved_runtime_state["state"]["pending_import_candidates"][0]["name"] == "Golden Age Cinema"


@pytest.mark.asyncio
async def test_workspace_import_replaces_empty_shell_trip_with_built_itinerary(
    monkeypatch: pytest.MonkeyPatch,
):
    workspace_id = "telegram:-10066:main"
    existing_trip = _make_empty_trip("trip_empty_shell")
    imported_trip = _make_trip("trip_imported_seed")
    saved_trip: dict[str, Trip] = {}

    async def _load_trip(trip_id: str):
        if trip_id == existing_trip.trip_id:
            return existing_trip
        if trip_id == imported_trip.trip_id:
            return imported_trip
        return None

    async def _save_trip(trip: Trip):
        saved_trip["trip"] = trip
        return True

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://www.tiktok.com/@demo/video/seed",
                        "file_path": "/tmp/seed.mp4",
                        "title": "Seed clip",
                        "platform": "tiktok",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(
            analyze_multiple_videos=AsyncMock(
                return_value=[SimpleNamespace(locations=[{"name": "Tokyo Tower"}], metadata={})]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(return_value=imported_trip)),
    )
    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[existing_trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "get_workspace_trip_id",
        AsyncMock(return_value=existing_trip.trip_id),
    )
    monkeypatch.setattr(workspaces_router.workspace_runtime, "save_runtime_state", AsyncMock())
    monkeypatch.setattr(workspaces_router.workspace_runtime, "append_event", AsyncMock())
    monkeypatch.setattr(workspaces_router.workspace_runtime, "build_workspace_snapshot", AsyncMock(return_value={}))
    monkeypatch.setattr(workspaces_router.workspace_runtime, "bind_workspace_to_trip", AsyncMock())

    result = await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://www.tiktok.com/@demo/video/seed"]),
    )

    assert result["trip_id"] == existing_trip.trip_id
    assert saved_trip["trip"].trip_id == existing_trip.trip_id
    assert len(saved_trip["trip"].days) == 1
    assert saved_trip["trip"].days[0].pois[0].name == "Tokyo Tower"


@pytest.mark.asyncio
async def test_workspace_existing_trip_ingest_keeps_raw_caption_candidate_even_if_import_trip_drops_it(
    monkeypatch: pytest.MonkeyPatch,
):
    workspace_id = "telegram:-10067:main"
    existing_trip = _make_trip("trip_existing_workspace_caption")
    imported_trip = Trip(
        trip_id="trip_pending_caption",
        title="Imported Candidate Trip",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/cinema",
                title="Cinema clip",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-02",
                pois=[
                    POI(
                        id="poi_bridge",
                        name="Sydney Harbour Bridge",
                        category="Culture",
                        coords=(151.2108, -33.8523),
                        img="https://example.com/bridge.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Bridge view from the clip",
                        priority="normal",
                        intensity="normal",
                        visit_duration=90,
                        media_urls=["https://www.tiktok.com/@demo/video/cinema"],
                    )
                ],
            )
        ],
        accommodation=existing_trip.accommodation,
    )

    saved_runtime_state: dict[str, dict] = {}

    async def _load_trip(trip_id: str):
        if trip_id == existing_trip.trip_id:
            return existing_trip
        return None

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://www.tiktok.com/@demo/video/cinema",
                        "file_path": "/tmp/cinema.mp4",
                        "title": "Cinema clip",
                        "platform": "tiktok",
                        "description": "Westpac Open Air cinema",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(
            analyze_multiple_videos=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        locations=[
                            {
                                "name": "Westpac Open Air cinema",
                                "type": "Culture",
                                "description": "Cinema from the caption",
                                "priority": "high",
                                "intensity": "low",
                                "visit_duration": 120,
                            },
                            {
                                "name": "Sydney Harbour Bridge",
                                "type": "Culture",
                                "description": "Bridge view from the clip",
                            },
                        ],
                        metadata={"city": "Sydney", "country": "Australia", "scope_type": "city"},
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(return_value=imported_trip)),
    )
    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[existing_trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=lambda _workspace_id, state: saved_runtime_state.setdefault("state", state)),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "get_workspace_trip_id",
        AsyncMock(return_value=existing_trip.trip_id),
    )

    await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://www.tiktok.com/@demo/video/cinema"]),
    )

    pending_names = [candidate["name"] for candidate in saved_runtime_state["state"]["pending_import_candidates"]]
    assert "Westpac Open Air cinema" in pending_names
    assert "Sydney Harbour Bridge" in pending_names


@pytest.mark.asyncio
async def test_workspace_import_without_resolved_pois_falls_back_to_media_staging_trip(
    monkeypatch: pytest.MonkeyPatch,
):
    workspace_id = "telegram:-10068:main"
    saved_trip: dict[str, Trip] = {}
    saved_runtime_state: dict[str, dict] = {}

    async def _save_trip(trip: Trip):
        saved_trip["trip"] = trip
        return True

    async def _save_runtime_state(_workspace_id: str, state: dict):
        saved_runtime_state["state"] = state

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://www.tiktok.com/@demo/video/cinema",
                        "file_path": "/tmp/cinema.mp4",
                        "title": "Cinema clip",
                        "platform": "tiktok",
                        "description": "Westpac Open Air cinema",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(
            analyze_multiple_videos=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        locations=[
                            {
                                "name": "Westpac Open Air cinema",
                                "type": "Culture",
                                "description": "Cinema from the caption",
                            }
                        ],
                        metadata={"city": "Sydney", "country": "Australia", "scope_type": "city"},
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(side_effect=ValueError("No extracted locations could be resolved"))),
    )
    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(return_value=None),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=_save_runtime_state),
    )

    result = await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://www.tiktok.com/@demo/video/cinema"]),
    )

    assert result["imported_count"] == 1
    assert result["pending_candidates_count"] == 1
    assert saved_trip["trip"].days == []
    assert saved_trip["trip"].source_videos[0].url == "https://www.tiktok.com/@demo/video/cinema"
    assert saved_runtime_state["state"]["pending_import_candidates"][0]["name"] == "Westpac Open Air cinema"


@pytest.mark.asyncio
async def test_workspace_import_keeps_only_candidates_not_already_in_new_trip(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10069:main"
    imported_trip = Trip(
        trip_id="trip_partial_import",
        title="Imported Candidate Trip",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/cinema",
                title="Cinema clip",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-02",
                pois=[
                    POI(
                        id="poi_bridge",
                        name="Sydney Harbour Bridge",
                        category="Culture",
                        coords=(151.2108, -33.8523),
                        img="https://example.com/bridge.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Bridge view from the clip",
                        priority="normal",
                        intensity="normal",
                        visit_duration=90,
                        media_urls=["https://www.tiktok.com/@demo/video/cinema"],
                    )
                ],
            )
        ],
        accommodation=_make_trip("trip_seed").accommodation,
    )
    saved_runtime_state: dict[str, dict] = {}

    monkeypatch.setattr(
        workspaces_router,
        "video_downloader",
        SimpleNamespace(
            download_multiple=AsyncMock(
                return_value=[
                    {
                        "success": True,
                        "url": "https://www.tiktok.com/@demo/video/cinema",
                        "file_path": "/tmp/cinema.mp4",
                        "title": "Cinema clip",
                        "platform": "tiktok",
                        "description": "Westpac Open Air cinema",
                    }
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "gemini_analyzer",
        SimpleNamespace(
            analyze_multiple_videos=AsyncMock(
                return_value=[
                    SimpleNamespace(
                        locations=[
                            {"name": "Westpac Open Air cinema", "type": "Culture", "description": "Cinema from caption"},
                            {"name": "Sydney Harbour Bridge", "type": "Culture", "description": "Bridge view"},
                        ],
                        metadata={"city": "Sydney", "country": "Australia", "scope_type": "city"},
                    )
                ]
            )
        ),
    )
    monkeypatch.setattr(
        workspaces_router,
        "itinerary_builder",
        SimpleNamespace(build_itinerary=AsyncMock(return_value=imported_trip)),
    )
    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(return_value=None),
            save_trip=AsyncMock(return_value=True),
            list_all_trips=AsyncMock(return_value=[]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=lambda _workspace_id, state: saved_runtime_state.setdefault("state", state)),
    )

    result = await workspaces_router.process_workspace_videos(
        workspace_id,
        VideoProcessRequest(urls=["https://www.tiktok.com/@demo/video/cinema"]),
    )

    assert result["pending_candidates_count"] == 1
    assert saved_runtime_state["state"]["pending_import_candidates"][0]["name"] == "Westpac Open Air cinema"


@pytest.mark.asyncio
async def test_workspace_chat_adds_pending_import_candidate_without_graph(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10077:main"
    trip = _make_trip("trip_pending_add")
    saved_runtime_state: dict[str, dict] = {}
    saved_trip: dict[str, Trip] = {}

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    async def _save_trip(updated_trip: Trip):
        saved_trip["trip"] = updated_trip
        return True

    async def _save_runtime_state(_workspace_id: str, state: dict):
        saved_runtime_state["state"] = state

    pending_candidate = {
        "id": "poi_pending_cinema",
        "name": "Golden Age Cinema",
        "category": "Culture",
        "coords": [151.2093, -33.8688],
        "img": "https://example.com/cinema.jpg",
        "time_slot": "19:00 - 21:00",
        "vibe": "Art deco cinema from the caption",
        "priority": "normal",
        "intensity": "low",
        "visit_duration": 120,
        "media_urls": ["https://www.tiktok.com/@demo/video/cinema"],
    }

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "load_runtime_state",
        AsyncMock(return_value={"pending_import_candidates": [pending_candidate]}),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=_save_runtime_state),
    )
    monkeypatch.setattr(
        workspaces_router,
        "app",
        SimpleNamespace(ainvoke=AsyncMock(side_effect=AssertionError("graph should not run"))),
    )

    response = await workspaces_router._invoke_workspace_agent(
        workspace_id=workspace_id,
        message="Add this cinema",
        user_id="55",
        source="telegram",
    )

    added_names = [poi.name for day in saved_trip["trip"].days for poi in day.pois]
    assert "Golden Age Cinema" in added_names
    assert saved_runtime_state["state"]["pending_import_candidates"] == []
    assert any(msg.type == "agent" and "Golden Age Cinema" in msg.content for msg in response.messages)


@pytest.mark.asyncio
async def test_workspace_chat_resolves_pending_candidate_without_coords(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10078:main"
    trip = _make_trip("trip_pending_geo")
    saved_runtime_state: dict[str, dict] = {}
    saved_trip: dict[str, Trip] = {}

    async def _load_trip(trip_id: str):
        if trip_id == trip.trip_id:
            return trip
        return None

    async def _save_trip(updated_trip: Trip):
        saved_trip["trip"] = updated_trip
        return True

    async def _save_runtime_state(_workspace_id: str, state: dict):
        saved_runtime_state["state"] = state

    pending_candidate = {
        "name": "Westpac Open Air cinema",
        "category": "Culture",
        "coords": [],
        "img": "",
        "time_slot": "19:00 - 21:00",
        "vibe": "Cinema from the caption",
        "priority": "high",
        "intensity": "low",
        "visit_duration": 120,
        "media_urls": ["https://www.tiktok.com/@demo/video/cinema"],
        "query_hint": "Sydney, Australia",
        "scope": {
            "scope_name": "Sydney",
            "country": "Australia",
            "country_code": "au",
            "scope_type": "city",
            "query_hint": "Sydney, Australia",
        },
        "source_title": "Cinema clip",
        "source_caption": "Doesn’t get any better than Westpac Open Air cinema",
        "raw_type": "Culture",
    }

    monkeypatch.setattr(
        workspaces_router,
        "storage",
        SimpleNamespace(
            load_trip=AsyncMock(side_effect=_load_trip),
            save_trip=AsyncMock(side_effect=_save_trip),
            list_all_trips=AsyncMock(return_value=[trip]),
            seed_placeholder_if_empty=AsyncMock(return_value=None),
        ),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "load_runtime_state",
        AsyncMock(return_value={"pending_import_candidates": [pending_candidate]}),
    )
    monkeypatch.setattr(
        workspaces_router.workspace_runtime,
        "save_runtime_state",
        AsyncMock(side_effect=_save_runtime_state),
    )
    monkeypatch.setattr(
        workspaces_router.tavily_location,
        "geocode_location",
        AsyncMock(return_value={"coords": [151.2205, -33.8639]}),
    )
    monkeypatch.setattr(
        workspaces_router.tavily_location,
        "get_place_image",
        AsyncMock(return_value="https://example.com/cinema.jpg"),
    )
    monkeypatch.setattr(
        workspaces_router,
        "app",
        SimpleNamespace(ainvoke=AsyncMock(side_effect=AssertionError("graph should not run"))),
    )

    response = await workspaces_router._invoke_workspace_agent(
        workspace_id=workspace_id,
        message="Add this cinema",
        user_id="55",
        source="telegram",
    )

    added_names = [poi.name for day in saved_trip["trip"].days for poi in day.pois]
    assert "Westpac Open Air cinema" in added_names
    assert saved_runtime_state["state"]["pending_import_candidates"] == []
    assert any(msg.type == "agent" and "Westpac Open Air cinema" in msg.content for msg in response.messages)


@pytest.mark.asyncio
async def test_telegram_webhook_sends_outbound_reply(monkeypatch: pytest.MonkeyPatch):
    chat_response = ChatResponse(
        messages=[
            ChatMessage(id="u1", type="user", content="hi", timestamp="2026-04-24T00:00:00Z"),
            ChatMessage(id="a1", type="agent", content="Try these flights", timestamp="2026-04-24T00:00:01Z"),
            ChatMessage(
                id="i1",
                type="interrupt",
                content="Pick one",
                timestamp="2026-04-24T00:00:02Z",
                options=[
                    ChatOption(id="o1", name="Flight A", price=200, description="A"),
                    ChatOption(id="o2", name="Flight B", price=260, description="B"),
                ],
            ),
        ],
        updated_trip=None,
    )

    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_WEBHOOK_SECRET", "sec")
    monkeypatch.setattr(telegram_router.settings, "PUBLIC_WEB_BASE_URL", "https://demo.vacay.ai")
    monkeypatch.setattr(telegram_router.settings, "TELEGRAM_BOT_TOKEN", "demo-token")
    send_mock = AsyncMock(return_value={"ok": True})
    monkeypatch.setattr(telegram_router.telegram_bot, "get_username", AsyncMock(return_value="VacayClawBot"))
    monkeypatch.setattr(telegram_router.telegram_bot, "send_message", send_mock)
    monkeypatch.setattr(telegram_router, "_invoke_workspace_agent", AsyncMock(return_value=chat_response))

    req = TelegramWebhookRequest(
        update_id=1,
        message={
            "text": "find flights",
            "chat": {"id": -10099, "title": "Vacay"},
            "from": {"id": 55},
            "message_thread_id": 777,
        },
    )

    result = await telegram_router.ingest_telegram_webhook(req, x_telegram_bot_api_secret_token="sec")

    assert result["status"] == "processed"
    assert result["sent_to_telegram"] is True
    send_mock.assert_awaited_once()
    payload = send_mock.await_args.kwargs
    assert payload["chat_id"] == -10099
    assert payload["message_thread_id"] == 777
    assert "Workspace:" in payload["text"]
    assert "Options:" in payload["text"]


@pytest.mark.asyncio
async def test_workspace_chat_mirrors_web_turn_back_to_telegram(monkeypatch: pytest.MonkeyPatch):
    workspace_id = "telegram:-10077:main"
    send_mock = AsyncMock(return_value={"ok": True})
    response = ChatResponse(
        messages=[
            ChatMessage(id="u1", type="user", content="Shrink it to 2 days", timestamp="2026-04-24T00:00:00Z"),
            ChatMessage(id="a1", type="agent", content="Resized trip to 2 days.", timestamp="2026-04-24T00:00:01Z"),
        ],
        updated_trip=None,
    )

    monkeypatch.setattr(workspaces_router, "_invoke_workspace_agent", AsyncMock(return_value=response))
    monkeypatch.setattr(workspaces_router, "telegram_bot", SimpleNamespace(enabled=True, send_message=send_mock), raising=False)

    result = await workspaces_router.send_workspace_message(
        workspace_id,
        WorkspaceChatRequest(message="Shrink it to 2 days", user_id="web-user-1", source="web"),
    )

    assert result.messages[1].content == "Resized trip to 2 days."
    assert send_mock.await_count == 2
    first_payload = send_mock.await_args_list[0].kwargs
    second_payload = send_mock.await_args_list[1].kwargs
    assert first_payload["chat_id"] == -10077
    assert first_payload["text"] == "Web user: Shrink it to 2 days"
    assert second_payload["chat_id"] == -10077
    assert "Resized trip to 2 days." in second_payload["text"]
