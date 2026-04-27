from types import SimpleNamespace

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from backend.agent.nodes import critic as critic_node_module
from backend.agent.nodes import orchestrator as orchestrator_node_module
from backend.agent.nodes import travel_editor as travel_editor_node_module
from backend.agent.nodes.travel_tool_executor import (
    _execute_add_meal_stop,
    _execute_resize_trip,
    haversine_km,
    _pick_named_place_result,
    _search_places_nearby_sync,
)
from backend.models.schemas import Accommodation, Day, POI, Trip


def _poi(name: str, coords: tuple[float, float], *, category: str = "Culture", slot: str = "10:00 - 11:00") -> POI:
    return POI(
        id=f"poi_{name.lower().replace(' ', '_')}",
        name=name,
        category=category,
        coords=coords,
        img="https://example.com/poi.jpg",
        time_slot=slot,
        vibe=f"{name} vibe",
        priority="normal",
        intensity="normal",
        visit_duration=60,
    )


def _parse_slot(slot: str) -> tuple[int, int]:
    start_raw, end_raw = [part.strip() for part in slot.split("-", maxsplit=1)]
    start_h, start_m = [int(part) for part in start_raw.split(":")]
    end_h, end_m = [int(part) for part in end_raw.split(":")]
    return start_h * 60 + start_m, end_h * 60 + end_m


def _trip_for_resize() -> Trip:
    return Trip(
        trip_id="trip_resize",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(day_number=1, date="2026-05-01", pois=[_poi("Bondi Beach", (151.2743, -33.8915)), _poi("Coogee Beach", (151.2576, -33.9205))]),
            Day(day_number=2, date="2026-05-02", pois=[_poi("The Rocks", (151.2090, -33.8599)), _poi("Opera House", (151.2153, -33.8568))]),
            Day(day_number=3, date="2026-05-03", pois=[_poi("Bronte Beach", (151.2653, -33.9033)), _poi("Sydney Tower", (151.2070, -33.8708))]),
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def _trip_for_meals() -> Trip:
    return Trip(
        trip_id="trip_meals",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    _poi("Bondi Beach", (151.2743, -33.8915), slot="09:00 - 10:00"),
                    _poi("Icebergs Pool", (151.2820, -33.8910), slot="14:00 - 15:00"),
                ],
            )
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def _trip_for_multi_day_meals() -> Trip:
    return Trip(
        trip_id="trip_multi_day_meals",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    _poi("Sydney Harbour Bridge", (151.2108, -33.8523), slot="09:00 - 10:00"),
                    _poi("Circular Quay", (151.2120, -33.8610), slot="10:30 - 11:30"),
                    _poi("Observatory Hill", (151.2048, -33.8599), slot="14:00 - 15:00"),
                    _poi("Darling Harbour", (151.2001, -33.8748), slot="16:30 - 17:30"),
                ],
            ),
            Day(
                day_number=2,
                date="2026-05-02",
                pois=[
                    _poi("Coogee Beach", (151.2576, -33.9205), category="Nature", slot="09:00 - 10:30"),
                    _poi("Bronte Beach", (151.2653, -33.9033), category="Nature", slot="11:00 - 12:30"),
                    _poi("Mrs Macquarie's Point", (151.2162, -33.8675), category="Nature", slot="14:00 - 15:00"),
                ],
            ),
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def _trip_with_remote_outlier() -> Trip:
    return Trip(
        trip_id="trip_remote_outlier",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    _poi("Blue Mountains", (150.3119, -33.7147), category="Nature"),
                    _poi("Darling Harbour", (151.2001, -33.8748)),
                    _poi("Sydney Harbour Bridge", (151.2108, -33.8523)),
                ],
            ),
            Day(
                day_number=2,
                date="2026-05-02",
                pois=[
                    _poi("Observatory Hill", (151.2048, -33.8599)),
                    _poi("Opera House", (151.2153, -33.8568)),
                ],
            ),
            Day(
                day_number=3,
                date="2026-05-03",
                pois=[
                    _poi("Bronte Beach", (151.2653, -33.9033), category="Nature"),
                    _poi("Clovelly Beach", (151.2594, -33.9127), category="Nature"),
                    _poi("Coogee Beach", (151.2576, -33.9205), category="Nature"),
                ],
            ),
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def _trip_with_two_remote_outliers() -> Trip:
    return Trip(
        trip_id="trip_two_remote_outliers",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    _poi("Bondi Beach (South End / Cliffs)", (151.27399, -33.891296), category="Nature"),
                    _poi("Bronte Beach", (151.2653, -33.9033), category="Nature"),
                    _poi("Coogee Beach", (151.2576, -33.9205), category="Nature"),
                    _poi("Manly", (151.2869, -33.7969), category="Nature"),
                ],
            ),
            Day(
                day_number=2,
                date="2026-05-02",
                pois=[
                    _poi("Gordon's Bay", (151.2678, -33.9192), category="Nature"),
                    _poi("Observatory Hill", (151.2048, -33.8599)),
                    _poi("Sydney Opera House", (151.2153, -33.8568)),
                    _poi("Darling Harbour", (151.2001, -33.8748)),
                ],
            ),
            Day(
                day_number=3,
                date="2026-05-03",
                pois=[
                    _poi("Blue Mountains", (150.3119, -33.7147), category="Nature"),
                ],
            ),
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def _trip_with_eastern_beach_overflow() -> Trip:
    return Trip(
        trip_id="trip_eastern_beach_overflow",
        title="Sydney Explorer",
        source_videos=[],
        days=[
            Day(
                day_number=1,
                date="2026-05-01",
                pois=[
                    _poi("Bronte Beach", (151.2653, -33.9033), category="Nature"),
                    _poi("Clovelly Beach", (151.2594, -33.9127), category="Nature"),
                    _poi("Coogee Beach", (151.2576, -33.9205), category="Nature"),
                    _poi("Icebergs Pool", (151.2746, -33.8951), category="Nature"),
                    _poi("Gordon's Bay", (151.2678, -33.9192), category="Nature"),
                ],
            ),
            Day(
                day_number=2,
                date="2026-05-02",
                pois=[
                    _poi("Observatory Hill", (151.2048, -33.8599)),
                    _poi("Sydney Opera House", (151.2153, -33.8568)),
                    _poi("Darling Harbour", (151.2001, -33.8748)),
                ],
            ),
            Day(
                day_number=3,
                date="2026-05-03",
                pois=[
                    _poi("Blue Mountains", (150.3119, -33.7147), category="Nature"),
                ],
            ),
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200.0,
            status="Booked",
            img="https://example.com/hotel.jpg",
            coords=(151.2093, -33.8688),
        ),
    )


def test_execute_resize_trip_groups_obvious_geographic_clusters():
    trip = _trip_for_resize()

    resized, message = _execute_resize_trip(trip, 2)

    assert len(resized.days) == 2
    day_names = [{poi.name for poi in day.pois} for day in resized.days]
    assert {"Bondi Beach", "Coogee Beach", "Bronte Beach"} in day_names
    assert {"The Rocks", "Opera House", "Sydney Tower"} in day_names
    assert "2 days" in message


def test_execute_resize_trip_keeps_remote_outlier_day_geographically_clean():
    trip = _trip_with_remote_outlier()

    resized, _ = _execute_resize_trip(trip, 3)

    blue_day = next(day for day in resized.days if any(poi.name == "Blue Mountains" for poi in day.pois))
    blue_day_names = {poi.name for poi in blue_day.pois}

    assert "Darling Harbour" not in blue_day_names
    assert "Sydney Harbour Bridge" not in blue_day_names


def test_execute_resize_trip_drops_remote_outlier_when_shrinking_days():
    trip = _trip_with_remote_outlier()

    resized, message = _execute_resize_trip(trip, 2)

    remaining_names = {poi.name for day in resized.days for poi in day.pois}

    assert "Blue Mountains" not in remaining_names
    assert len(resized.days) == 2
    assert "dropped" in message.lower()


def test_execute_resize_trip_drops_second_remote_outlier_when_two_day_plan_is_full():
    trip = _trip_with_two_remote_outliers()

    resized, message = _execute_resize_trip(trip, 2)

    remaining_names = {poi.name for day in resized.days for poi in day.pois}

    assert "Blue Mountains" not in remaining_names
    assert "Manly" not in remaining_names
    assert len(resized.days) == 2
    assert "dropped" in message.lower()


def test_execute_resize_trip_keeps_two_day_clusters_geographically_tight_when_one_region_overflows():
    trip = _trip_with_eastern_beach_overflow()

    resized, message = _execute_resize_trip(trip, 2)

    assert len(resized.days) == 2
    assert "Blue Mountains" not in {poi.name for day in resized.days for poi in day.pois}
    assert "dropped" in message.lower()

    for day in resized.days:
        max_pair_distance = 0.0
        for index, left in enumerate(day.pois):
            for right in day.pois[index + 1 :]:
                max_pair_distance = max(max_pair_distance, haversine_km(left.coords, right.coords))
        assert max_pair_distance < 6.5


def test_execute_add_meal_stop_adds_food_poi_to_day(monkeypatch: pytest.MonkeyPatch):
    trip = _trip_for_meals()

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_sync",
        lambda anchor_coords, meal_type, cuisine_hint="": [
            {
                "name": "Bills Bondi",
                "description": "Popular brunch spot near Bondi.",
                "coords": [151.276, -33.892],
            }
        ],
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fetch_image", lambda name: "https://example.com/meal.jpg")

    updated, message = _execute_add_meal_stop(trip, day_number=1, meal_type="lunch", cuisine_hint="")

    food_pois = [poi for poi in updated.days[0].pois if poi.category == "Food"]
    assert any(poi.name == "Bills Bondi" for poi in food_pois)
    assert any("12:" in poi.time_slot for poi in food_pois)
    assert "Bills Bondi" in message


def test_search_places_nearby_falls_back_to_text_search_when_overpass_times_out(
    monkeypatch: pytest.MonkeyPatch,
):
    class _TimeoutingClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, *args, **kwargs):
            if "overpass" in url:
                raise httpx.ReadTimeout("timed out")
            raise AssertionError(f"Unexpected URL: {url}")

    class _FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def text(self, query: str, max_results: int = 5):
            assert "lunch restaurants near Bondi Beach" in query
            return [
                {
                    "title": "Bills Bondi",
                    "body": "Popular brunch and lunch spot near Bondi Beach.",
                    "href": "https://example.com/bills-bondi",
                }
            ]

    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor.httpx.Client", _TimeoutingClient)
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor.DDGS", _FakeDDGS)
    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._reverse_geocode_anchor_sync",
        lambda coords: "Bondi Beach, Sydney, Australia",
        raising=False,
    )
    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._auto_geocode",
        lambda place_name, city_hint: (151.2745, -33.8911),
    )

    results = _search_places_nearby_sync((151.2743, -33.8915), "lunch")

    assert results[0]["name"] == "Bills Bondi"
    assert results[0]["coords"] == [151.2745, -33.8911]


def test_search_places_nearby_tries_secondary_overpass_endpoint_before_text_fallback(
    monkeypatch: pytest.MonkeyPatch,
):
    class _Response:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "elements": [
                    {
                        "tags": {
                            "name": "Cafe Sydney",
                            "amenity": "restaurant",
                            "addr:street": "Customs House",
                        },
                        "lon": 151.2093,
                        "lat": -33.8610,
                    }
                ]
            }

    class _FailoverClient:
        calls: list[str] = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def get(self, url, *args, **kwargs):
            self.calls.append(url)
            if url == "https://primary-overpass.invalid/api/interpreter":
                raise httpx.ReadTimeout("timed out")
            if url == "https://secondary-overpass.invalid/api/interpreter":
                return _Response()
            raise AssertionError(f"Unexpected URL: {url}")

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor.OVERPASS_INTERPRETER_URLS",
        [
            "https://primary-overpass.invalid/api/interpreter",
            "https://secondary-overpass.invalid/api/interpreter",
        ],
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor.httpx.Client", _FailoverClient)
    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_text_fallback_sync",
        lambda anchor_coords, meal_type, cuisine_hint="": [],
    )

    results = _search_places_nearby_sync((151.1996, -33.8675), "dinner")

    assert [item["name"] for item in results] == ["Cafe Sydney"]
    assert _FailoverClient.calls == [
        "https://primary-overpass.invalid/api/interpreter",
        "https://secondary-overpass.invalid/api/interpreter",
    ]


def test_execute_add_meal_stops_preserve_existing_sightseeing_pois_across_two_days(monkeypatch: pytest.MonkeyPatch):
    trip = _trip_for_multi_day_meals()
    original_names = {poi.name for day in trip.days for poi in day.pois}
    meal_names = iter(["Tago-An", "Caminetto Restaurant", "Bondi Trattoria", "Cafe Sydney"])

    def _fake_search(anchor_coords, meal_type, cuisine_hint=""):
        meal_name = next(meal_names)
        return [
            {
                "name": meal_name,
                "description": f"{meal_type.title()} near the itinerary",
                "coords": [anchor_coords[0], anchor_coords[1]],
            }
        ]

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_sync",
        _fake_search,
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fetch_image", lambda name: "https://example.com/meal.jpg")

    updated, _ = _execute_add_meal_stop(trip, day_number=1, meal_type="lunch", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=1, meal_type="dinner", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=2, meal_type="lunch", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=2, meal_type="dinner", cuisine_hint="")

    final_names = {poi.name for day in updated.days for poi in day.pois}
    food_names = {
        poi.name
        for day in updated.days
        for poi in day.pois
        if poi.category == "Food"
    }

    assert original_names <= final_names
    assert food_names == {"Tago-An", "Caminetto Restaurant", "Bondi Trattoria", "Cafe Sydney"}


def test_execute_add_meal_stop_skips_restaurant_already_used_that_day(monkeypatch: pytest.MonkeyPatch):
    trip = _trip_for_meals()
    trip.days[0].pois.append(
        _poi("Spice Room at the Malaya", (151.2100, -33.8700), category="Food", slot="12:30 - 13:45")
    )

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_sync",
        lambda anchor_coords, meal_type, cuisine_hint="": [
            {
                "name": "Spice Room at the Malaya",
                "description": "Already picked for lunch",
                "coords": [151.2100, -33.8700],
            },
            {
                "name": "Cafe Sydney",
                "description": "Distinct dinner option",
                "coords": [151.2110, -33.8690],
            },
        ],
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fetch_image", lambda name: "https://example.com/meal.jpg")

    updated, message = _execute_add_meal_stop(trip, day_number=1, meal_type="dinner", cuisine_hint="")

    food_names = [poi.name for poi in updated.days[0].pois if poi.category == "Food"]
    assert food_names.count("Spice Room at the Malaya") == 1
    assert "Cafe Sydney" in food_names
    assert "Cafe Sydney" in message


def test_execute_add_meal_stop_does_not_claim_success_if_replan_drops_new_stop(monkeypatch: pytest.MonkeyPatch):
    trip = _trip_for_meals()

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_sync",
        lambda anchor_coords, meal_type, cuisine_hint="": [
            {
                "name": "Bills Bondi",
                "description": "Popular brunch spot near Bondi.",
                "coords": [151.276, -33.892],
            }
        ],
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fetch_image", lambda name: "https://example.com/meal.jpg")

    def _fake_execute_add(local_trip, args):
        local_trip.days[0].pois.append(
            _poi(
                args["name"],
                (args["longitude"], args["latitude"]),
                category="Food",
                slot=args["time_slot"],
            )
        )
        return local_trip, f"Added '{args['name']}' (ID: poi_food) to Day 1."

    def _fake_fit_day_within_clock(local_trip, day_number):
        del day_number
        local_trip.days[0].pois = [poi for poi in local_trip.days[0].pois if poi.name != "Bills Bondi"]
        return local_trip, ["Bills Bondi"]

    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._execute_add", _fake_execute_add)
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fit_day_within_clock", _fake_fit_day_within_clock)

    updated, message = _execute_add_meal_stop(trip, day_number=1, meal_type="lunch", cuisine_hint="")

    food_names = [poi.name for poi in updated.days[0].pois if poi.category == "Food"]
    assert "Bills Bondi" not in food_names
    assert "Bills Bondi" not in message
    assert "could not" in message.lower()


def test_execute_add_meal_stops_keep_days_in_time_order_without_overlaps(monkeypatch: pytest.MonkeyPatch):
    trip = _trip_for_multi_day_meals()
    meal_names = iter(["Beach Burrito Company", "Manly Greenhouse", "Toppinz", "Frango"])

    def _fake_search(anchor_coords, meal_type, cuisine_hint=""):
        meal_name = next(meal_names)
        return [
            {
                "name": meal_name,
                "description": f"{meal_type.title()} near the itinerary",
                "coords": [anchor_coords[0], anchor_coords[1]],
            }
        ]

    monkeypatch.setattr(
        "backend.agent.nodes.travel_tool_executor._search_places_nearby_sync",
        _fake_search,
    )
    monkeypatch.setattr("backend.agent.nodes.travel_tool_executor._fetch_image", lambda name: "https://example.com/meal.jpg")

    updated, _ = _execute_add_meal_stop(trip, day_number=1, meal_type="lunch", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=1, meal_type="dinner", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=2, meal_type="lunch", cuisine_hint="")
    updated, _ = _execute_add_meal_stop(updated, day_number=2, meal_type="dinner", cuisine_hint="")

    for day in updated.days:
        starts = [_parse_slot(poi.time_slot)[0] for poi in day.pois]
        assert starts == sorted(starts)

        for previous, current in zip(day.pois, day.pois[1:]):
            previous_end = _parse_slot(previous.time_slot)[1]
            current_start = _parse_slot(current.time_slot)[0]
            assert previous_end <= current_start


def test_pick_named_place_result_skips_generic_article_titles():
    chosen = _pick_named_place_result(
        [
            {
                "name": "The 50 best spots for lunch in Bondi",
                "description": "Listicle title",
                "coords": [151.2740, -33.8910],
            },
            {
                "name": "Bills Bondi",
                "description": "Restaurant near Bondi Beach",
                "coords": [151.2760, -33.8920],
            },
        ],
        anchor_coords=(151.2743, -33.8915),
    )

    assert chosen is not None
    assert chosen["name"] == "Bills Bondi"


def test_orchestrator_short_circuits_shrink_to_days():
    state = {
        "messages": [HumanMessage(content="Shrink it to 2 days")],
        "trip": _trip_for_resize(),
        "critique": "",
        "plan": None,
        "current_step": 0,
    }

    result = orchestrator_node_module.orchestrator_node(state)

    assert result["next_node"] == "travel_editor"
    assert result["plan"] == ["resize trip to 2 days"]


def test_orchestrator_short_circuits_initial_day_count_request():
    state = {
        "messages": [HumanMessage(content="Plan a 3-day trip from these TikToks")],
        "trip": _trip_for_resize(),
        "critique": "",
        "plan": None,
        "current_step": 0,
    }

    result = orchestrator_node_module.orchestrator_node(state)

    assert result["next_node"] == "travel_editor"
    assert result["plan"] == ["resize trip to 3 days"]


def test_orchestrator_short_circuits_multi_day_meal_planning():
    trip = _trip_for_resize()
    trip.days = trip.days[:2]
    state = {
        "messages": [HumanMessage(content="Find lunch and dinner locations for both days")],
        "trip": trip,
        "critique": "",
        "plan": None,
        "current_step": 0,
    }

    result = orchestrator_node_module.orchestrator_node(state)

    assert result["next_node"] == "travel_editor"
    assert result["plan"] == [
        "add a lunch restaurant stop to day 1",
        "add a dinner restaurant stop to day 1",
        "add a lunch restaurant stop to day 2",
        "add a dinner restaurant stop to day 2",
    ]


def test_travel_editor_short_circuits_resize_instruction():
    state = {
        "messages": [HumanMessage(content="Please fix the geography")],
        "trip": _trip_for_resize(),
        "plan": ["resize trip to 2 days"],
        "current_step": 0,
        "critique": "Days are too spread out.",
    }

    result = travel_editor_node_module.travel_editor_node(state)

    tool_calls = result["messages"][0].tool_calls
    assert tool_calls[0]["name"] == "resize_trip"
    assert tool_calls[0]["args"]["target_days"] == 2


def test_travel_editor_short_circuits_meal_instruction():
    state = {
        "messages": [HumanMessage(content="Please fix the meal gap")],
        "trip": _trip_for_meals(),
        "plan": ["add a dinner restaurant stop to day 1"],
        "current_step": 0,
        "critique": "",
    }

    result = travel_editor_node_module.travel_editor_node(state)

    tool_calls = result["messages"][0].tool_calls
    assert tool_calls[0]["name"] == "add_meal_stop"
    assert tool_calls[0]["args"]["day_number"] == 1
    assert tool_calls[0]["args"]["meal_type"] == "dinner"


def test_travel_editor_stops_resize_loop_after_tool_result():
    state = {
        "messages": [
            HumanMessage(content="Shrink it to 2 days"),
            ToolMessage(content="Resized trip to 2 days.", tool_call_id="tool_resize"),
        ],
        "trip": _trip_for_resize(),
        "plan": ["resize trip to 2 days"],
        "current_step": 0,
        "critique": "",
    }

    result = travel_editor_node_module.travel_editor_node(state)

    response = result["messages"][0]
    assert not getattr(response, "tool_calls", None)
    assert "Resized trip to 2 days." in response.content


def test_travel_editor_stops_meal_loop_after_tool_result():
    state = {
        "messages": [
            HumanMessage(content="Find lunch location for day 1"),
            ToolMessage(content="Added 'Bills Bondi' (ID: poi_food) to Day 1.", tool_call_id="tool_meal"),
        ],
        "trip": _trip_for_meals(),
        "plan": ["add a lunch restaurant stop to day 1"],
        "current_step": 0,
        "critique": "",
    }

    result = travel_editor_node_module.travel_editor_node(state)

    response = result["messages"][0]
    assert not getattr(response, "tool_calls", None)
    assert "Bills Bondi" in response.content


def test_critic_auto_approves_completed_resize_step():
    state = {
        "messages": [
            HumanMessage(content="Plan a 3-day trip from these TikToks"),
            ToolMessage(content="Resized trip to 3 days.", tool_call_id="tool_resize"),
            AIMessage(content="Resized trip to 3 days."),
        ],
        "trip": _trip_for_resize(),
        "plan": ["resize trip to 3 days"],
        "current_step": 0,
        "last_agent": "travel_editor",
        "iteration_count": 0,
    }

    result = critic_node_module.critic_node(state)

    assert result["next_node"] == "approve"
    assert result["iteration_count"] == 0


def test_critic_auto_approves_completed_meal_step():
    state = {
        "messages": [
            HumanMessage(content="Find lunch and dinner locations for both days"),
            ToolMessage(content="Added 'Bills Bondi' (ID: poi_food) to Day 1.", tool_call_id="tool_meal"),
            AIMessage(content="Added 'Bills Bondi' (ID: poi_food) to Day 1."),
        ],
        "trip": _trip_for_meals(),
        "plan": ["add a lunch restaurant stop to day 1"],
        "current_step": 0,
        "last_agent": "travel_editor",
        "iteration_count": 0,
    }

    result = critic_node_module.critic_node(state)

    assert result["next_node"] == "approve"
    assert result["iteration_count"] == 0


def test_critic_auto_approves_booking_step():
    state = {
        "messages": [
            HumanMessage(content="Book a flight to Sydney for 2 pax, on the weekend of 2nd to 4th May"),
            ToolMessage(content="Found 8 options:\n- offer_4: Emirates", tool_call_id="tool_booking"),
            AIMessage(content="I found flights and selected the cheapest offer."),
        ],
        "trip": _trip_for_meals(),
        "last_agent": "booking_agent",
        "iteration_count": 0,
        "booking_offers": [{"id": "offer_4", "price": 1103.0}],
    }

    result = critic_node_module.critic_node(state)

    assert result["next_node"] == "approve"
    assert result["iteration_count"] == 0
