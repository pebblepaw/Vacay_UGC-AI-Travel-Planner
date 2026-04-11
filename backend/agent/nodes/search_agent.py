
"""
Search Agent Node — Finds external information (places, restaurants, activities).

Uses standard LangGraph tool calling with ToolNode (unlike Travel Editor which
uses a custom executor). This works because search_places only needs a query
string — no trip state access required.

FLOW:
  search_agent → (tool_calls?) → search_tool_node → search_agent → (no tool_calls) → critic
"""

from langchain_core.messages import SystemMessage
from backend.agent.state import AgentState
from backend.agent.tools.trip_tools import search_places
from backend.llm import get_agent_llm
# from langchain_core.messages import AIMessage

def _get_trip_city(trip) -> str:
    """Try to extract the city/area from the trip title or POI names."""
    if not trip:
        return ""
    
    # Simple heuristic: return the trip title (should contain the city)
    return trip.title

def search_agent_node(state: AgentState) -> dict:
    """Search agent: finds places using Tavily + geocoding."""

    llm = get_agent_llm(temperature=0)

    tools = [search_places]
    llm_with_tools = llm.bind_tools(tools)

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    critique = state.get("critique", "")
    messages = state["messages"]
    trip = state.get("trip")

    # Get instruction
    if plan and current_step < len(plan):
        instruction = plan[current_step]
    else:
        instruction = messages[-1].content

    city_context = _get_trip_city(trip)

    system_content = f"""You are the Search Agent. You find places, restaurants, and activities for travelers.

    TRIP CONTEXT: This trip is about "{city_context}".

    YOUR TASK: {instruction}

    {f"CRITIC FEEDBACK (address this): {critique}" if critique else ""}

    GUIDELINES:
    - ALWAYS include the city/area name in your search query for relevant results.
    - Use the search_places tool to find information.
    - When presenting results to the user, format them as a clean numbered list.
    - Keep descriptions brief (1 sentence per place).
    - Do NOT repeat the full itinerary.
    - End with a short prompt like "Which one would you like to add?"

    FORMATTING EXAMPLE:
    Here are some options near [area]:

    1. **Restaurant Name** — Brief description of cuisine/vibe (coords: 2.3522, 48.8566)
    2. **Restaurant Name** — Brief description of cuisine/vibe (coords: 2.3488, 48.8534)
    3. **Restaurant Name** — Brief description of cuisine/vibe (coords: 2.3401, 48.8612)

    Which one would you like to add?

    IMPORTANT: Always include the coordinates from the search results. Format: (coords: longitude, latitude).
    This ensures the next agent can place the POI on the map without asking the user."""

    import logging as _logging
    _log = _logging.getLogger(__name__)
    _log.info(f">>> SEARCH_AGENT NODE entered, instruction={instruction}")
    system_msg = SystemMessage(content=system_content)
    response = llm_with_tools.invoke([system_msg] + list(messages))
    has_tools = bool(getattr(response, 'tool_calls', None))
    _log.info(f">>> SEARCH_AGENT done, has_tool_calls={has_tools}, content_len={len(response.content or '')}")

    return {
        "messages": [response],
        "last_agent": "search_agent",
    }