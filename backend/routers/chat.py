"""Legacy trip chat router retained for backward compatibility.

All new runtime behavior is workspace-scoped. This endpoint now proxies into
workspace routing using `trip:{trip_id}` workspace ids.
"""
from fastapi import APIRouter

from backend.models.schemas import ChatRequest, ChatResponse
from backend.routers.workspaces import _invoke_workspace_agent
from backend.services.workspace_runtime import workspace_runtime

router = APIRouter(prefix="/api/trips", tags=["chat"])


@router.post("/{trip_id}/chat", response_model=ChatResponse)
async def send_chat_message(trip_id: str, request: ChatRequest):
    workspace_id = f"trip:{trip_id}"
    await workspace_runtime.ensure_workspace(workspace_id, trip_id=trip_id)
    return await _invoke_workspace_agent(
        workspace_id=workspace_id,
        message=request.message,
        user_id=None,
        source="web",
    )
