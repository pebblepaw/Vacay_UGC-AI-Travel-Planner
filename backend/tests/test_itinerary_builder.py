from unittest.mock import AsyncMock

import pytest

from backend.models.schemas import GeminiAnalysisResult
from backend.services.itinerary_builder import ItineraryBuilderService


@pytest.mark.asyncio
async def test_build_pois_drops_unresolved_locations_instead_of_saving_zero_coords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()

    async def fake_geocode(name: str, city_hint: str, scope=None):
        if name == "Wukang Building":
            return {
                "coords": [121.43746, 31.20518],
                "full_name": "Wukang Building, Shanghai, China",
                "address": "Wukang Building, Shanghai, China",
                "img": "",
                "country_code": "cn",
                "country": "China",
                "locality": "Shanghai",
            }
        return None

    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.geocode_location",
        AsyncMock(side_effect=fake_geocode),
    )
    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.get_place_image",
        AsyncMock(return_value="https://example.com/place.jpg"),
    )

    pois = await service._build_pois_from_locations(
        [
            {"name": "Wukang Building", "type": "Culture", "description": "Art deco icon"},
            {"name": "Apoli Itabakery", "type": "Food", "description": "Bakery stop"},
        ],
        city="Shanghai",
        scope={
            "scope_name": "Shanghai",
            "country": "China",
            "country_code": "cn",
            "scope_type": "city",
            "query_hint": "Shanghai, China",
        },
    )

    assert [poi.name for poi in pois] == ["Wukang Building"]
    assert pois[0].coords != (0.0, 0.0)


def test_extract_location_scope_prefers_city_when_all_videos_agree() -> None:
    service = ItineraryBuilderService()

    scope = service._extract_location_scope(
        [
            GeminiAnalysisResult(
                locations=[{"name": "Wukang Building"}],
                activities=[],
                vibes=[],
                metadata={"city": "Shanghai", "country": "China", "confidence": "high"},
            ),
            GeminiAnalysisResult(
                locations=[{"name": "To Summer"}],
                activities=[],
                vibes=[],
                metadata={"city": "Shanghai", "country": "China", "confidence": "high"},
            ),
        ]
    )

    assert scope["scope_name"] == "Shanghai"
    assert scope["country"] == "China"
    assert scope["country_code"] == "cn"
    assert scope["scope_type"] == "city"


def test_extract_location_scope_falls_back_to_country_when_city_is_missing() -> None:
    service = ItineraryBuilderService()

    scope = service._extract_location_scope(
        [
            GeminiAnalysisResult(
                locations=[{"name": "Doubtful Sound"}],
                activities=[],
                vibes=[],
                metadata={"country": "New Zealand", "confidence": "high"},
            )
        ]
    )

    assert scope["scope_name"] == "New Zealand"
    assert scope["country"] == "New Zealand"
    assert scope["country_code"] == "nz"
    assert scope["scope_type"] == "country"
