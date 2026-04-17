from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import BackgroundTasks, HTTPException

from backend.models.schemas import (
    Accommodation,
    Day,
    GeminiAnalysisResult,
    POI,
    SourceVideo,
    Trip,
    VideoProcessRequest,
)
from backend.routers import videos as videos_router


def _make_trip() -> Trip:
    return Trip(
        trip_id="trip_test_video_success",
        title="Test Trip",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://example.com/video",
                title="Test Video",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    POI(
                        id="poi_1",
                        name="Queenstown Lakefront",
                        category="Nature",
                        coords=(168.6626, -45.0312),
                        img="https://example.com/queenstown.jpg",
                        time_slot="09:00 - 11:00",
                        vibe="Scenic lake views",
                        priority="high",
                        intensity="low",
                        visit_duration=90,
                    )
                ],
            )
        ],
        accommodation=Accommodation(
            name="Queenstown Hotel",
            price_per_night=200.0,
            status="Mock Data - Booking not implemented yet",
            img="https://example.com/hotel.jpg",
            coords=(168.6626, -45.0312),
        ),
    )


def _patch_pipeline(
    monkeypatch: pytest.MonkeyPatch,
    *,
    analysis_results: list[GeminiAnalysisResult],
    trip: Trip | None = None,
) -> tuple[SimpleNamespace, SimpleNamespace]:
    downloader = SimpleNamespace(
        download_multiple=AsyncMock(
            return_value=[
                {
                    "success": True,
                    "file_path": "/tmp/test-video.mp4",
                    "title": "Test Video",
                    "platform": "tiktok",
                }
            ]
        ),
        cleanup_video=AsyncMock(),
    )
    analyzer = SimpleNamespace(
        analyze_multiple_videos=AsyncMock(return_value=analysis_results)
    )
    builder = SimpleNamespace(build_itinerary=AsyncMock(return_value=trip or _make_trip()))
    storage = SimpleNamespace(save_trip=AsyncMock(return_value=True))

    monkeypatch.setattr(videos_router, "video_downloader", downloader)
    monkeypatch.setattr(videos_router, "gemini_analyzer", analyzer)
    monkeypatch.setattr(videos_router, "itinerary_builder", builder)
    monkeypatch.setattr(videos_router, "storage", storage)

    return builder, storage


@pytest.mark.asyncio
async def test_process_videos_rejects_upstream_analysis_errors_when_no_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder, storage = _patch_pipeline(
        monkeypatch,
        analysis_results=[
            GeminiAnalysisResult(
                locations=[],
                activities=[],
                vibes=[],
                metadata={"error": "API key not valid. Please pass a valid API key."},
            )
        ],
    )

    request = VideoProcessRequest(urls=["https://example.com/video"])

    with pytest.raises(HTTPException) as exc_info:
        await videos_router.process_videos(request, BackgroundTasks())

    assert exc_info.value.status_code == 502
    assert "Gemini" in exc_info.value.detail
    builder.build_itinerary.assert_not_called()
    storage.save_trip.assert_not_called()


@pytest.mark.asyncio
async def test_process_videos_rejects_empty_analysis_without_saving_blank_trip(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder, storage = _patch_pipeline(
        monkeypatch,
        analysis_results=[
            GeminiAnalysisResult(
                locations=[],
                activities=["scenic views"],
                vibes=["relaxing"],
                metadata={"city": "Queenstown", "confidence": "low"},
            )
        ],
    )

    request = VideoProcessRequest(urls=["https://example.com/video"])

    with pytest.raises(HTTPException) as exc_info:
        await videos_router.process_videos(request, BackgroundTasks())

    assert exc_info.value.status_code == 422
    assert "No travel locations" in exc_info.value.detail
    builder.build_itinerary.assert_not_called()
    storage.save_trip.assert_not_called()


@pytest.mark.asyncio
async def test_process_videos_still_succeeds_when_locations_are_extracted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    builder, storage = _patch_pipeline(
        monkeypatch,
        analysis_results=[
            GeminiAnalysisResult(
                locations=[
                    {
                        "name": "Queenstown Lakefront",
                        "type": "Nature",
                        "description": "Scenic lake views",
                    }
                ],
                activities=["sightseeing"],
                vibes=["relaxing"],
                metadata={"city": "Queenstown", "confidence": "high"},
            )
        ],
    )

    request = VideoProcessRequest(urls=["https://example.com/video"])
    response = await videos_router.process_videos(request, BackgroundTasks())

    assert response.status == "completed"
    assert response.trip is not None
    builder.build_itinerary.assert_awaited_once()
    storage.save_trip.assert_awaited_once()
