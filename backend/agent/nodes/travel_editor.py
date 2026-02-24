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

The LLM decides which tool(s) to call based on the plan instruction
and trip context.
"""

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import SystemMessage
from backend.config import settings
from backend.agent.state import AgentState
from backend.agent.tools.trip_tools import (
    delete_poi,
    add_poi,
    swap_poi,
    move_poi,
    replan_day,
    optimize_trip,
)

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

    llm = ChatGoogleGenerativeAI(
        model = settings.GEMINI_MODEL, 
        api_key = settings.GEMINI_API_KEY, 
        temperature=0
    )

    tools = [delete_poi, add_poi, swap_poi, move_poi, replan_day, optimize_trip]
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

    GUIDELINES:
    - Use POI IDs from the trip context above (e.g., poi_1, poi_2) when calling delete_poi, swap_poi, or move_poi.
    - After deleting or adding POIs, consider calling replan_day to fix the schedule.
    - When adding a POI, you MUST provide coordinates. If you don't know exact coords, estimate based on the area.
    - For category, use exactly one of: Food, Art, Nature, Culture, Shopping, Nightlife.
    - For priority/intensity, use exactly one of: high, normal, low.
    - If the task requires information you don't have (like specific restaurant coords), say so — the orchestrator will route to search_agent first.
    - When you're done making changes, respond with a summary of what you did. Do NOT call any more tools."""

    # Use the message history so the LLM sees previous tool results in this loop
    # But replace/add the system message with updated trip context
    system_msg = SystemMessage(content=system_content)

    # Invoke the LLM with tools
    response = llm_with_tools.invoke([system_msg] + list(messages))

    return {
        "messages": [response],
        "last_agent": "travel_editor",
    }

