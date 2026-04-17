import json

from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.nodes import booking_agent as booking_agent_module
from backend.models.schemas import Accommodation, Day, POI, SourceVideo, Trip
from backend.services.booking_intent import BookingIntent, normalize_booking_intent


class FakeIntentLLM:
    def __init__(self, payload: dict):
        self.payload = payload

    def invoke(self, messages):
        return AIMessage(content=json.dumps(self.payload))


def make_trip() -> Trip:
    return Trip(
        trip_id="trip_test",
        title="Lake Como Escape",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/123",
                title="Lake Como cafes",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-04-19",
                pois=[
                    POI(
                        id="poi_1",
                        name="Villa del Balbianello",
                        category="Culture",
                        coords=(9.2026, 45.9719),
                        img="https://example.com/1.jpg",
                        time_slot="10:00 - 11:30",
                        vibe="Historic villa on the lake.",
                    ),
                    POI(
                        id="poi_2",
                        name="Bellagio Waterfront",
                        category="Culture",
                        coords=(9.2592, 45.9872),
                        img="https://example.com/2.jpg",
                        time_slot="14:00 - 16:00",
                        vibe="Classic lake promenade.",
                    ),
                ],
            )
        ],
        accommodation=Accommodation(
            name="Grand Hotel",
            price_per_night=320,
            status="confirmed",
            img="https://example.com/hotel.jpg",
            coords=(9.25, 45.98),
        ),
    )


def test_normalize_booking_intent_handles_natural_language_round_trip() -> None:
    llm = FakeIntentLLM(
        {
            "booking_type": "flight",
            "provider_hint": "trip.com",
            "origin": "Singapore Changi Airport",
            "origin_code": "SIN",
            "origin_city_code": "SIN",
            "destination": "Milan",
            "destination_code": "",
            "destination_city_code": "MIL",
            "departure_date": "2026-04-19",
            "return_date": "2026-04-25",
            "trip_type": "round_trip",
            "adults": 2,
            "cabin": "economy",
            "budget_limit": 0,
            "origin_source": "user",
            "destination_source": "trip_context",
            "departure_date_source": "user",
            "trip_type_source": "user",
            "adults_source": "user",
            "missing_fields": [],
            "can_search": True,
            "follow_up_question": "",
        }
    )

    intent = normalize_booking_intent(
        message=(
            "Departure is Changi Airport Singapore. Arrival is Italy nearest airport to "
            "Lake Como. Leave on Sunday 19 Apr, come back on 25 Apr. Round trip. "
            "2 people. Cheapest flight available."
        ),
        trip=make_trip(),
        llm=llm,
    )

    assert intent.origin == "Singapore Changi Airport"
    assert intent.origin_code == "SIN"
    assert intent.destination == "Milan"
    assert intent.destination_city_code == "MIL"
    assert intent.departure_date == "2026-04-19"
    assert intent.return_date == "2026-04-25"
    assert intent.trip_type == "round_trip"
    assert intent.adults == 2
    assert intent.can_search is True


def test_booking_agent_uses_normalized_intent_for_tool_call(monkeypatch) -> None:
    monkeypatch.setattr(
        booking_agent_module,
        "normalize_booking_intent",
        lambda **kwargs: BookingIntent(
            booking_type="flight",
            provider_hint="trip.com",
            origin="Singapore Changi Airport",
            origin_code="SIN",
            origin_city_code="SIN",
            destination="Milan",
            destination_code="",
            destination_city_code="MIL",
            departure_date="2026-04-19",
            return_date="2026-04-25",
            trip_type="round_trip",
            adults=2,
            cabin="economy",
            budget_limit=0,
            origin_source="user",
            destination_source="trip_context",
            departure_date_source="user",
            trip_type_source="user",
            adults_source="user",
            missing_fields=[],
            can_search=True,
            follow_up_question="",
        ),
    )

    state = {
        "messages": [HumanMessage(content="Find flights from Singapore to Lake Como next Sunday.")],
        "trip": make_trip(),
        "plan": [],
        "current_step": 0,
        "critique": "",
        "booking_context": {},
        "booking_offers": [],
        "selected_offer": {},
        "booking_result": {},
    }

    result = booking_agent_module.booking_agent_node(state)
    tool_calls = result["messages"][0].tool_calls

    assert len(tool_calls) == 1
    assert tool_calls[0]["name"] == "find_booking_options"
    assert tool_calls[0]["args"]["origin"] == "Singapore Changi Airport"
    assert tool_calls[0]["args"]["destination"] == "Milan"
    assert tool_calls[0]["args"]["departure_date"] == "2026-04-19"
    assert tool_calls[0]["args"]["return_date"] == "2026-04-25"
    assert tool_calls[0]["args"]["adults"] == 2


def test_booking_agent_asks_for_missing_details_from_normalized_intent(monkeypatch) -> None:
    monkeypatch.setattr(
        booking_agent_module,
        "normalize_booking_intent",
        lambda **kwargs: BookingIntent(
            booking_type="flight",
            provider_hint="trip.com",
            origin="Singapore",
            destination="Milan",
            departure_date="",
            return_date="",
            trip_type="round_trip",
            adults=None,
            origin_source="user",
            destination_source="trip_context",
            departure_date_source="missing",
            trip_type_source="user",
            adults_source="missing",
            missing_fields=["departure date", "adult count"],
            can_search=False,
            follow_up_question="I still need the departure date and number of adults before I can search trip.com.",
        ),
    )

    state = {
        "messages": [HumanMessage(content="Find the cheapest flight for this trip.")],
        "trip": make_trip(),
        "plan": [],
        "current_step": 0,
        "critique": "",
        "booking_context": {},
        "booking_offers": [],
        "selected_offer": {},
        "booking_result": {},
    }

    result = booking_agent_module.booking_agent_node(state)
    response = result["messages"][0]

    assert response.content == "I still need the departure date and number of adults before I can search trip.com."
    assert not getattr(response, "tool_calls", None)


def test_booking_agent_normalizes_plain_english_ticket_request(monkeypatch) -> None:
    called = {"count": 0}

    def fake_normalizer(**kwargs):
        called["count"] += 1
        return BookingIntent(
            booking_type="flight",
            provider_hint="trip.com",
            origin="Singapore Changi Airport",
            origin_code="SIN",
            origin_city_code="SIN",
            destination="Milan",
            destination_city_code="MIL",
            departure_date="2026-04-19",
            return_date="2026-04-25",
            trip_type="round_trip",
            adults=2,
            origin_source="user",
            destination_source="trip_context",
            departure_date_source="user",
            trip_type_source="user",
            adults_source="user",
            missing_fields=[],
            can_search=True,
            follow_up_question="",
        )

    monkeypatch.setattr(booking_agent_module, "normalize_booking_intent", fake_normalizer)

    state = {
        "messages": [HumanMessage(content="I need tickets from Singapore to Lake Como on 2026-04-19 for two people.")],
        "trip": make_trip(),
        "plan": [],
        "current_step": 0,
        "critique": "",
        "booking_context": {},
        "booking_offers": [],
        "selected_offer": {},
        "booking_result": {},
    }

    result = booking_agent_module.booking_agent_node(state)

    assert called["count"] == 1
    assert result["messages"][0].tool_calls[0]["name"] == "find_booking_options"


def test_booking_agent_does_not_repeat_stale_failure_on_new_user_turn(monkeypatch) -> None:
    called = {"count": 0}

    def fake_normalizer(**kwargs):
        called["count"] += 1
        return BookingIntent(
            booking_type="flight",
            provider_hint="trip.com",
            origin="Singapore Changi Airport",
            destination="Queenstown",
            departure_date="2026-11-01",
            return_date="2026-11-07",
            trip_type="round_trip",
            adults=2,
            origin_source="user",
            destination_source="trip_context",
            departure_date_source="user",
            trip_type_source="user",
            adults_source="user",
            missing_fields=[],
            can_search=True,
            follow_up_question="",
        )

    monkeypatch.setattr(booking_agent_module, "normalize_booking_intent", fake_normalizer)

    state = {
        "messages": [HumanMessage(content="Can you find flights from Singapore to this place?")],
        "trip": make_trip(),
        "plan": [],
        "current_step": 0,
        "critique": "",
        "booking_context": {"attempted": True, "last_error": "old timeout", "provider_hint": "trip.com"},
        "booking_offers": [],
        "selected_offer": {},
        "booking_result": {},
    }

    result = booking_agent_module.booking_agent_node(state)

    assert called["count"] == 1
    assert result["messages"][0].tool_calls[0]["name"] == "find_booking_options"


def test_booking_agent_opens_checkout_in_visible_browser_after_selection() -> None:
    state = {
        "messages": [HumanMessage(content="Book offer_1.")],
        "trip": make_trip(),
        "plan": [],
        "current_step": 0,
        "critique": "",
        "booking_context": {"explicit_selection": True},
        "booking_offers": [
            {
                "id": "offer_1",
                "title": "Demo Flight",
                "price": 199.0,
                "currency": "USD",
            }
        ],
        "selected_offer": {
            "id": "offer_1",
            "title": "Demo Flight",
            "price": 199.0,
            "currency": "USD",
        },
        "booking_result": {},
    }

    result = booking_agent_module.booking_agent_node(state)
    tool_call = result["messages"][0].tool_calls[0]

    assert tool_call["name"] == "proceed_checkout"
    assert tool_call["args"]["headless"] is False
