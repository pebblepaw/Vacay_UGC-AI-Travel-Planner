"""
Critic Node — The Reflection/Self-Critique layer.

This implements the REFLECTION pattern: after an agent makes changes,
the critic validates them before the user sees the result.

CHECKS:
1. Timing: Do time_slots overlap? Is the day unreasonably long?
2. Geography: Are POIs on the same day in the same general area?
3. Intensity: Are there consecutive high-intensity activities?
4. Completeness: Did the modification address the user's original request?
5. Destructiveness: Were too many POIs deleted? Is a day empty?

DECISIONS:
- 'approve' → Changes are good. Go to response_formatter.
- 'revise' → Issues found. Send back to the agent with feedback.
- 'confirm' → Destructive change detected. Ask user to confirm (HITL).
"""

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings
from backend.agent.state import AgentState

critic_prompt = ChatPromptTemplate.from_template("""You are a Trip Critic. You review modifications made to a travel itinerary and check for issues.

    CURRENT TRIP STATE (after modifications):
    {trip_context}

    RECENT ACTIONS TAKEN:
    {recent_actions}

    ORIGINAL USER REQUEST:
    {user_request}

    Check for these issues:
    1. TIMING: Do any time_slots overlap on the same day? Is any day longer than 12 hours (9am-9pm)?
    2. GEOGRAPHY: Are all POIs on the same day within a reasonable area? (e.g., not one in Shinjuku and one 50km away on the same day)
    3. INTENSITY: Are there 3+ consecutive high-intensity activities? That's exhausting.
    4. COMPLETENESS: Did the changes actually address what the user asked for?
    5. EMPTY DAYS: Is any day now empty (0 POIs)?
    6. DESTRUCTIVE: Were more than 2 POIs deleted, or does any day have only 1 POI left?

    Return ONLY a JSON object:
    {{
        "decision": "approve" | "revise" | "confirm",
        "reasoning": "Brief explanation of your assessment",
        "suggestions": "Specific suggestions for improvement (only if revise)"
    }}

    RULES:
    - If everything looks fine → "approve"
    - If there are fixable issues → "revise" with specific suggestions
    - If changes are destructive (day emptied, 3+ POIs deleted) → "confirm" (ask user)
    - When in doubt, "approve" — don't be overly strict
    """)


def _format_trip_with_ids(trip) -> str:
    """Format trip for critic review."""
    if not trip:
        return "No trip loaded."

    lines = [f"Trip: {trip.title}"]
    for day in trip.days:
        lines.append(f"\nDay {day.day_number} ({day.date}): [{len(day.pois)} POIs]")
        for poi in day.pois:
            lines.append(
                f"  [{poi.id}] {poi.name} | {poi.category} | {poi.time_slot} "
                f"| priority:{poi.priority} | intensity:{poi.intensity}"
            )
    return "\n".join(lines)


def _extract_recent_actions(messages) -> str:
    """Extract recent tool results from message history."""
    actions = []
    for msg in messages[-10:]:
        # ToolMessages contain the results of tool executions
        if hasattr(msg, "type") and msg.type == "tool":
            actions.append(msg.content)
    return "\n".join(actions) if actions else "No tool actions recorded."


def critic_node(state: AgentState) -> dict:
    """Critic: validates trip modifications and decides approve/revise/confirm."""

    llm = ChatGoogleGenerativeAI(
        model=settings.GEMINI_MODEL,
        api_key=settings.GEMINI_API_KEY,
        temperature=0,
    )

    chain = critic_prompt | llm | JsonOutputParser()

    trip = state.get("trip")
    messages = state["messages"]
    iteration_count = state.get("iteration_count", 0)

    # ── Safety: auto-approve after 3 iterations to prevent infinite loops ──
    if iteration_count >= 3:
        return {
            "next_node": "approve",
            "critique": "",
            "iteration_count": iteration_count,
        }

    trip_context = _format_trip_with_ids(trip)
    recent_actions = _extract_recent_actions(messages)

    # Find the original user request (first HumanMessage)
    user_request = ""
    for msg in messages:
        if hasattr(msg, "type") and msg.type == "human":
            user_request = msg.content
            break

    try:
        result = chain.invoke({
            "trip_context": trip_context,
            "recent_actions": recent_actions,
            "user_request": user_request,
        })

        decision = result.get("decision", "approve")
        reasoning = result.get("reasoning", "")
        suggestions = result.get("suggestions", "")

        critique_text = ""
        if decision == "revise":
            critique_text = f"{reasoning}. Suggestions: {suggestions}"

        return {
            "next_node": decision,  # Used by critic_router in graph.py
            "critique": critique_text,
            "iteration_count": iteration_count + 1,
        }

    except Exception as e:
        # If critic fails, auto-approve
        return {
            "next_node": "approve",
            "critique": "",
            "iteration_count": iteration_count,
        }