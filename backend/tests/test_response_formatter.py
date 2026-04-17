from langchain_core.messages import AIMessage, ToolMessage

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


def test_response_formatter_pauses_search_plan_and_emits_poi_options() -> None:
    state = {
        "messages": [
            ToolMessage(
                content=(
                    '{"results": ['
                    '{"name": "Xin Rong Ji", "description": "Michelin lunch", "coords": [121.47, 31.23]}, '
                    '{"name": "Akin", "description": "Modern cafe", "coords": [121.48, 31.24]}'
                    ']}'
                ),
                tool_call_id="tool_1",
            ),
            AIMessage(content="1. Xin Rong Ji\n2. Akin\nWhich one would you like to add?"),
        ],
        "trip": None,
        "plan": ["Search for lunch locations for Day 1", "Add the selected location to the itinerary"],
        "current_step": 0,
        "last_agent": "search_agent",
        "booking_result": {},
        "booking_offers": [],
        "selected_offer": {},
        "booking_context": {},
    }

    result = response_formatter_node(state)

    assert result["next_node"] == "done"
    assert result["messages"][0].content.startswith("1. Xin Rong Ji")
    assert result["chat_interrupt"]["interrupt_type"] == "poi_selection"
    assert len(result["chat_interrupt"]["options"]) == 2
    assert result["search_results"][0]["name"] == "Xin Rong Ji"
