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

    # Multi-step plan by orchestator
    # e.g. search for sushi restaurants > add it to day 1 
    plan: Optional[List[str]]

    # which part of plan we're at
    current_step: int 

    # Reflection 
    # Feedback from critic node (only populated if critic says "revise")
    critique: Optional[str]

    # Loop counter
    # Max 3 -> then critic auto-approves (to prevent infinite loop)
    iteration_count: int 

    # agent tracking (so critic knows who to route back to)
    last_agent: Optional[str]

    # human in the loop 
    # proposed changes waiting for user confirmation
    pending_changes: Optional[dict]

    # routing control — set by orchestrator, critic, formatter
    # to tell the graph router which node to go to next
    next_node: Optional[str]
