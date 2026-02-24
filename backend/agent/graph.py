"""
LangGraph agent orchestration for VACAY trip editing.

GRAPH TOPOLOGY:
    orchestrator → {travel_editor, search_agent, chitchat}
    travel_editor ←→ travel_tool_executor (custom, updates trip in state)
    search_agent  ←→ search_tool_node (standard ToolNode)
    both agents   → critic → {approve→formatter, revise→agent, confirm→human_review}
    formatter     → {orchestrator (if more plan steps), END (if done)}
    chitchat      → END
    human_review  → END

KEY DESIGN DECISIONS:
1. Two tool execution patterns (custom vs standard) — shows architectural versatility
2. Critic after every agent action — reflection pattern
3. Bounded iteration — max 3 critique loops
4. Plan continuation in formatter — multi-step plan-and-execute
5. Human-in-the-loop via interrupt_before
"""

from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode, tools_condition
from backend.agent.state import AgentState

# ── Import all nodes ──
from backend.agent.nodes.orchestrator import orchestrator_node
from backend.agent.nodes.travel_editor import travel_editor_node
from backend.agent.nodes.travel_tool_executor import travel_tool_executor
from backend.agent.nodes.search_agent import search_agent_node
from backend.agent.nodes.critic import critic_node
from backend.agent.nodes.response_formatter import response_formatter_node
from backend.agent.nodes.human_review import human_review_node
from backend.agent.nodes.chitchat import chitchat_node

# ── Import search tool for standard ToolNode ──
from backend.agent.tools.trip_tools import search_places

# ── Standard ToolNode for search (only search_places) ──
search_tool_node = ToolNode([search_places])


# ============================================================================
# ROUTER FUNCTIONS
# ============================================================================

def orchestrator_router(state: AgentState) -> str:
    """Route from orchestrator to the appropriate agent."""
    return state.get("next_node", "chitchat")


def travel_editor_router(state: AgentState) -> str:
    """Route from travel editor: to tool executor (if tool_calls) or critic (if done).

    This replaces the standard tools_condition with a version that routes to
    our CUSTOM tool executor instead of a standard ToolNode, and to the critic
    instead of END.
    """
    last_message = state["messages"][-1]

    # Check if the LLM wants to call tools
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "travel_tools"
    else:
        return "critic"


def search_agent_router(state: AgentState) -> str:
    """Route from search agent: to standard ToolNode (if tool_calls) or critic (if done)."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "search_tools"
    else:
        return "critic"


def critic_router(state: AgentState) -> str:
    """Route from critic based on its decision."""
    decision = state.get("next_node", "approve")
    last_agent = state.get("last_agent", "travel_editor")

    if decision == "approve":
        return "response_formatter"
    elif decision == "revise":
        return last_agent  # Send back to the agent that needs to fix things
    elif decision == "confirm":
        return "human_review"
    else:
        return "response_formatter"


def formatter_router(state: AgentState) -> str:
    """Route from formatter: back to orchestrator (if more steps) or END."""
    next_node = state.get("next_node", "done")

    if next_node == "continue_plan":
        return "orchestrator"
    else:
        return END


# ============================================================================
# BUILD THE GRAPH
# ============================================================================

workflow = StateGraph(AgentState)

# ── Add all nodes ──
workflow.add_node("orchestrator", orchestrator_node)
workflow.add_node("travel_editor", travel_editor_node)
workflow.add_node("travel_tools", travel_tool_executor)      # Custom executor
workflow.add_node("search_agent", search_agent_node)
workflow.add_node("search_tools", search_tool_node)           # Standard ToolNode
workflow.add_node("critic", critic_node)
workflow.add_node("response_formatter", response_formatter_node)
workflow.add_node("human_review", human_review_node)
workflow.add_node("chitchat", chitchat_node)

# ── Entry point ──
workflow.set_entry_point("orchestrator")

# ── Orchestrator → agents ──
workflow.add_conditional_edges(
    "orchestrator",
    orchestrator_router,
    {
        "travel_editor": "travel_editor",
        "search_agent": "search_agent",
        "chitchat": "chitchat",
    },
)

# ── Travel Editor tool loop ──
# If LLM returned tool_calls → custom executor → back to editor
# If LLM returned final response (no tool_calls) → critic
workflow.add_conditional_edges(
    "travel_editor",
    travel_editor_router,
    {
        "travel_tools": "travel_tools",
        "critic": "critic",
    },
)
workflow.add_edge("travel_tools", "travel_editor")  # Loop: executor → editor

# ── Search Agent tool loop ──
# Same pattern but with standard ToolNode
workflow.add_conditional_edges(
    "search_agent",
    search_agent_router,
    {
        "search_tools": "search_tools",
        "critic": "critic",
    },
)
workflow.add_edge("search_tools", "search_agent")  # Loop: ToolNode → agent

# ── Critic → routing ──
workflow.add_conditional_edges(
    "critic",
    critic_router,
    {
        "response_formatter": "response_formatter",
        "travel_editor": "travel_editor",
        "search_agent": "search_agent",
        "human_review": "human_review",
    },
)

# ── Response Formatter → orchestrator (if more steps) or END ──
workflow.add_conditional_edges(
    "response_formatter",
    formatter_router,
    {
        "orchestrator": "orchestrator",
        END: END,
    },
)

# ── Terminal nodes ──
workflow.add_edge("chitchat", END)
workflow.add_edge("human_review", END)

# ── Compile with human-in-the-loop interrupt ──
app = workflow.compile(interrupt_before=["human_review"])