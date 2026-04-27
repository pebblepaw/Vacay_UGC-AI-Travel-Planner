import asyncio

from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.nodes import booking_tool_executor as booking_tool_executor_module


def test_find_booking_options_persists_attempted_failure_state_when_search_raises(monkeypatch) -> None:
    async def raise_search_error(query):
        raise RuntimeError("navigation timeout")

    monkeypatch.setattr(
        booking_tool_executor_module.browser_use_worker,
        "search_offers",
        raise_search_error,
    )

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "find_booking_options",
                        "args": {
                            "booking_type": "flight",
                            "origin": "Singapore Changi Airport",
                            "origin_code": "SIN",
                            "origin_city_code": "SIN",
                            "destination": "Sydney",
                            "destination_code": "SYD",
                            "destination_city_code": "SYD",
                            "departure_date": "2026-05-02",
                            "return_date": "2026-05-04",
                            "trip_type": "round_trip",
                            "adults": 2,
                            "provider_hint": "trip.com",
                            "max_results": 10,
                        },
                        "id": "tool_booking",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "booking_context": {},
        "booking_offers": [],
        "selected_offer": {"id": "stale_offer"},
        "booking_result": {"status": "stale"},
    }

    result = asyncio.run(booking_tool_executor_module.booking_tool_executor(state))

    assert result["booking_offers"] == []
    assert result["selected_offer"] == {}
    assert result["booking_result"] == {}
    assert result["booking_context"]["attempted"] is True
    assert result["booking_context"]["provider_hint"] == "trip.com"
    assert result["booking_context"]["origin"] == "Singapore Changi Airport"
    assert result["booking_context"]["destination"] == "Sydney"
    assert result["booking_context"]["departure_date"] == "2026-05-02"
    assert result["booking_context"]["return_date"] == "2026-05-04"
    assert "navigation timeout" in result["booking_context"]["last_error"]
    assert "navigation timeout" in result["messages"][0].content


def test_find_booking_options_force_refresh_ignores_cached_offers(monkeypatch) -> None:
    async def fake_search(query):
        return [
            {
                "id": "offer_new",
                "title": "Fresh Demo Flight",
                "price": 321.0,
                "currency": "USD",
            }
        ]

    monkeypatch.setattr(
        booking_tool_executor_module.browser_use_worker,
        "search_offers",
        fake_search,
    )

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "find_booking_options",
                        "args": {
                            "booking_type": "flight",
                            "origin": "Singapore",
                            "origin_code": "SIN",
                            "origin_city_code": "SIN",
                            "destination": "Sydney",
                            "destination_code": "SYD",
                            "destination_city_code": "SYD",
                            "departure_date": "2026-05-02",
                            "return_date": "2026-05-04",
                            "trip_type": "round_trip",
                            "adults": 2,
                            "provider_hint": "trip.com",
                            "max_results": 10,
                            "force_refresh": True,
                        },
                        "id": "tool_booking",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "booking_context": {
            "origin": "Singapore",
            "destination": "Sydney",
            "departure_date": "2026-05-02",
            "return_date": "2026-05-04",
            "trip_type": "round_trip",
            "provider_hint": "trip.com",
        },
        "booking_offers": [{"id": "offer_stale"}],
        "selected_offer": {"id": "offer_stale"},
        "booking_result": {"status": "failed"},
    }

    result = asyncio.run(booking_tool_executor_module.booking_tool_executor(state))

    assert result["booking_offers"][0]["id"] == "offer_new"
    assert result["selected_offer"] == {}
    assert result["booking_result"] == {}


def test_proceed_checkout_passes_workspace_id_into_selected_offer(monkeypatch) -> None:
    captured: dict = {}

    async def fake_checkout(offer, traveler, headless=True, skip_fill=False):
        captured["offer"] = offer
        return {
            "status": "needs_user_input",
            "reason": "Reached traveler info page.",
            "confirmation_url": "https://demo.vacay.ai/browser?token=short",
            "screenshot": "",
        }

    monkeypatch.setattr(
        booking_tool_executor_module.playwright_checkout_runner,
        "checkout_to_confirmation",
        fake_checkout,
    )

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "proceed_checkout",
                        "args": {
                            "traveler_name": "",
                            "traveler_email": "",
                            "traveler_phone": "",
                            "traveler_gender": "",
                            "traveler_birth_date": "",
                            "traveler_nationality": "",
                            "traveler_doc_type": "",
                            "traveler_doc_number": "",
                            "traveler_doc_expiry": "",
                            "allow_empty_traveler": True,
                            "headless": False,
                        },
                        "id": "tool_checkout",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "workspace_id": "telegram:-5289526650:main",
        "booking_context": {"selected_offer_id": "offer_1"},
        "booking_offers": [{"id": "offer_1"}],
        "selected_offer": {
            "id": "offer_1",
            "title": "Demo flight",
            "provider": "trip.com",
            "live_session_id": "trip_session_demo",
        },
        "booking_result": {},
    }

    result = asyncio.run(booking_tool_executor_module.booking_tool_executor(state))

    assert captured["offer"]["workspace_id"] == "telegram:-5289526650:main"
    assert result["booking_result"]["status"] == "needs_user_input"


def test_proceed_checkout_retries_after_failed_checkout_status(monkeypatch) -> None:
    calls: list[dict] = []

    async def fake_checkout(offer, traveler, headless=True, skip_fill=False):
        calls.append(offer)
        return {
            "status": "needs_user_input",
            "reason": "Trip.com requires verification. Continue at the current URL.",
            "confirmation_url": "https://www.trip.com/flights/showfarefirst/?captcha=1",
            "screenshot": "",
        }

    monkeypatch.setattr(
        booking_tool_executor_module.playwright_checkout_runner,
        "checkout_to_confirmation",
        fake_checkout,
    )

    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "proceed_checkout",
                        "args": {
                            "traveler_name": "",
                            "traveler_email": "",
                            "traveler_phone": "",
                            "traveler_gender": "",
                            "traveler_birth_date": "",
                            "traveler_nationality": "",
                            "traveler_doc_type": "",
                            "traveler_doc_number": "",
                            "traveler_doc_expiry": "",
                            "allow_empty_traveler": True,
                            "headless": False,
                        },
                        "id": "tool_checkout",
                        "type": "tool_call",
                    }
                ],
            )
        ],
        "workspace_id": "telegram:-1003790620984:main",
        "booking_context": {"selected_offer_id": "offer_1", "checkout_status": "failed"},
        "booking_offers": [{"id": "offer_1"}],
        "selected_offer": {
            "id": "offer_1",
            "title": "Demo flight",
            "provider": "trip.com",
            "live_session_id": "trip_session_demo",
        },
        "booking_result": {
            "status": "failed",
            "reason": "Still on search results page; checkout form not reached.",
        },
    }

    result = asyncio.run(booking_tool_executor_module.booking_tool_executor(state))

    assert len(calls) == 1
    assert result["booking_context"]["checkout_status"] == "needs_user_input"
    assert "requires verification" in result["messages"][0].content


def test_proceed_checkout_marks_current_human_turn_to_prevent_same_turn_retry(monkeypatch) -> None:
    async def fake_checkout(offer, traveler, headless=True, skip_fill=False):
        return {
            "status": "needs_user_input",
            "reason": "Trip.com requires verification before checkout.",
            "confirmation_url": "https://www.trip.com/flights/showfarefirst/?captcha=1",
            "handoff_channel": "provider_verification",
            "screenshot": "",
        }

    monkeypatch.setattr(
        booking_tool_executor_module.playwright_checkout_runner,
        "checkout_to_confirmation",
        fake_checkout,
    )

    state = {
        "messages": [
            HumanMessage(content="@VacayClawBot let's go with 1"),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "proceed_checkout",
                        "args": {
                            "traveler_name": "",
                            "traveler_email": "",
                            "traveler_phone": "",
                            "traveler_gender": "",
                            "traveler_birth_date": "",
                            "traveler_nationality": "",
                            "traveler_doc_type": "",
                            "traveler_doc_number": "",
                            "traveler_doc_expiry": "",
                            "allow_empty_traveler": True,
                            "headless": False,
                        },
                        "id": "tool_checkout",
                        "type": "tool_call",
                    }
                ],
            ),
        ],
        "workspace_id": "telegram:-1003790620984:main",
        "booking_context": {"selected_offer_id": "offer_1"},
        "booking_offers": [{"id": "offer_1"}],
        "selected_offer": {
            "id": "offer_1",
            "title": "Demo flight",
            "provider": "trip.com",
            "live_session_id": "trip_session_demo",
        },
        "booking_result": {},
    }

    result = asyncio.run(booking_tool_executor_module.booking_tool_executor(state))

    assert result["booking_context"]["checkout_retry_turn_key"] == "@vacayclawbot let's go with 1"
