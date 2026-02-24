"""
Human Review Node — Human-in-the-Loop (HITL) for destructive changes.

When the critic detects a destructive action (too many deletions, empty days, etc.),
it routes here. This node uses LangGraph's interrupt mechanism to pause execution
and wait for user confirmation.

HOW IT WORKS:
1. Graph is compiled with `interrupt_before=["human_review"]`
2. When execution reaches this node, LangGraph PAUSES and returns to the caller
3. The caller (chat router) detects the interrupt and sends a confirmation message
4. When the user confirms, execution resumes with this node
5. This node checks the user's response and either approves or rolls back

NOTE: For Phase 5, we implement a simplified version that always proceeds
after showing a confirmation message. Full HITL with rollback is Phase 6.
"""

from langchain_core.messages import AIMessage
from backend.agent.state import AgentState


def human_review_node(state: AgentState) -> dict:
    """Human review: present changes for confirmation.

    In the current simplified implementation, this just adds a confirmation
    message. The LangGraph interrupt_before mechanism pauses BEFORE this node,
    so the caller can handle the confirmation flow.
    """
    messages = state["messages"]
    trip = state.get("trip")

    # Extract what happened from recent tool messages
    changes = []
    for msg in messages[-10:]:
        if hasattr(msg, "type") and msg.type == "tool":
            changes.append(msg.content)

    changes_summary = "\n".join(changes) if changes else "Changes were made to your trip."

    confirmation_msg = (
        f"⚠️ I've made some significant changes to your trip. "
        f"Here's what happened:\n\n{changes_summary}\n\n"
        f"The changes have been applied. Let me know if you'd like to undo anything!"
    )

    return {
        "messages": [AIMessage(content=confirmation_msg)],
        "next_node": "done",
    }