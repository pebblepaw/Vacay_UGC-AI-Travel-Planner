from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings
from backend.agent.state import AgentState
from backend.agent.tools.trip_tools import search_places
from langchain_core.messages import AIMessage


llm = ChatGoogleGenerativeAI(
    model_name="gemini-2.0-flash",
    api_key=settings.GEMINI_API_KEY
)


tools = [search_places]
llm_with_tools = llm.bind_tools(tools)

def search_agent_node(state: AgentState): 


    plan = state.get('plan','')

    response = llm_with_tools.invoke(f"Execute this plan: {plan}")

    return{"messages": [response]}

