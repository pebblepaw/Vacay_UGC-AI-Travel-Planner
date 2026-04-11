"""
Orchestrator Node — The Brain of the agent.

This is the SUPERVISOR pattern: it doesn't do work itself, it delegates.

On each invocation, it either:
  1. Decomposes a NEW user request into a plan (list of steps) 
  2. Advances to the NEXT step of an existing plan
  3. Routes to the appropriate specialist agent for the current step

PLAN-AND-EXECUTE pattern example: 
  User: "Replace the ramen with a nice sushi place"
  Plan: ["search for upscale sushi restaurants near Shinjuku", "swap poi_2 with best result"]
  Step 0 → search_agent
  Step 1 → travel_editor

"""

from backend.agent import state
import re
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from backend.agent.state import AgentState
from backend.llm import get_agent_llm

orchestrator_prompt = ChatPromptTemplate.from_template("""
                                                        
    You are the Orchestrator for a travel itinerary editor. You manage a team of specialist agents:

    1. 'travel_editor' — Modifies the trip itinerary (add, delete, swap, move POIs; replan a day; optimize the trip)
    2. 'search_agent' — Searches the web for places, restaurants, activities (use when the user wants to FIND something NEW)
    3. 'booking_agent' — Handles booking workflows (find offers, select offer, proceed to checkout confirmation page)
    4. 'chitchat' — Handles greetings, thank-yous, off-topic questions

    CURRENT TRIP:
    {trip_context}

    USER REQUEST: {input}

    CONVERSATION HISTORY (last messages):
    {history}

    PREVIOUS CRITIQUE (if any): {critique}

    YOUR TASK:
    Analyze the user's request IN CONTEXT of the conversation history and create a plan.

    CRITICAL — FOLLOW-UP DETECTION:
    Look at the CONVERSATION HISTORY carefully. If the previous agent message presented options/results 
    (e.g. a list of restaurants) and the user's current message is selecting one of those options 
    (e.g. "Cafe 12", "the first one", "Let's go with X", "1", "option 2"), then:
    - This is a FOLLOW-UP SELECTION, NOT a new search request
    - Route to 'travel_editor' with an instruction to ADD the selected place to the itinerary
    - Include the place name, category, coordinates (if shown), and any details from the previous search results in the instruction
    - If coordinates were shown (e.g. "coords: 2.35, 48.85"), include them in the instruction
    - Specify which day to add it to (pick a reasonable day based on the trip context)
    - Specify a reasonable time slot based on the type of activity (e.g. lunch = "12:00 - 13:30")
    - Do NOT route back to search_agent — the search is already done
    - Do NOT ask the user any follow-up questions

    RULES:
    - Simple requests have 1 step. Example: "Remove the ramen" → ["delete the ramen POI"]
    - Complex requests need multiple steps. Example: "Replace ramen with sushi" → ["search for sushi restaurants near Shinjuku Tokyo", "swap poi_2 with the best sushi result"]
    - If the user just wants to chat or says hello → single step routed to chitchat
    - If the user asks to book tickets/hotels/transport, route to booking_agent
    - If the user asks for flight options on trip.com, ALWAYS route to booking_agent (not search_agent)
    - When searching, ALWAYS include the city/area in the search query
    - If a critique was provided, adjust your plan to address it

    Return ONLY a JSON object:
    {{
        "next_node": "travel_editor" | "search_agent" | "booking_agent" | "chitchat",
        "plan": ["step 1 description", "step 2 description", ...],
        "current_step_instruction": "The specific instruction for the agent handling this step"
    }}

    EXAMPLES:
    - User: "Hello!" → {{"next_node": "chitchat", "plan": ["greet user"], "current_step_instruction": "Say hello and offer help with the trip"}}
    - User: "Delete TeamLab" → {{"next_node": "travel_editor", "plan": ["delete TeamLab Borderless"], "current_step_instruction": "Delete the POI named TeamLab Borderless (poi_1)"}}
    - User: "Find me a good sushi place" → {{"next_node": "search_agent", "plan": ["search for sushi restaurants"], "current_step_instruction": "Search for highly-rated sushi restaurants in Tokyo"}}
    - User: "Book a train from Tokyo to Osaka next Friday" → {{"next_node": "booking_agent", "plan": ["find train offers from Tokyo to Osaka for next Friday", "select best-value offer and proceed to checkout confirmation"], "current_step_instruction": "Find train offers from Tokyo to Osaka for next Friday with 1 adult"}}
    - User: "List flights from Tokyo to Shanghai on trip.com" → {{"next_node": "booking_agent", "plan": ["find flight offers from Tokyo to Shanghai on trip.com"], "current_step_instruction": "Find flight offers on trip.com"}}
    - User: "Replace ramen with something fancier" → {{"next_node": "search_agent", "plan": ["search for upscale restaurants near Shinjuku Tokyo", "swap the ramen POI with the best result"], "current_step_instruction": "Search for upscale restaurants near Shinjuku Tokyo"}}
    - User: "Optimize my trip" → {{"next_node": "travel_editor", "plan": ["optimize the full trip"], "current_step_instruction": "Run optimize_trip to rebalance POIs across days by geography"}}
    - [After search results showed restaurant options] User: "Let's go with Cafe 12" → {{"next_node": "travel_editor", "plan": ["add Cafe 12 to the itinerary"], "current_step_instruction": "Add a new POI named 'Cafe 12' with category 'Food' to Day 1 at time '12:00 - 13:30'. Coordinates from search: longitude=2.3522, latitude=48.8566. Use add_poi tool. Do NOT ask the user any questions."}}
    - [After search results showed options] User: "1" → {{"next_node": "travel_editor", "plan": ["add the first search result to the itinerary"], "current_step_instruction": "Add a new POI named '[first result name]' with category 'Food' to Day 1 at time '12:00 - 13:30'. Use coords from search results if available, otherwise use 0,0. Use add_poi tool. Do NOT ask any questions."}}
    """)

# Convert pydantic trip data structure -> to string 
def _format_trip_with_ids(trip) -> str:
    '''
    Format trip data as text with POI IDs for the LLM to reference. 
    
    Example output: 
        Day 1 (2024-04-15):
        [poi_1] TeamLab Borderless | Art | 10:00-13:00 | priority:high | intensity:normal | 180min
        [poi_2] Shinjuku Gyoen Ramen | Food | 13:30-14:30 | priority:normal | intensity:normal | 60min
    '''

    if not trip: 
        return "No trip created yet." 
    
    lines = [f"Trip: {trip.title}"]
    for day in trip.days: 
        lines.append(f"\nDay {day.day_number} ({day.date}):")

        if not day.pois: 
            lines.append(" (no locations)")

        for poi in day.pois: 
            lines.append(
                f" [{poi.id}] {poi.name} | {poi.category} | {poi.time_slot} | priority:{poi.priority} | intensity:{poi.intensity} | {poi.visit_duration}min"
            )
    return "\n".join(lines)

def orchestrator_node(state: AgentState) -> dict: 
    import logging
    _log = logging.getLogger(__name__)
    _log.info(">>> ORCHESTRATOR NODE entered")

    llm = get_agent_llm(temperature=0)

    chain = orchestrator_prompt | llm | JsonOutputParser() 

    messages = state["messages"]
    trip = state.get("trip")
    critique = state.get("critique", "")
    plan = state.get("plan")
    current_step = state.get("current_step", 0) 

    # ── If we're mid-plan and advancing to the next step ──
    if plan and current_step > 0 and current_step < len(plan):
        # We're continuing an existing plan, not starting fresh
        step_instruction = plan[current_step]

        # Decide which agent handles this step
        lowered = step_instruction.lower()
        if any(kw in lowered for kw in ["book", "booking", "checkout", "ticket", "hotel", "flight", "train"]):
            next_node = "booking_agent"
        elif any(kw in lowered for kw in ["search", "find", "look for"]):
            next_node = "search_agent"
        else:
            next_node = "travel_editor"

        return {
            "next_node": next_node,
            "plan": plan,
            "current_step": current_step,
            "critique": "",  # Clear critique when advancing
        }

    # ── New request or first step: short-circuit booking queries ──
    last_msg = messages[-1].content
    lowered_msg = last_msg.lower()
    booking_keywords = [
        "book",
        "booking",
        "ticket",
        "flight",
        "train",
        "hotel",
        "trip.com",
        "tripcom",
        "机票",
        "订票",
        "航班",
        "单程",
        "往返",
        "经济舱",
        "商务舱",
        "头等舱",
        "机场",
    ]
    has_option_id = bool(re.search(r"\boffer_\d+\b|option_id\s*:\s*offer_\d+", last_msg, re.IGNORECASE))
    has_booking_context = bool(state.get("booking_context") or state.get("booking_offers"))
    has_booking_history = any(
        isinstance(m.content, str)
        and re.search(r"offer_\d+|可选航班|请选择一个航班|option_id", m.content, re.IGNORECASE)
        for m in messages[-10:]
    )
    if (
        has_option_id
        or has_booking_context
        or has_booking_history
        or any(k in lowered_msg or k in last_msg for k in booking_keywords)
    ):
        return {
            "next_node": "booking_agent",
            "plan": [f"find booking options on trip.com for: {last_msg}"],
            "current_step": 0,
            "critique": "",
            "iteration_count": 0,
        }

    # ── New request or first step: ask LLM to plan ──
    trip_str = _format_trip_with_ids(trip)

    # Build history with role labels so LLM can track the conversation
    history_lines = []
    for m in messages[-10:]:  # Last 10 messages for context
        if hasattr(m, 'type'):
            if m.type == 'human':
                history_lines.append(f"USER: {m.content}")
            elif m.type == 'ai' and m.content:
                # Truncate long AI responses to keep prompt manageable
                content = m.content[:500] + "..." if len(m.content) > 500 else m.content
                history_lines.append(f"AGENT: {content}")
    history = "\n".join(history_lines) if history_lines else "No previous conversation."

    try:
        result = chain.invoke({
            "input": last_msg,
            "trip_context": trip_str,
            "history": history,
            "critique": critique or "None",
        })

        _log.info(f">>> ORCHESTRATOR plan={result.get('plan')}, next={result['next_node']}")
        return {
            "next_node": result["next_node"],
            "plan": result.get("plan", [last_msg]),
            "current_step": 0,
            "critique": "",  # Clear old critique
            "iteration_count": 0,  # Reset iteration count for new plan
        }

    except Exception as e:
        # If LLM fails to produce valid JSON, default to chitchat
        return {
            "next_node": "chitchat",
            "plan": ["handle parsing error"],
            "current_step": 0,
            "critique": "",
        }


