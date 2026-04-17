"""Search Agent Node."""

from __future__ import annotations

from dataclasses import dataclass

from langchain_core.messages import SystemMessage

from backend.agent.state import AgentState
from backend.agent.tools.trip_tools import search_places
from backend.app_config import get_assistant_language_instruction
from backend.llm import get_agent_llm


@dataclass(frozen=True)
class MealAnchor:
    day_number: int
    before_name: str
    after_name: str


def _get_trip_city(trip) -> str:
    if not trip:
        return ""
    return trip.title


def _time_to_minutes(text: str) -> int | None:
    parts = text.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour = int(parts[0])
        minute = int(parts[1])
    except ValueError:
        return None
    return hour * 60 + minute


def _slot_midpoint(time_slot: str) -> int | None:
    parts = [part.strip() for part in time_slot.split("-")]
    if len(parts) != 2:
        return None
    start = _time_to_minutes(parts[0])
    end = _time_to_minutes(parts[1])
    if start is None or end is None:
        return None
    return (start + end) // 2


def _infer_meal_anchor(trip, instruction: str) -> MealAnchor | None:
    if not trip:
        return None

    lowered = instruction.lower()
    meal_targets = {
        "breakfast": 9 * 60,
        "brunch": 11 * 60,
        "lunch": 12 * 60 + 30,
        "noon": 12 * 60 + 30,
        "dinner": 19 * 60,
    }
    target = next((minutes for keyword, minutes in meal_targets.items() if keyword in lowered), None)
    if target is None:
        generic_meal_terms = (
            "meal",
            "restaurant",
            "place to eat",
            "somewhere to eat",
            "food",
            "eat",
        )
        if any(term in lowered for term in generic_meal_terms):
            target = 12 * 60 + 30
    if target is None:
        return None

    best: tuple[int, MealAnchor] | None = None
    for day in trip.days:
        scored = []
        for poi in day.pois:
            midpoint = _slot_midpoint(poi.time_slot)
            if midpoint is not None:
                scored.append((midpoint, poi.name))
        if not scored:
            continue

        before = max((item for item in scored if item[0] <= target), default=None, key=lambda item: item[0])
        after = min((item for item in scored if item[0] >= target), default=None, key=lambda item: item[0])
        if not before and not after:
            continue

        before_name = before[1] if before else (after[1] if after else "")
        after_name = after[1] if after else before_name
        distance = 0
        if before:
            distance += abs(target - before[0])
        if after:
            distance += abs(after[0] - target)

        anchor = MealAnchor(
            day_number=day.day_number,
            before_name=before_name,
            after_name=after_name,
        )
        if best is None or distance < best[0]:
            best = (distance, anchor)

    return best[1] if best else None


def build_search_instruction(instruction: str, trip) -> str:
    anchor = _infer_meal_anchor(trip, instruction)
    if not anchor:
        return instruction

    if anchor.before_name == anchor.after_name:
        anchor_text = f"near {anchor.before_name}"
    else:
        anchor_text = f"between {anchor.before_name} and {anchor.after_name}"
    return (
        f"{instruction}\n"
        f"Meal planning context: treat this as a Day {anchor.day_number} meal stop around local mealtime, and search {anchor_text}."
    )


def search_agent_node(state: AgentState) -> dict:
    llm = get_agent_llm(role="search_agent", temperature=0)

    tools = [search_places]
    llm_with_tools = llm.bind_tools(tools)

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    critique = state.get("critique", "")
    messages = state["messages"]
    trip = state.get("trip")

    if plan and current_step < len(plan):
        instruction = plan[current_step]
    else:
        instruction = messages[-1].content

    instruction = build_search_instruction(instruction, trip)
    city_context = _get_trip_city(trip)

    system_content = f"""You are the Search Agent. You find places, restaurants, and activities for travelers.

TRIP CONTEXT: This trip is about "{city_context}".
YOUR TASK: {instruction}
{f"CRITIC FEEDBACK (address this): {critique}" if critique else ""}
{get_assistant_language_instruction()}

GUIDELINES:
- ALWAYS include the city or anchor area in your search query for relevant results.
- Use the search_places tool to find information.
- When presenting results to the user, format them as a clean numbered list.
- Keep descriptions brief (1 sentence per place).
- Do NOT repeat the full itinerary.
- End with a short prompt like "Which one would you like to add?"
- IMPORTANT: Always include the coordinates from the search results. Format: (coords: longitude, latitude).
"""

    import logging as _logging

    _log = _logging.getLogger(__name__)
    _log.info(">>> SEARCH_AGENT NODE entered, instruction=%s", instruction)
    response = llm_with_tools.invoke([SystemMessage(content=system_content)] + list(messages))
    has_tools = bool(getattr(response, "tool_calls", None))
    _log.info(">>> SEARCH_AGENT done, has_tool_calls=%s, content_len=%s", has_tools, len(response.content or ""))

    return {
        "messages": [response],
        "last_agent": "search_agent",
    }
