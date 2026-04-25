"""
Travel Editor Node — The specialist for trip modifications.

This is a ReAct agent: it reasons about what to do, calls tools, sees results,
and repeats until done. The tool execution happens in travel_tool_executor.py.

TOOLS AVAILABLE:
- delete_poi(poi_id) — Remove a POI
- add_poi(day, name, category, coords, ...) — Add a new POI
- swap_poi(old_id, new_name, ...) — Replace a POI
- move_poi(poi_id, target_day) — Move between days
- replan_day(day_number) — Re-sequence a day
- optimize_trip() — Cross-day optimization
- resize_trip(target_days) — Repack the itinerary into a new day count
- add_meal_stop(day_number, meal_type, cuisine_hint) — Insert a restaurant stop

The LLM decides which tool(s) to call based on the plan instruction
and trip context.
"""

import re
import uuid

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
from backend.agent.state import AgentState
from backend.agent.tools.trip_tools import (
    delete_poi,
    add_poi,
    swap_poi,
    move_poi,
    replan_day,
    optimize_trip,
    resize_trip,
    add_meal_stop,
)
from backend.app_config import get_assistant_language_instruction
from backend.llm import get_agent_llm


def _tool_result_summary(instruction: str, messages) -> AIMessage | None:
    if not messages:
        return None

    last_message = messages[-1]
    if not isinstance(last_message, ToolMessage):
        return None

    content = (last_message.content or "").strip()
    if not content:
        return None

    lowered = (instruction or "").lower()
    if any(keyword in lowered for keyword in ("resize", "shrink", "reduce", "expand", "stretch")):
        return AIMessage(content=content)

    if any(keyword in lowered for keyword in ("lunch", "dinner", "brunch", "breakfast", "restaurant", "food")):
        return AIMessage(content=content)

    if "replan" in lowered or "optimize" in lowered:
        return AIMessage(content=content)

    return None


def _deterministic_tool_message(instruction: str, messages) -> AIMessage | None:
    followup = _tool_result_summary(instruction, messages)
    if followup is not None:
        return followup

    lowered = (instruction or "").lower()

    resize_match = re.search(r"\b(?:resize|shrink|reduce|expand|stretch)\b.*?\bto\s+(\d+)\s+days?\b", lowered)
    if not resize_match:
        resize_match = re.search(r"\b(\d+)\s*-\s*day\b", lowered)
    if resize_match:
        target_days = int(resize_match.group(1))
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "resize_trip",
                    "args": {"target_days": target_days},
                    "id": f"auto_{uuid.uuid4().hex[:10]}",
                    "type": "tool_call",
                }
            ],
        )

    meal_match = re.search(
        r"\badd(?:\s+a)?\s+(lunch|dinner|brunch)\b.*?\bday\s+(\d+)\b",
        lowered,
    )
    if meal_match:
        meal_type = meal_match.group(1)
        day_number = int(meal_match.group(2))
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "add_meal_stop",
                    "args": {
                        "day_number": day_number,
                        "meal_type": meal_type,
                        "cuisine_hint": "",
                    },
                    "id": f"auto_{uuid.uuid4().hex[:10]}",
                    "type": "tool_call",
                }
            ],
        )

    replan_match = re.search(r"\breplan\b.*?\bday\s+(\d+)\b", lowered)
    if replan_match:
        day_number = int(replan_match.group(1))
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "replan_day",
                    "args": {"day_number": day_number},
                    "id": f"auto_{uuid.uuid4().hex[:10]}",
                    "type": "tool_call",
                }
            ],
        )

    if "optimize trip" in lowered or "optimize itinerary" in lowered:
        return AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "optimize_trip",
                    "args": {},
                    "id": f"auto_{uuid.uuid4().hex[:10]}",
                    "type": "tool_call",
                }
            ],
        )

    return None

def _format_trip_with_ids(trip) -> str:
    """Format trip for LLM context. Same as orchestrator version."""
    if not trip:
        return "No trip loaded."

    lines = [f"Trip: {trip.title}"]
    for day in trip.days:
        lines.append(f"\nDay {day.day_number} ({day.date}):")
        if not day.pois:
            lines.append("  (no locations)")
        for poi in day.pois:
            lines.append(
                f"  [{poi.id}] {poi.name} | {poi.category} | {poi.time_slot} "
                f"| priority:{poi.priority} | intensity:{poi.intensity} | {poi.visit_duration}min "
                f"| coords:({poi.coords[0]:.4f}, {poi.coords[1]:.4f})"
            )
    return "\n".join(lines)

def travel_editor_node(state: AgentState) -> dict:
    """Travel Editor: reasons about trip modifications and calls tools.

    The LLM receives:
    1. System prompt with tool usage guidelines
    2. The full trip context (with POI IDs and coords)
    3. The plan instruction from the orchestrator
    4. Any critique feedback from previous iterations
    5. The message history (including previous tool results)
    """

    llm = get_agent_llm(role="travel_editor", temperature=0)

    tools = [
        delete_poi,
        add_poi,
        swap_poi,
        move_poi,
        replan_day,
        optimize_trip,
        resize_trip,
        add_meal_stop,
    ]
    llm_with_tools = llm.bind_tools(tools)


    trip = state.get("trip")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    critique = state.get("critique", "")
    messages = state["messages"]

    # Get the current step instruction
    if plan and current_step < len(plan):
        instruction = plan[current_step]
    else:
        instruction = messages[-1].content

    trip_context = _format_trip_with_ids(trip)

    # Build the system message with trip context
    system_content = f"""You are the Travel Editor agent. You modify trip itineraries using tools.

    CURRENT TRIP:
    {trip_context}

    YOUR TASK: {instruction}

    {f"CRITIC FEEDBACK (address this): {critique}" if critique else ""}
    {get_assistant_language_instruction()}

    GUIDELINES:
    - Use POI IDs from the trip context above (e.g., poi_1, poi_2) when calling delete_poi, swap_poi, or move_poi.
    - After deleting or adding POIs, consider calling replan_day to fix the schedule.
    - If the user wants fewer or more days, call resize_trip with the requested day count.
    - If the user wants lunch, dinner, brunch, or restaurants added into the trip, call add_meal_stop for the correct day.
    - For category, use exactly one of: Food, Art, Nature, Culture, Shopping, Nightlife.
    - For priority/intensity, use exactly one of: high, normal, low.
    - When you're done making changes, respond with a summary of what you did. Do NOT call any more tools.

    CRITICAL — NEVER ASK THE USER FOR INFORMATION:
    - NEVER ask for coordinates. If coords appear in conversation history (from search results), use them. Otherwise pass longitude=0, latitude=0 — the system will auto-geocode.
    - NEVER ask for a time. Pick a sensible default based on the category:
      * Food (lunch): "12:00 - 13:30"
      * Food (dinner): "19:00 - 20:30"
      * Nature: "09:00 - 11:00"
      * Culture: "10:00 - 12:00"
      * Art: "14:00 - 16:00"
      * Shopping: "15:00 - 17:00"
      * Nightlife: "20:00 - 22:00"
    - NEVER ask for any other details. Use reasonable defaults and just add the POI.
    - If the user selected an item from search results, look in the conversation history for coords and details."""

    # Use the message history so the LLM sees previous tool results in this loop
    # But replace/add the system message with updated trip context
    system_msg = SystemMessage(content=system_content)

    # Invoke the LLM with tools
    import logging as _logging
    _log = _logging.getLogger(__name__)
    _log.info(f">>> TRAVEL_EDITOR NODE entered, instruction={instruction}, msg_count={len(messages)}")
    response = _deterministic_tool_message(instruction, messages) or llm_with_tools.invoke([system_msg] + list(messages))
    has_tools = bool(getattr(response, 'tool_calls', None))
    _log.info(f">>> TRAVEL_EDITOR done, has_tool_calls={has_tools}, tool_names={[tc['name'] for tc in (response.tool_calls or [])]}")

    return {
        "messages": [response],
        "last_agent": "travel_editor",
    }
