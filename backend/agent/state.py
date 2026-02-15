# State is the shared memory that is passed between all the nodes 
# Holds the conversation history and the data being manipulated (the Trip)

from typing import TypedDict, Annotated, List, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages
from backend.models.schemas import Trip

class AgentState(TypedDict): 

    # add_message appends new messages
    # to enable chat history

    messages: Annotated[List[BaseMessage], add_messages]

    # trip object: mutable, can be updated by nodes 
    trip: Optional[Trip]

    # 'orchestrator', 'travel_agent', 'search_agent', 'chitchat'
    next_node: Optional[str]

    # only for orchestrator to track multi-step plans 
    plan: Optional[str]
    