from langchain_core.messages import AIMessage

from backend.agent.nodes.response_formatter import response_formatter_node


def test_response_formatter_keeps_booking_follow_up_question() -> None:
    state = {
        "messages": [AIMessage(content="I still need the departure date and number of adults.")],
        "trip": None,
        "plan": [],
        "current_step": 0,
        "last_agent": "booking_agent",
        "booking_result": {},
        "booking_offers": [],
        "selected_offer": {},
        "booking_context": {},
    }

    result = response_formatter_node(state)

    assert result["messages"][0].content == "I still need the departure date and number of adults."


def test_response_formatter_skips_fresh_tab_handoff_for_live_browser_checkout() -> None:
    state = {
        "messages": [AIMessage(content="")],
        "trip": None,
        "plan": [],
        "current_step": 0,
        "last_agent": "booking_agent",
        "booking_result": {
            "status": "needs_user_payment",
            "reason": "Reached pre-payment stage in the live browser.",
            "confirmation_url": "https://www.trip.com/flights/passenger?booking=123",
            "handoff_channel": "live_browser",
        },
        "booking_offers": [],
        "selected_offer": {},
        "booking_context": {"provider_hint": "trip.com"},
    }

    result = response_formatter_node(state)

    assert result["messages"][0].content
    assert result.get("chat_interrupt") is None


def test_response_formatter_uses_remote_browser_copy_for_signed_takeover_page() -> None:
    state = {
        "messages": [AIMessage(content="")],
        "trip": None,
        "plan": [],
        "current_step": 0,
        "last_agent": "booking_agent",
        "booking_result": {
            "status": "needs_user_input",
            "reason": "Reached traveler page in the hosted remote browser.",
            "confirmation_url": "https://demo.vacay.ai/browser?token=signed",
            "handoff_channel": "remote_browser",
        },
        "booking_offers": [],
        "selected_offer": {},
        "booking_context": {"provider_hint": "trip.com"},
    }

    result = response_formatter_node(state)

    assert "remote browser" in result["messages"][0].content.lower()
    assert result["chat_interrupt"]["interrupt_type"] == "open_url"
    assert result["chat_interrupt"]["content"] == "https://demo.vacay.ai/browser?token=signed"


def test_response_formatter_uses_provider_verification_copy_for_trip_captcha() -> None:
    state = {
        "messages": [AIMessage(content="")],
        "trip": None,
        "plan": [],
        "current_step": 0,
        "last_agent": "booking_agent",
        "booking_result": {
            "status": "needs_user_input",
            "reason": "Trip.com requires verification before checkout.",
            "confirmation_url": "https://www.trip.com/flights/showfarefirst/?captcha=1",
            "handoff_channel": "provider_verification",
        },
        "booking_offers": [],
        "selected_offer": {},
        "booking_context": {"provider_hint": "trip.com"},
    }

    result = response_formatter_node(state)

    content = result["messages"][0].content.lower()
    assert "captcha encountered" in content
    assert "verification" in content
    assert "sign in" not in content
    assert result["chat_interrupt"]["content"] == "https://www.trip.com/flights/showfarefirst/?captcha=1"
