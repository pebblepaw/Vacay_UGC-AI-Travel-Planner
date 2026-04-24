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
