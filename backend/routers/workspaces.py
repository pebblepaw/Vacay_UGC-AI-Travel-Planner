"""Workspace-scoped API endpoints for VacayClaw runtime."""
from __future__ import annotations

from datetime import datetime
import logging
import uuid

from fastapi import APIRouter, HTTPException, Query
from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.graph import app
from backend.models.schemas import (
    ChatMessage,
    ChatResponse,
    Trip,
    VideoProcessRequest,
    WorkspaceChatRequest,
    WorkspaceSnapshotResponse,
)
from backend.services.gemini_analyzer import gemini_analyzer
from backend.services.itinerary_builder import itinerary_builder
from backend.services.video_downloader import video_downloader
from backend.services.workspace_runtime import workspace_runtime
from backend.storage.supabase_storage import supabase_storage as storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])


@router.post("/{workspace_id}/videos/process")
async def process_workspace_videos(workspace_id: str, request: VideoProcessRequest):
    """Ingest multiple links and merge into the same workspace trip."""
    await workspace_runtime.ensure_workspace(workspace_id)
    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    existing_trip = await storage.load_trip(trip_id)

    download_results = await video_downloader.download_multiple(request.urls)
    successful = [r for r in download_results if r.get("success")]
    if not successful:
        raise HTTPException(status_code=400, detail="Failed to download any workspace video URLs")

    analysis_results = await gemini_analyzer.analyze_multiple_videos(
        [{"file_path": r["file_path"], "title": r.get("title", "Untitled")} for r in successful]
    )

    video_metadata = [
        {
            "url": str(r.get("url") or ""),
            "title": r.get("title", "Untitled"),
            "platform": r.get("platform", "tiktok"),
        }
        for r in successful
    ]

    new_trip = await itinerary_builder.build_itinerary(video_metadata, analysis_results, request.trip_title)

    if existing_trip:
        existing_urls = {video.url for video in existing_trip.source_videos}
        existing_trip.source_videos.extend([v for v in new_trip.source_videos if v.url not in existing_urls])
        existing_trip.days.extend(new_trip.days)
        merged_trip = existing_trip
    else:
        merged_trip = new_trip

    await storage.save_trip(merged_trip)
    await workspace_runtime.bind_workspace_to_trip(workspace_id, merged_trip.trip_id, title=merged_trip.title)
    await workspace_runtime.append_event(
        workspace_id,
        "agent",
        f"Imported {len(successful)} new media links into workspace",
        metadata={"failed": [r.get("url") for r in download_results if not r.get("success")]},
    )
    snapshot = await workspace_runtime.build_workspace_snapshot(workspace_id, merged_trip)

    return {
        "workspace_id": workspace_id,
        "trip_id": merged_trip.trip_id,
        "snapshot": snapshot,
        "imported_count": len(successful),
        "failed_count": len(download_results) - len(successful),
    }


async def _invoke_workspace_agent(workspace_id: str, message: str, user_id: str | None, source: str) -> ChatResponse:
    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    trip = await storage.load_trip(trip_id)

    if not trip:
        trips = await storage.list_all_trips()
        if not trips:
            await storage.seed_placeholder_if_empty()
            trips = await storage.list_all_trips()
        if not trips:
            raise HTTPException(status_code=500, detail="No trip found to attach workspace")

        trip = trips[0]
        await workspace_runtime.bind_workspace_to_trip(workspace_id, trip.trip_id, title=trip.title)

    events = await workspace_runtime.list_events(workspace_id, limit=16)
    history_messages = []
    for ev in events:
        role = ev.get("role")
        content = ev.get("content")
        if not content:
            continue
        if role == "user":
            history_messages.append(HumanMessage(content=content))
        elif role == "agent":
            history_messages.append(AIMessage(content=content))

    runtime_state = await workspace_runtime.load_runtime_state(workspace_id)
    initial_state = {
        "messages": history_messages[-10:] + [HumanMessage(content=message)],
        "trip": trip,
        "next_node": None,
        "plan": None,
        "current_step": 0,
        "critique": "",
        "iteration_count": 0,
        "last_agent": None,
        "pending_changes": None,
        "booking_context": runtime_state.get("booking_context"),
        "booking_offers": runtime_state.get("booking_offers"),
        "selected_offer": runtime_state.get("selected_offer"),
        "booking_result": runtime_state.get("booking_result"),
        "workspace_id": workspace_id,
        "workspace_memory": await workspace_runtime.list_memory(workspace_id),
        "user_memory": await workspace_runtime.list_memory(workspace_id, user_id=user_id),
    }

    result = await app.ainvoke(initial_state, config={"recursion_limit": 50})
    final_content = "I'm not sure how to help with that."
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            final_content = msg.content
            break

    updated_trip = result.get("trip") or trip
    if isinstance(updated_trip, dict):
        updated_trip = Trip(**updated_trip)

    await storage.save_trip(updated_trip)
    await workspace_runtime.bind_workspace_to_trip(workspace_id, updated_trip.trip_id, title=updated_trip.title)
    await workspace_runtime.save_runtime_state(
        workspace_id,
        {
            "booking_context": result.get("booking_context"),
            "booking_offers": result.get("booking_offers"),
            "selected_offer": result.get("selected_offer"),
            "booking_result": result.get("booking_result"),
        },
    )

    await workspace_runtime.append_event(workspace_id, "user", message, {"user_id": user_id, "source": source})
    await workspace_runtime.append_event(workspace_id, "agent", final_content, {"source": source})

    if "budget" in message.lower():
        await workspace_runtime.upsert_memory(workspace_id, user_id, "budget_preference", message)
    if "flight" in message.lower() or "airline" in message.lower():
        await workspace_runtime.upsert_memory(workspace_id, None, "last_flight_intent", message)

    chat_interrupt = result.get("chat_interrupt")
    response_messages = [
        ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="user",
            content=message,
            timestamp=datetime.now(),
        ),
        ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="agent",
            content=final_content,
            timestamp=datetime.now(),
        ),
    ]

    if isinstance(chat_interrupt, dict):
        response_messages.append(
            ChatMessage(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                type="interrupt",
                content=str(chat_interrupt.get("content") or ""),
                timestamp=datetime.now(),
                interrupt_type=chat_interrupt.get("interrupt_type"),
                options=chat_interrupt.get("options"),
                status=chat_interrupt.get("status"),
            )
        )

    return ChatResponse(messages=response_messages, updated_trip=updated_trip)


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def send_workspace_message(workspace_id: str, request: WorkspaceChatRequest):
    await workspace_runtime.ensure_workspace(workspace_id)
    return await _invoke_workspace_agent(
        workspace_id=workspace_id,
        message=request.message,
        user_id=request.user_id,
        source=request.source,
    )


@router.get("/{workspace_id}/snapshot", response_model=WorkspaceSnapshotResponse)
async def get_workspace_snapshot(workspace_id: str, token: str | None = Query(default=None)):
    if token:
        verified_workspace = workspace_runtime.verify_share_token(token)
        if verified_workspace != workspace_id:
            raise HTTPException(status_code=403, detail="Invalid workspace share token")

    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    trip = await storage.load_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Workspace trip not found")

    snapshot = await workspace_runtime.build_workspace_snapshot(workspace_id, trip)
    return WorkspaceSnapshotResponse(**snapshot)


@router.post("/{workspace_id}/share-link")
async def create_workspace_share_link(workspace_id: str):
    await workspace_runtime.ensure_workspace(workspace_id)
    token = workspace_runtime.make_share_token(workspace_id)
    return {
        "workspace_id": workspace_id,
        "token": token,
        "url_path": f"/?workspace={workspace_id}&token={token}",
    }
