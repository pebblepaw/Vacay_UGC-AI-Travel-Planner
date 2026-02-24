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
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings
from backend.agent.state import AgentState

orchestrator_prompt = ChatPromptTemplate.from_template("""
                                                        
    You are the Orchestrator for a travel itinerary editor. You manage a team of specialist agents:

    1. 'travel_editor' — Modifies the trip itinerary (add, delete, swap, move POIs; replan a day; optimize the trip)
    2. 'search_agent' — Searches the web for places, restaurants, activities (use when the user wants to FIND something)
    3. 'chitchat' — Handles greetings, thank-yous, off-topic questions

    CURRENT TRIP:
    {trip_context}

    USER REQUEST: {input}

    CONVERSATION HISTORY (last 5 messages):
    {history}

    PREVIOUS CRITIQUE (if any): {critique}

    YOUR TASK:
    Analyze the user's request and create a plan. A plan is a list of steps to fulfill the request.

    RULES:
    - Simple requests have 1 step. Example: "Remove the ramen" → ["delete the ramen POI"]
    - Complex requests need multiple steps. Example: "Replace ramen with sushi" → ["search for sushi restaurants near Shinjuku Tokyo", "swap poi_2 with the best sushi result"]
    - If the user just wants to chat or says hello → single step routed to chitchat
    - When searching, ALWAYS include the city/area in the search query
    - If a critique was provided, adjust your plan to address it

    Return ONLY a JSON object:
    {{
        "next_node": "travel_editor" | "search_agent" | "chitchat",
        "plan": ["step 1 description", "step 2 description", ...],
        "current_step_instruction": "The specific instruction for the agent handling this step"
    }}

    EXAMPLES:
    - User: "Hello!" → {{"next_node": "chitchat", "plan": ["greet user"], "current_step_instruction": "Say hello and offer help with the trip"}}
    - User: "Delete TeamLab" → {{"next_node": "travel_editor", "plan": ["delete TeamLab Borderless"], "current_step_instruction": "Delete the POI named TeamLab Borderless (poi_1)"}}
    - User: "Find me a good sushi place" → {{"next_node": "search_agent", "plan": ["search for sushi restaurants"], "current_step_instruction": "Search for highly-rated sushi restaurants in Tokyo"}}
    - User: "Replace ramen with something fancier" → {{"next_node": "search_agent", "plan": ["search for upscale restaurants near Shinjuku Tokyo", "swap the ramen POI with the best result"], "current_step_instruction": "Search for upscale restaurants near Shinjuku Tokyo"}}
    - User: "Optimize my trip" → {{"next_node": "travel_editor", "plan": ["optimize the full trip"], "current_step_instruction": "Run optimize_trip to rebalance POIs across days by geography"}}
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

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GEMINI_API_KEY,
        temperature=0
    )

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
        # Simple heuristic: if the step mentions "search"/"find" → search_agent, else → travel_editor
        if any(kw in step_instruction.lower() for kw in ["search", "find", "look for"]):
            next_node = "search_agent"
        else:
            next_node = "travel_editor"

        return {
            "next_node": next_node,
            "plan": plan,
            "current_step": current_step,
            "critique": "",  # Clear critique when advancing
        }

    # ── New request or first step: ask LLM to plan ──
    last_msg = messages[-1].content
    trip_str = _format_trip_with_ids(trip)
    history = "\n".join([m.content for m in messages[-5:]])

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


