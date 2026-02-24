
"""
Response Formatter Node — Produces the final user-facing message.

This is the last node before END. It:
1. Summarizes what changes were made
2. Shows the updated trip overview
3. Formats everything nicely for the chat UI

This node also handles advancing the plan to the next step.
If there are more steps in the plan, it routes back to the orchestrator.
"""

from langchain_core.messages import AIMessage
from backend.agent.state import AgentState


def _format_trip_summary(trip) -> str:
    """Compact trip summary for the chat response."""
    if not trip:
        return ""

    lines = []
    for day in trip.days:
        poi_names = [f"{p.name} ({p.time_slot})" for p in day.pois]
        lines.append(f"📅 Day {day.day_number}: {', '.join(poi_names)}")
    return "\n".join(lines)


def response_formatter_node(state: AgentState) -> dict:
    """Format the final response and check if there are more plan steps."""

    messages = state["messages"]
    trip = state.get("trip")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)

    # ── Find the last substantive AI response ──
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            last_ai_content = msg.content
            break

    # ── Check if there are more plan steps ──
    next_step = current_step + 1
    has_more_steps = plan and next_step < len(plan)

    if has_more_steps:
        # More steps to execute — route back to orchestrator
        return {
            "current_step": next_step,
            "next_node": "continue_plan",  # Signal to graph router
        }

    # ── Final response: format with trip summary ──
    trip_summary = _format_trip_summary(trip)

    formatted = last_ai_content
    if trip_summary:
        formatted += f"\n\n**Updated Itinerary:**\n{trip_summary}"

    return {
        "messages": [AIMessage(content=formatted)],
        "next_node": "done",
    }