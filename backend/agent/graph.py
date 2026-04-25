"""
LangGraph agent orchestration for VACAY trip editing.

GRAPH TOPOLOGY:
    orchestrator → {travel_editor, search_agent, booking_agent, chitchat}
    travel_editor ←→ travel_tool_executor (custom, updates trip in state)
    search_agent  ←→ search_tool_node (standard ToolNode)
    booking_agent ←→ booking_tool_executor (custom, updates booking state)
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
from __future__ import annotations

from contextlib import AbstractContextManager
import logging
import signal
from typing import Any

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.prebuilt import ToolNode, tools_condition

from backend.config import settings
from backend.services.langgraph_supabase_checkpointer import SupabaseWorkspaceCheckpointer
from backend.agent.state import AgentState

# ── Import all nodes ──
from backend.agent.nodes.orchestrator import orchestrator_node
from backend.agent.nodes.travel_editor import travel_editor_node
from backend.agent.nodes.travel_tool_executor import travel_tool_executor
from backend.agent.nodes.search_agent import search_agent_node
from backend.agent.nodes.booking_agent import booking_agent_node
from backend.agent.nodes.booking_tool_executor import booking_tool_executor
from backend.agent.nodes.critic import critic_node
from backend.agent.nodes.response_formatter import response_formatter_node
from backend.agent.nodes.human_review import human_review_node
from backend.agent.nodes.chitchat import chitchat_node

# ── Import search tool for standard ToolNode ──
from backend.agent.tools.trip_tools import search_places

# ── Standard ToolNode for search (only search_places) ──
search_tool_node = ToolNode([search_places])
logger = logging.getLogger(__name__)


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


def booking_agent_router(state: AgentState) -> str:
    """Route from booking agent: tool executor or critic."""
    last_message = state["messages"][-1]

    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "booking_tools"
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
workflow.add_node("booking_agent", booking_agent_node)
workflow.add_node("booking_tools", booking_tool_executor)
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
        "booking_agent": "booking_agent",
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

# ── Booking Agent tool loop ──
workflow.add_conditional_edges(
    "booking_agent",
    booking_agent_router,
    {
        "booking_tools": "booking_tools",
        "critic": "critic",
    },
)
workflow.add_edge("booking_tools", "booking_agent")

# ── Critic → routing ──
workflow.add_conditional_edges(
    "critic",
    critic_router,
    {
        "response_formatter": "response_formatter",
        "travel_editor": "travel_editor",
        "search_agent": "search_agent",
        "booking_agent": "booking_agent",
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

def _compile_graph(checkpointer: PostgresSaver | None = None) -> Any:
    return workflow.compile(interrupt_before=["human_review"], checkpointer=checkpointer)


_compiled_app: Any = _compile_graph()
_checkpointer_context: AbstractContextManager[PostgresSaver] | None = None


def get_graph_app() -> Any:
    return _compiled_app


def _normalize_checkpoint_url(checkpoint_url: str) -> str:
    separator = "&" if "?" in checkpoint_url else "?"
    normalized = checkpoint_url
    if "sslmode=" not in checkpoint_url:
        normalized = f"{normalized}{separator}sslmode=require"
        separator = "&"
    if "connect_timeout=" not in normalized:
        normalized = f"{normalized}{separator}connect_timeout=5"
    return normalized


def configure_graph_checkpointer(conn_string: str | None = None) -> bool:
    global _compiled_app, _checkpointer_context

    close_graph_checkpointer()
    checkpoint_url = conn_string or settings.LANGGRAPH_CHECKPOINT_URL
    if not checkpoint_url:
        _compiled_app = _compile_graph()
        return False

    try:
        checkpoint_url = _normalize_checkpoint_url(checkpoint_url)

        def _raise_timeout(signum, frame):
            raise TimeoutError("Timed out while connecting LangGraph Postgres checkpointer")

        previous_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, _raise_timeout)
        signal.setitimer(signal.ITIMER_REAL, 10)
        try:
            context = PostgresSaver.from_conn_string(checkpoint_url)
            saver = context.__enter__()
            saver.setup()
            _checkpointer_context = context
            _compiled_app = _compile_graph(checkpointer=saver)
            logger.info("Configured LangGraph Postgres checkpointer")
            return True
        finally:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, previous_handler)
    except Exception as exc:
        logger.warning("LangGraph Postgres checkpointer unavailable: %s", exc)

    try:
        saver = SupabaseWorkspaceCheckpointer()
        _checkpointer_context = saver
        _compiled_app = _compile_graph(checkpointer=saver)
        logger.info("Configured LangGraph Supabase REST checkpointer")
        return True
    except Exception as exc:
        logger.warning("LangGraph durable checkpointer unavailable, falling back to stateless graph: %s", exc)
        close_graph_checkpointer()
        _compiled_app = _compile_graph()
        return False


def close_graph_checkpointer() -> None:
    global _checkpointer_context
    if _checkpointer_context is None:
        return
    try:
        _checkpointer_context.__exit__(None, None, None)
    finally:
        _checkpointer_context = None


class GraphAppProxy:
    async def ainvoke(self, *args, **kwargs):
        return await get_graph_app().ainvoke(*args, **kwargs)

    def invoke(self, *args, **kwargs):
        return get_graph_app().invoke(*args, **kwargs)

    def __getattr__(self, item):
        return getattr(get_graph_app(), item)


app = GraphAppProxy()
