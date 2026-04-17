from unittest.mock import AsyncMock

import pytest

from backend.services import tavily_location as tavily_location_module
from backend.services.tavily_location import TavilyLocationService


@pytest.mark.asyncio
async def test_geocode_location_uses_tavily_address_with_mapbox_when_name_lookup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()

    monkeypatch.setattr(service, "_geocode_with_nominatim_structured", AsyncMock(return_value=None))
    monkeypatch.setattr(
        service,
        "_geocode_with_nominatim",
        AsyncMock(side_effect=[None, None]),
    )

    discover_candidates = AsyncMock(
        return_value=["139 Fernhill Road, Queenstown 9300, New Zealand"]
    )
    mapbox_geocode = AsyncMock(
        return_value={
            "coords": [168.633519, -45.038931],
            "full_name": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
            "address": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
            "img": "",
        }
    )

    monkeypatch.setattr(
        service,
        "_discover_location_candidates_with_tavily",
        discover_candidates,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_geocode_with_mapbox",
        mapbox_geocode,
        raising=False,
    )

    result = await service.geocode_location("The Nest, Kamana Lake House", "Queenstown")

    assert result is not None
    assert result["coords"] == [168.633519, -45.038931]
    discover_candidates.assert_awaited_once_with("The Nest, Kamana Lake House", "Queenstown")
    mapbox_geocode.assert_awaited_once_with(
        "139 Fernhill Road, Queenstown 9300, New Zealand",
        "Queenstown",
    )


@pytest.mark.asyncio
async def test_geocode_location_falls_back_to_nominatim_for_tavily_address_when_mapbox_misses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()

    monkeypatch.setattr(service, "_geocode_with_nominatim_structured", AsyncMock(return_value=None))
    nominatim_geocode = AsyncMock(
        side_effect=[
            None,
            None,
            {
                "coords": [168.633519, -45.038931],
                "full_name": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
                "address": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
                "img": "",
            },
        ]
    )
    monkeypatch.setattr(service, "_geocode_with_nominatim", nominatim_geocode)

    discover_candidates = AsyncMock(
        return_value=["139 Fernhill Road, Queenstown 9300, New Zealand"]
    )
    mapbox_geocode = AsyncMock(return_value=None)

    monkeypatch.setattr(
        service,
        "_discover_location_candidates_with_tavily",
        discover_candidates,
        raising=False,
    )
    monkeypatch.setattr(
        service,
        "_geocode_with_mapbox",
        mapbox_geocode,
        raising=False,
    )

    result = await service.geocode_location("The Nest, Kamana Lake House", "Queenstown")

    assert result is not None
    assert result["coords"] == [168.633519, -45.038931]
    discover_candidates.assert_awaited_once_with("The Nest, Kamana Lake House", "Queenstown")
    mapbox_geocode.assert_awaited_once_with(
        "139 Fernhill Road, Queenstown 9300, New Zealand",
        "Queenstown",
    )
    assert nominatim_geocode.await_count == 3


@pytest.mark.asyncio
async def test_geocode_with_mapbox_prefers_public_token_over_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()
    captured: dict[str, object] = {}

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "features": [
                    {
                        "place_type": ["address"],
                        "place_name": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
                        "center": [168.633519, -45.038931],
                    }
                ]
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params=None):
            captured["url"] = url
            captured["params"] = params or {}
            return FakeResponse()

    monkeypatch.setattr(tavily_location_module.httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient())
    monkeypatch.setattr(tavily_location_module.settings, "MAPBOX_PUBLIC", "pk.public-test-token")
    monkeypatch.setattr(tavily_location_module.settings, "MAPBOX_SECRET", "sk.secret-test-token")

    result = await service._geocode_with_mapbox("139 Fernhill Road, Queenstown", "Queenstown")

    assert result is not None
    assert captured["params"]["access_token"] == "pk.public-test-token"
