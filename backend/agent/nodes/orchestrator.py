from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings
from backend.agent.state import AgentState

llm = ChatGoogleGenerativeAI(
    model="gemini-2.0-flash",
    api_key=settings.GEMINI_API_KEY
)

orchestrator_prompt = ChatPromptTemplate.from_template("""
You are the Orchestrator. You manage a team of agents: 
1. 'travel_agent': Modifies the trip (add/remove/move POIs)
2. 'search_agent': Finds info (restaurants, weather, etc.) or "Find X near Y". 
3. 'chitchat': Handles samll talk 

Current Trip Context: 
{trip_context}
User request: {input}
Conversation History: {history}

Analyze the request. Return a JSON with: 
- 'next_node': 'travel_agent', 'search_agent' or 'chitchat'
- 'plan': A specific instruction for that agent (e.g. 'Find western restaurants
near The Bund' or 'Add Joe's Pizza to Day 1'). 
""")

chain = orchestrator_prompt | llm | JsonOutputParser() 

# Convert pydantic trip data structure -> to string 
def _format_trip(trip):
    if not trip: return "No trip created yet."
    summary = []
    for day in trip.days:
            pois = [f"- {p.name} ({p.time_slot})" for p in day.pois]
            summary.append(f"Day {day.day_number}: {', '.join(pois)}")
    return "\n".join(summary)


def orchestrator_node(state: AgentState): 

    last_msg = state['messages'][-1].content
    trip_str = _format_trip(state.get('trip'))
    history = "\n".join([m.content for m in state['messages'][-5:]])

    try: 
        result = chain.invoke({
            'input':last_msg,
            'trip_context': trip_str,
            'history': history
            })
        return {
            'next_node': result['next_node'], 
            'plan': result.get['plan']
        }
    except Exception as e: 
        return {
            'next_node': 'chitchat', 
            'plan': "I didn't understand that."
        }
