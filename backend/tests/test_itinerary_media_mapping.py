from unittest.mock import AsyncMock

import pytest

from backend.models.schemas import GeminiAnalysisResult
from backend.services.itinerary_builder import ItineraryBuilderService


@pytest.mark.asyncio
async def test_build_itinerary_attaches_source_media_to_each_poi(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
        return {
            "coords": [139.7, 35.6],
            "full_name": f"{name}, Tokyo, Japan",
            "address": f"{name}, Tokyo, Japan",
            "img": "https://example.com/place.jpg",
            "country_code": "jp",
            "country": "Japan",
            "locality": "Tokyo",
        }

    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.geocode_location",
        AsyncMock(side_effect=fake_geocode),
    )
    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.get_place_image",
        AsyncMock(return_value="https://example.com/place.jpg"),
    )

    trip = await service.build_itinerary(
        video_data=[
            {
                "url": "https://instagram.com/reel/abc",
                "title": "Tokyo cafe reel",
                "platform": "instagram",
                "preview_url": "http://127.0.0.1:8000/media/abc.mp4",
            },
            {
                "url": "https://youtube.com/watch?v=tokyo123",
                "title": "Tokyo tower short",
                "platform": "youtube",
            },
        ],
        analysis_results=[
            GeminiAnalysisResult(
                locations=[{"name": "Koffee Mameya", "type": "Food", "description": "Coffee stop"}],
                activities=[],
                vibes=[],
                metadata={"city": "Tokyo", "country": "Japan", "confidence": "high"},
            ),
            GeminiAnalysisResult(
                locations=[{"name": "Tokyo Tower", "type": "Culture", "description": "Landmark"}],
                activities=[],
                vibes=[],
                metadata={"city": "Tokyo", "country": "Japan", "confidence": "high"},
            ),
        ],
    )

    poi_map = {poi.name: poi for day in trip.days for poi in day.pois}

    assert poi_map["Koffee Mameya"].media_urls == ["https://instagram.com/reel/abc"]
    assert poi_map["Tokyo Tower"].media_urls == ["https://youtube.com/watch?v=tokyo123"]
    assert trip.source_videos[0].preview_url == "http://127.0.0.1:8000/media/abc.mp4"
