import asyncio
from unittest.mock import AsyncMock, call

import pytest

from backend.services import tavily_location as tavily_location_module
from backend.services.tavily_location import TavilyLocationService


@pytest.mark.asyncio
async def test_geocode_location_prefers_scoped_mapbox_before_nominatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()

    mapbox_geocode = AsyncMock(
        return_value={
            "coords": [151.2446, -33.9230],
            "full_name": "Coogee Beach, Sydney NSW, Australia",
            "address": "Coogee Beach, Sydney NSW, Australia",
            "img": "",
            "country_code": "au",
            "country": "Australia",
            "region": "New South Wales",
            "locality": "Sydney",
        }
    )
    structured_geocode = AsyncMock(return_value=None)
    nominatim_geocode = AsyncMock(return_value=None)
    discover_candidates = AsyncMock(return_value=[])

    monkeypatch.setattr(service, "_geocode_with_mapbox", mapbox_geocode, raising=False)
    monkeypatch.setattr(service, "_geocode_with_nominatim_structured", structured_geocode)
    monkeypatch.setattr(service, "_geocode_with_nominatim", nominatim_geocode)
    monkeypatch.setattr(
        service,
        "_discover_location_candidates_with_tavily",
        discover_candidates,
        raising=False,
    )

    result = await service.geocode_location("Coogee Beach", "Sydney, Australia")

    assert result is not None
    assert result["coords"] == [151.2446, -33.9230]
    mapbox_geocode.assert_awaited_once_with("Coogee Beach, Sydney, Australia", "Sydney, Australia")
    structured_geocode.assert_not_awaited()
    nominatim_geocode.assert_not_awaited()
    discover_candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_geocode_location_rejects_weak_mapbox_match_and_falls_back_to_nominatim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()

    mapbox_geocode = AsyncMock(
        return_value={
            "coords": [151.308537, -33.696215],
            "full_name": "Sydney Road, Warriewood New South Wales 2102, Australia",
            "address": "Sydney Road, Warriewood New South Wales 2102, Australia",
            "img": "",
            "country_code": "au",
            "country": "Australia",
            "region": "New South Wales",
            "locality": "Sydney",
        }
    )
    structured_geocode = AsyncMock(
        return_value={
            "coords": [151.2152967, -33.8567844],
            "full_name": "Sydney Opera House, 2 Macquarie Street, Sydney NSW 2000, Australia",
            "address": "Sydney Opera House, 2 Macquarie Street, Sydney NSW 2000, Australia",
            "img": "",
            "country_code": "au",
            "country": "Australia",
            "region": "New South Wales",
            "locality": "Sydney",
        }
    )
    nominatim_geocode = AsyncMock(return_value=None)
    discover_candidates = AsyncMock(return_value=[])

    monkeypatch.setattr(service, "_geocode_with_mapbox", mapbox_geocode, raising=False)
    monkeypatch.setattr(service, "_geocode_with_nominatim_structured", structured_geocode)
    monkeypatch.setattr(service, "_geocode_with_nominatim", nominatim_geocode)
    monkeypatch.setattr(
        service,
        "_discover_location_candidates_with_tavily",
        discover_candidates,
        raising=False,
    )

    result = await service.geocode_location("Sydney Opera House", "Sydney, Australia")

    assert result is not None
    assert result["full_name"].startswith("Sydney Opera House")
    mapbox_geocode.assert_awaited_once_with("Sydney Opera House, Sydney, Australia", "Sydney, Australia")
    structured_geocode.assert_awaited_once_with("Sydney Opera House", "Sydney, Australia")
    nominatim_geocode.assert_not_awaited()
    discover_candidates.assert_not_awaited()


@pytest.mark.asyncio
async def test_structured_nominatim_includes_city_hint_in_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()
    captured: dict[str, dict] = {}

    class _Response:
        status_code = 200

        def json(self):
            return [
                {
                    "lon": "151.2579",
                    "lat": "-33.9208",
                    "display_name": "Coogee Beach, Sydney, New South Wales, Australia",
                    "address": {
                        "city": "Sydney",
                        "state": "New South Wales",
                        "country": "Australia",
                        "country_code": "au",
                    },
                }
            ]

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url, params, headers, timeout):
            captured["params"] = params
            return _Response()

    monkeypatch.setattr(tavily_location_module.httpx, "AsyncClient", lambda *args, **kwargs: _Client())
    monkeypatch.setattr(tavily_location_module.asyncio, "sleep", AsyncMock())

    result = await service._geocode_with_nominatim_structured("Coogee Beach", "Sydney, Australia")

    assert result is not None
    assert captured["params"]["q"] == "Coogee Beach, Sydney, Australia"
    assert captured["params"]["countrycodes"] == "au"


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
        side_effect=[
            None,
            {
                "coords": [168.633519, -45.038931],
                "full_name": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
                "address": "139 Fernhill Road, Fernhill, Queenstown 9300, New Zealand",
                "img": "",
            },
        ]
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
    assert mapbox_geocode.await_args_list == [
        call("The Nest, Kamana Lake House, Queenstown", "Queenstown"),
        call("139 Fernhill Road, Queenstown 9300, New Zealand", "Queenstown"),
    ]


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
    assert mapbox_geocode.await_args_list == [
        call("The Nest, Kamana Lake House, Queenstown", "Queenstown"),
        call("139 Fernhill Road, Queenstown 9300, New Zealand", "Queenstown"),
    ]
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


def test_result_within_scope_accepts_chinese_shanghai_match() -> None:
    service = TavilyLocationService()

    result = {
        "full_name": "南京西路, 黄浦区, 上海市, 中国",
        "address": "南京西路, 黄浦区, 上海市, 中国",
        "country_code": "cn",
        "country": "中国",
        "region": "上海市",
        "locality": "黄浦区",
    }
    scope = {
        "scope_name": "Shanghai",
        "country": "China",
        "country_code": "cn",
        "scope_type": "city",
        "query_hint": "Shanghai, China",
    }

    assert service._result_within_scope(result, scope) is True


@pytest.mark.asyncio
async def test_geocode_location_times_out_after_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()
    service._LOCATION_TIMEOUT_SECONDS = 0.01

    async def slow_geocode(place_name: str, city: str | None = None, scope: dict | None = None) -> dict | None:
        await asyncio.sleep(0.05)
        return None

    monkeypatch.setattr(service, "_geocode_location_with_strategies", slow_geocode)

    result = await service.geocode_location("Slow Place", "Shanghai")

    assert result is None


@pytest.mark.asyncio
async def test_discover_location_candidates_filters_noise_and_caps_results(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = TavilyLocationService()
    service.api_key = "test-key"

    class FakeResponse:
        status_code = 200

        @staticmethod
        def json() -> dict:
            return {
                "answer": (
                    "Located at 1 Bund Road, Shanghai 200002. "
                    "Opening Hours: 10am to 10pm. "
                    "Located at 2 Bund Road, Shanghai 200002. "
                    "Located at 3 Bund Road, Shanghai 200002. "
                    "Located at 4 Bund Road, Shanghai 200002. "
                    "Located at 5 Bund Road, Shanghai 200002. "
                    "Located at 6 Bund Road, Shanghai 200002."
                ),
                "results": [],
            }

    class FakeAsyncClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, *args, **kwargs):
            return FakeResponse()

    monkeypatch.setattr(tavily_location_module.httpx, "AsyncClient", lambda *args, **kwargs: FakeAsyncClient())

    candidates = await service._discover_location_candidates_with_tavily("Bund", "Shanghai")

    assert candidates == [
        "1 Bund Road, Shanghai 200002",
        "2 Bund Road, Shanghai 200002",
        "3 Bund Road, Shanghai 200002",
        "4 Bund Road, Shanghai 200002",
        "5 Bund Road, Shanghai 200002",
    ]
