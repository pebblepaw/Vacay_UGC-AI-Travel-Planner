import asyncio
from unittest.mock import AsyncMock

import pytest

from backend.models.schemas import GeminiAnalysisResult
from backend.services.itinerary_builder import ItineraryBuilderService


@pytest.mark.asyncio
async def test_build_pois_drops_unresolved_locations_instead_of_saving_zero_coords(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
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


@pytest.mark.asyncio
async def test_build_itinerary_caps_candidate_pool_and_clusters_days(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()

    coord_map = {
        "Bondi Beach": [151.2743, -33.8915],
        "Coogee Beach": [151.2576, -33.9205],
        "Bronte Beach": [151.2653, -33.9033],
        "Icebergs Pool": [151.2820, -33.8910],
        "Opera House": [151.2153, -33.8568],
        "The Rocks": [151.2090, -33.8599],
        "Sydney Tower": [151.2070, -33.8708],
        "Darling Harbour": [151.2012, -33.8748],
        "Manly Beach": [151.2869, -33.7969],
        "Taronga Zoo": [151.2417, -33.8430],
        "Paddington Markets": [151.2305, -33.8845],
        "Newtown": [151.1793, -33.8981],
        "Low Priority Detour": [151.1500, -33.9500],
        "Another Detour": [151.3400, -33.7600],
    }

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
        coords = coord_map[name]
        return {
            "coords": coords,
            "full_name": f"{name}, Sydney, Australia",
            "address": f"{name}, Sydney, Australia",
            "img": "https://example.com/place.jpg",
            "country_code": "au",
            "country": "Australia",
            "locality": "Sydney",
        }

    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.geocode_location",
        AsyncMock(side_effect=fake_geocode),
    )
    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.get_place_image",
        AsyncMock(return_value="https://example.com/place.jpg"),
    )

    locations = [
        {"name": "Bondi Beach", "type": "Nature", "description": "Coastal icon"},
        {"name": "Bondi Beach", "type": "Nature", "description": "Seen again"},
        {"name": "Coogee Beach", "type": "Nature", "description": "Clifftop walk"},
        {"name": "Bronte Beach", "type": "Nature", "description": "Surf stop"},
        {"name": "Icebergs Pool", "type": "Nature", "description": "Swim stop"},
        {"name": "Opera House", "type": "Culture", "description": "Landmark"},
        {"name": "The Rocks", "type": "Culture", "description": "Historic quarter"},
        {"name": "Sydney Tower", "type": "Culture", "description": "Observation deck"},
        {"name": "Darling Harbour", "type": "Culture", "description": "Harbour walk"},
        {"name": "Manly Beach", "type": "Nature", "description": "Ferry day"},
        {"name": "Taronga Zoo", "type": "Nature", "description": "Zoo"},
        {"name": "Paddington Markets", "type": "Shopping", "description": "Market"},
        {"name": "Newtown", "type": "Nightlife", "description": "Evening strip"},
        {"name": "Low Priority Detour", "type": "Culture", "description": "Hidden gem", "priority": "low"},
        {"name": "Another Detour", "type": "Culture", "description": "Far away", "priority": "low"},
    ]

    trip = await service.build_itinerary(
        video_data=[{"url": "https://tiktok.com/1", "title": "Sydney", "platform": "tiktok"}],
        analysis_results=[
            GeminiAnalysisResult(
                locations=locations,
                activities=[],
                vibes=[],
                metadata={"city": "Sydney", "country": "Australia", "confidence": "high"},
            )
        ],
        trip_title="Sydney Demo",
    )

    assert len(trip.days) == 3
    all_names = [poi.name for day in trip.days for poi in day.pois]
    assert "Bondi Beach" in all_names
    assert "Low Priority Detour" not in all_names
    assert "Another Detour" not in all_names

    grouped_day_names = [{poi.name for poi in day.pois} for day in trip.days]
    assert any({"Bondi Beach", "Coogee Beach", "Bronte Beach", "Icebergs Pool"}.issubset(day_names) for day_names in grouped_day_names)
    assert any({"Opera House", "The Rocks", "Sydney Tower", "Darling Harbour"}.issubset(day_names) for day_names in grouped_day_names)


@pytest.mark.asyncio
async def test_build_pois_geocodes_ranked_locations_concurrently(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()
    active = 0
    max_active = 0

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        try:
            await asyncio.sleep(0.01)
            return {
                "coords": [151.2, -33.8],
                "full_name": f"{name}, Sydney, Australia",
                "address": f"{name}, Sydney, Australia",
                "img": "",
                "country_code": "au",
                "country": "Australia",
                "locality": "Sydney",
            }
        finally:
            active -= 1

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
            {"name": "Bondi Beach", "type": "Nature", "description": "Popular", "priority": "high"},
            {"name": "Coogee Beach", "type": "Nature", "description": "Popular"},
            {"name": "Opera House", "type": "Culture", "description": "Popular"},
            {"name": "Darling Harbour", "type": "Culture", "description": "Popular"},
        ],
        city="Sydney",
        scope={
            "scope_name": "Sydney",
            "country": "Australia",
            "country_code": "au",
            "scope_type": "city",
            "query_hint": "Sydney, Australia",
        },
    )

    assert [poi.name for poi in pois] == [
        "Bondi Beach",
        "Coogee Beach",
        "Opera House",
        "Darling Harbour",
    ]
    assert max_active > 1


@pytest.mark.asyncio
async def test_build_pois_uses_longer_import_geocode_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()
    captured_timeout: dict[str, float | None] = {}

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
        captured_timeout["value"] = timeout_seconds
        return {
            "coords": [151.2153, -33.8568],
            "full_name": f"{name}, Sydney, Australia",
            "address": f"{name}, Sydney, Australia",
            "img": "",
            "country_code": "au",
            "country": "Australia",
            "locality": "Sydney",
        }

    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.geocode_location",
        AsyncMock(side_effect=fake_geocode),
    )
    monkeypatch.setattr(
        "backend.services.itinerary_builder.tavily_location.get_place_image",
        AsyncMock(return_value="https://example.com/place.jpg"),
    )

    pois = await service._build_pois_from_locations(
        [{"name": "Westpac Open Air cinema", "type": "Culture", "description": "Open-air cinema"}],
        city="Sydney",
        scope={
            "scope_name": "Sydney",
            "country": "Australia",
            "country_code": "au",
            "scope_type": "city",
            "query_hint": "Sydney, Australia",
        },
    )

    assert len(pois) == 1
    assert captured_timeout["value"] == 15.0


@pytest.mark.asyncio
async def test_build_itinerary_uses_extra_day_instead_of_truncating_remote_cluster(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = ItineraryBuilderService()

    coord_map = {
        "Gordon’s Bay": [151.2253274, -33.8738008],
        "Observatory Hill": [151.2053568, -33.8597332],
        "Coogee Beach": [151.2576, -33.9205],
        "Darling Harbour": [151.1995619, -33.8675516],
        "Bronte Beach": [151.2653, -33.9033],
        "South end of Bondi Beach": [151.27399, -33.891296],
        "Icebergs Pool (Bondi)": [151.2820, -33.8910],
        "Blue Mountains": [150.3176131, -33.706152],
    }

    async def fake_geocode(name: str, city_hint: str, scope=None, timeout_seconds=None):
        coords = coord_map[name]
        return {
            "coords": coords,
            "full_name": f"{name}, Sydney, Australia",
            "address": f"{name}, Sydney, Australia",
            "img": "https://example.com/place.jpg",
            "country_code": "au",
            "country": "Australia",
            "locality": "Sydney",
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
        video_data=[{"url": "https://tiktok.com/sydney", "title": "Sydney", "platform": "tiktok"}],
        analysis_results=[
            GeminiAnalysisResult(
                locations=[
                    {"name": "Gordon’s Bay", "type": "Nature", "description": "Snorkel stop"},
                    {"name": "Observatory Hill", "type": "Culture", "description": "City view"},
                    {"name": "Coogee Beach", "type": "Nature", "description": "Beach"},
                    {"name": "Darling Harbour", "type": "Nightlife", "description": "Harbour"},
                    {"name": "Bronte Beach", "type": "Nature", "description": "Beach"},
                    {"name": "South end of Bondi Beach", "type": "Nature", "description": "Beach"},
                    {"name": "Icebergs Pool (Bondi)", "type": "Nature", "description": "Pool"},
                    {"name": "Blue Mountains", "type": "Nature", "description": "Day trip"},
                ],
                activities=[],
                vibes=[],
                metadata={"city": "Sydney", "country": "Australia", "confidence": "high"},
            )
        ],
    )

    all_names = [poi.name for day in trip.days for poi in day.pois]

    assert len(trip.days) == 3
    assert set(all_names) == set(coord_map)
    assert any({"Coogee Beach", "Bronte Beach", "South end of Bondi Beach", "Icebergs Pool (Bondi)"}.issubset({poi.name for poi in day.pois}) for day in trip.days)
