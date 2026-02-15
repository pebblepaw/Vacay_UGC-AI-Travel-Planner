'''Decides the flow of query > which tools '''

from typing import Literal
from langgraph.graph import StateGraph, END
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from langgraph.prebuilt import ToolNode, tools_condition
from backend.config import settings
from backend.agent.state import AgentState

# Import nodes 
from backend.agent.nodes.orchestrator import orchestrator_node
from backend.agent.nodes.search_agent import search_agent_node
from backend.agent.nodes.travel_agent import travel_agent_node
from backend.agent.nodes.chitchat import chitchat_node
from backend.agent.tools.trip_tools import optimize_route, shorten_trip, search_places

# Added gemini_model to the settings file, check again. 
llm = ChatGoogleGenerativeAI(model_name=settings.GEMINI_MODEL, 
                            api_key=settings.GEMINI_API_KEY,
                            temperature=0)

all_tools = [optimize_route, shorten_trip, search_places]
tool_node = ToolNode(all_tools)

# Build the graph
workflow = StateGraph(AgentState)
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("search_agent", search_agent_node)
workflow.add_node("travel_agent", travel_agent_node)
workflow.add_node("chitchat", chitchat_node)
workflow.add_node("tools", tool_node)

# Set entry point
workflow.set_entry_point("orchestrator") 

# Orchestrator router logic
workflow.add_conditional_edges(
    "orchestrator",
    lambda x: x['next_node'],
    {
        'travel_agent': 'travel_agent',
        'search_agent': 'search_agent',
        'chitchat': 'chitchat'  
    }
)


workflow.add_conditional_edges(
    "travel_agent",
    tools_condition
)

workflow.add_conditional_edges(
    "search_agent",
    tools_condition
)

# connect Chatbot & Tools nodes 
workflow.add_edge("tools","orchestrator") # Loop back 
workflow.add_edge('chitchat', END)

app = workflow.compile() 



