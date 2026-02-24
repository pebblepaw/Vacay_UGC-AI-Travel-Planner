# from langchain_google_genai import ChatGoogleGenerativeAI
# from backend.config import settings
# from backend.agent.state import AgentState
# from backend.agent.tools.trip_tools import optimize_route, shorten_trip

# llm = ChatGoogleGenerativeAI(
#     model="gemini-2.0-flash",
#     api_key=settings.GEMINI_API_KEY
# )

# tools = [optimize_route, shorten_trip] # We'll add add/remove tools later
# llm_with_tools = llm.bind_tools(tools)

# def travel_agent_node(state: AgentState): 
#     plan = state.get('plan','')
#     response = llm_with_tools.invoke(f"You have authority to modify the trip. Execute this plan: {plan}")
#     return {'messages': [response]}