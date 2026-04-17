from langchain_core.messages import HumanMessage

from backend.agent.nodes.critic import critic_node
from backend.agent.nodes.orchestrator import orchestrator_node


def test_orchestrator_turns_cached_search_selection_into_add_step() -> None:
    state = {
        "messages": [HumanMessage(content="Add no.1")],
        "trip": None,
        "critique": "",
        "plan": None,
        "current_step": 0,
        "search_results": [
            {
                "name": "Xin Rong Ji",
                "description": "Michelin lunch spot",
                "coords": [121.47, 31.23],
                "category": "Food",
                "time_slot": "12:00 - 13:30",
                "day_number": 1,
            }
        ],
    }

    result = orchestrator_node(state)

    assert result["next_node"] == "travel_editor"
    assert "Xin Rong Ji" in result["plan"][0]
    assert "12:00 - 13:30" in result["plan"][0]


def test_critic_uses_request_level_cap() -> None:
    state = {
        "messages": [HumanMessage(content="Replan my day")],
        "trip": None,
        "iteration_count": 0,
        "request_iteration_count": 3,
        "current_user_request": "Replan my day",
        "last_agent": "travel_editor",
    }

    result = critic_node(state)

    assert result["next_node"] == "approve"
