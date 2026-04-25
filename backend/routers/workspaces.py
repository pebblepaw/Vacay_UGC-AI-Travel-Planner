"""Workspace-scoped API endpoints for VacayClaw runtime."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.graph import app
from backend.agent.nodes.travel_tool_executor import _execute_replan_day
from backend.models.schemas import (
    Accommodation,
    ChatMessage,
    ChatResponse,
    Day,
    POI,
    SourceVideo,
    Trip,
    VideoProcessRequest,
    WorkspaceChatRequest,
    WorkspaceSnapshotResponse,
)
from backend.services.gemini_analyzer import gemini_analyzer
from backend.services.itinerary_builder import itinerary_builder
from backend.services.booking_intent import normalize_booking_intent
from backend.services.tavily_location import tavily_location
from backend.services.video_downloader import video_downloader
from backend.services.workspace_runtime import workspace_runtime
from backend.storage.supabase_storage import supabase_storage as storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
DEFAULT_CATEGORY_SLOTS = {
    "Food": "12:00 - 13:30",
    "Nature": "09:00 - 11:00",
    "Culture": "10:00 - 12:00",
    "Art": "14:00 - 16:00",
    "Shopping": "15:00 - 17:00",
    "Nightlife": "19:00 - 21:00",
}
PENDING_CATEGORY_MAP = {
    "landmark": "Culture",
    "attraction": "Culture",
    "museum": "Art",
    "restaurant": "Food",
    "cafe": "Food",
    "bar": "Nightlife",
    "club": "Nightlife",
    "park": "Nature",
    "garden": "Nature",
    "market": "Shopping",
    "mall": "Shopping",
    "temple": "Culture",
    "shrine": "Culture",
}


def _build_empty_workspace_trip(workspace_id: str) -> Trip:
    return Trip(
        trip_id=f"trip_{uuid.uuid4().hex[:12]}",
        title=f"Workspace {workspace_id.split(':')[-1]} trip",
        source_videos=[],
        days=[],
        accommodation=Accommodation(
            name="Add media or ask for flights to begin",
            price_per_night=0.0,
            status="Pending",
            img="https://placehold.co/600x400/f5ede8/372f2f?text=VacayClaw",
            coords=(0.0, 0.0),
        ),
    )


def _build_media_staging_trip(workspace_id: str, video_metadata: list[dict], trip_title: str | None = None) -> Trip:
    trip = _build_empty_workspace_trip(workspace_id)
    if trip_title:
        trip.title = trip_title
    trip.source_videos = [
        SourceVideo(
            platform=str(video.get("platform") or "tiktok"),
            url=str(video.get("url") or ""),
            title=str(video.get("title") or "Untitled"),
            preview_url=video.get("preview_url"),
            thumbnail_url=video.get("thumbnail_url"),
        )
        for video in video_metadata
    ]
    return trip


def _is_placeholder_trip(trip: Trip | None) -> bool:
    return bool(trip and trip.trip_id == "placeholder-welcome")


def _merge_source_videos(existing_trip: Trip, new_trip: Trip) -> None:
    existing_videos = {video.url: video for video in existing_trip.source_videos}
    for video in new_trip.source_videos:
        existing = existing_videos.get(video.url)
        if existing is None:
            existing_trip.source_videos.append(video)
            existing_videos[video.url] = video
            continue
        if not existing.preview_url and video.preview_url:
            existing.preview_url = video.preview_url
        if not existing.thumbnail_url and video.thumbnail_url:
            existing.thumbnail_url = video.thumbnail_url


def _normalize_pending_category(raw_category: str | None) -> str:
    candidate = str(raw_category or "").strip()
    if candidate in DEFAULT_CATEGORY_SLOTS:
        return candidate
    return PENDING_CATEGORY_MAP.get(candidate.lower(), "Culture")


def _build_scope_hint(metadata: dict | None) -> dict:
    metadata = metadata or {}
    city = str(metadata.get("city") or "").strip()
    country = str(metadata.get("country") or "").strip()
    scope_type = str(metadata.get("scope_type") or "city")
    scope_name = city or country or "Unknown City"
    country_code = tavily_location._country_code_from_hint(country or city or scope_name) or ""
    query_parts = [part for part in (city, country) if part]
    query_hint = ", ".join(query_parts) or scope_name
    return {
        "scope_name": scope_name,
        "country": country,
        "country_code": country_code,
        "scope_type": scope_type,
        "query_hint": query_hint,
    }


def _build_pending_import_candidates(
    video_metadata: list[dict],
    analysis_results: list,
    imported_trip: Trip,
) -> list[dict]:
    resolved_by_name: dict[str, POI] = {}
    for day in imported_trip.days:
        for poi in day.pois:
            resolved_by_name[poi.name.strip().lower()] = poi

    pending_candidates: list[dict] = []
    seen: set[tuple[str, str]] = set()
    for index, result in enumerate(analysis_results):
        video = video_metadata[index] if index < len(video_metadata) else {}
        source_url = str(video.get("url") or "").strip()
        metadata = getattr(result, "metadata", {}) or {}
        scope_hint = _build_scope_hint(metadata)
        source_title = str(video.get("title") or metadata.get("video_title") or "").strip()
        source_caption = str(metadata.get("caption_text") or video.get("title") or "").strip()
        for location in getattr(result, "locations", []) or []:
            name = str(location.get("name") or "").strip()
            if not name:
                continue
            dedupe_key = (name.lower(), source_url)
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)

            resolved = resolved_by_name.get(name.lower())
            category = resolved.category if resolved else _normalize_pending_category(location.get("type"))
            media_urls = list(location.get("media_urls") or [])
            if source_url and source_url not in media_urls:
                media_urls.append(source_url)
            if resolved:
                for media_url in resolved.media_urls:
                    if media_url and media_url not in media_urls:
                        media_urls.append(media_url)

            pending_candidates.append(
                {
                    "name": name,
                    "category": category,
                    "coords": list(resolved.coords) if resolved else list(location.get("coords") or []),
                    "img": resolved.img if resolved else str(location.get("img") or ""),
                    "time_slot": resolved.time_slot if resolved else _default_timeslot_for_category(category),
                    "vibe": str(location.get("description") or (resolved.vibe if resolved else "Imported from recent media")),
                    "priority": str(location.get("priority") or (resolved.priority if resolved else "normal")),
                    "intensity": str(location.get("intensity") or (resolved.intensity if resolved else "normal")),
                    "visit_duration": int(location.get("visit_duration") or (resolved.visit_duration if resolved else 60)),
                    "media_urls": media_urls,
                    "query_hint": scope_hint["query_hint"],
                    "scope": scope_hint,
                    "source_title": source_title,
                    "source_caption": source_caption,
                    "raw_type": str(location.get("type") or ""),
                }
            )
    return pending_candidates


def _filter_existing_trip_candidates(trip: Trip, candidates: list[dict]) -> list[dict]:
    existing_names = {
        poi.name.strip().lower()
        for day in trip.days
        for poi in day.pois
    }
    return [
        candidate
        for candidate in candidates
        if str(candidate.get("name") or "").strip().lower() not in existing_names
    ]


def _requests_pending_candidate_add(message: str) -> bool:
    lowered = message.lower().strip()
    if not lowered:
        return False
    return any(
        phrase in lowered
        for phrase in (
            "add this",
            "include this",
            "use this",
            "add it",
            "include it",
        )
    )


def _score_candidate_match(message: str, candidate: dict) -> int:
    lowered = message.lower()
    haystacks = [
        str(candidate.get("name") or "").lower(),
        str(candidate.get("category") or "").lower(),
        str(candidate.get("vibe") or "").lower(),
        str(candidate.get("raw_type") or "").lower(),
        str(candidate.get("source_title") or "").lower(),
        str(candidate.get("source_caption") or "").lower(),
    ]
    score = 0
    for haystack in haystacks:
        if haystack and haystack in lowered:
            score += 5
    for token in re.findall(r"[a-z0-9]+", lowered):
        if len(token) < 4:
            continue
        if any(token in haystack for haystack in haystacks):
            score += 1
    return score


def _is_fresh_booking_search(message: str, trip: Trip, history_messages: list) -> bool:
    intent = normalize_booking_intent(
        message=message,
        trip=trip,
        history=history_messages,
    )
    return bool(intent.is_booking_request and intent.can_search)


def _select_pending_candidate(message: str, candidates: list[dict]) -> tuple[dict | None, list[dict]]:
    if not candidates:
        return None, []

    if len(candidates) == 1 and _requests_pending_candidate_add(message):
        return candidates[0], []

    ranked = sorted(
        ((candidate, _score_candidate_match(message, candidate)) for candidate in candidates),
        key=lambda item: item[1],
        reverse=True,
    )
    best_candidate, best_score = ranked[0]
    if best_score <= 0:
        return None, candidates

    remaining = [candidate for candidate in candidates if candidate != best_candidate]
    return best_candidate, remaining


def _choose_target_day(trip: Trip, candidate_coords: tuple[float, float]) -> int:
    if not trip.days:
        return 1

    def _centroid(day: Day) -> tuple[float, float]:
        if not day.pois:
            return candidate_coords
        return (
            sum(poi.coords[0] for poi in day.pois) / len(day.pois),
            sum(poi.coords[1] for poi in day.pois) / len(day.pois),
        )

    def _haversine_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1 = radians(coord1[0]), radians(coord1[1])
        lon2, lat2 = radians(coord2[0]), radians(coord2[1])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * 6371 * asin(sqrt(a))

    return min(
        trip.days,
        key=lambda day: (_haversine_km(_centroid(day), candidate_coords), len(day.pois), day.day_number),
    ).day_number


def _default_timeslot_for_category(category: str) -> str:
    return DEFAULT_CATEGORY_SLOTS.get(category, "15:00 - 16:30")


def _candidate_to_poi(candidate: dict) -> POI:
    coords = tuple(candidate.get("coords") or (0.0, 0.0))
    if len(coords) != 2:
        coords = (0.0, 0.0)
    return POI(
        id=f"poi_{uuid.uuid4().hex[:8]}",
        name=str(candidate.get("name") or "Imported Place"),
        category=str(candidate.get("category") or "Culture"),
        coords=(float(coords[0]), float(coords[1])),
        img=str(candidate.get("img") or "https://placehold.co/600x400/f5ede8/372f2f?text=VacayClaw"),
        time_slot=str(candidate.get("time_slot") or _default_timeslot_for_category(str(candidate.get("category") or ""))),
        vibe=str(candidate.get("vibe") or "Imported from recent media"),
        priority=str(candidate.get("priority") or "normal"),
        intensity=str(candidate.get("intensity") or "normal"),
        visit_duration=int(candidate.get("visit_duration") or 60),
        media_urls=list(candidate.get("media_urls") or []),
    )


async def _materialize_pending_candidate(candidate: dict) -> dict:
    coords = list(candidate.get("coords") or [])
    if len(coords) == 2:
        return candidate

    query_hint = str(candidate.get("query_hint") or "").strip() or None
    scope = candidate.get("scope")
    geo_data = await tavily_location.geocode_location(
        str(candidate.get("name") or ""),
        query_hint,
        scope=scope if isinstance(scope, dict) else None,
        timeout_seconds=15.0,
    )
    if not geo_data:
        raise ValueError(f"Could not resolve {candidate.get('name') or 'that place'} precisely enough to add it.")

    enriched = {**candidate, "coords": geo_data.get("coords") or coords}
    if not enriched.get("img"):
        enriched["img"] = await tavily_location.get_place_image(
            str(candidate.get("name") or ""),
            query_hint,
        )
    return enriched


async def _apply_pending_candidate_to_trip(trip: Trip, candidate: dict) -> tuple[Trip, int, str]:
    candidate_name = str(candidate.get("name") or "").strip()
    if candidate_name and any(
        poi.name.strip().lower() == candidate_name.lower()
        for day in trip.days
        for poi in day.pois
    ):
        return trip, 0, f"{candidate_name} is already in the trip."

    candidate = await _materialize_pending_candidate(candidate)
    target_day_number = _choose_target_day(trip, tuple(candidate.get("coords") or (0.0, 0.0)))
    if not trip.days:
        trip.days.append(
            Day(
                day_number=1,
                date=datetime.now().strftime("%Y-%m-%d"),
                pois=[],
            )
        )
        target_day_number = 1

    target_day = next((day for day in trip.days if day.day_number == target_day_number), None)
    if target_day is None:
        target_day = Day(day_number=target_day_number, date=datetime.now().strftime("%Y-%m-%d"), pois=[])
        trip.days.append(target_day)
        trip.days.sort(key=lambda day: day.day_number)

    target_day.pois.append(_candidate_to_poi(candidate))
    updated_trip, _ = _execute_replan_day(trip, target_day_number)
    added_name = str(candidate.get("name") or "Imported place")
    return updated_trip, target_day_number, f"Added {added_name} to Day {target_day_number}."


@router.post("/{workspace_id}/videos/process")
async def process_workspace_videos(workspace_id: str, request: VideoProcessRequest):
    """Ingest multiple links and merge into the same workspace trip."""
    await workspace_runtime.ensure_workspace(workspace_id)
    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    existing_trip = await storage.load_trip(trip_id)
    if _is_placeholder_trip(existing_trip):
        existing_trip = None

    download_results = await video_downloader.download_multiple(request.urls)
    successful = [r for r in download_results if r.get("success")]
    if not successful:
        raise HTTPException(status_code=400, detail="Failed to download any workspace video URLs")

    analysis_results = await gemini_analyzer.analyze_multiple_videos(
        [
            {
                "file_path": r["file_path"],
                "title": r.get("title", "Untitled"),
                "caption": r.get("description") or r.get("title", "Untitled"),
            }
            for r in successful
        ]
    )

    video_metadata = [
        {
            "url": str(r.get("url") or ""),
            "title": r.get("title", "Untitled"),
            "platform": r.get("platform", "tiktok"),
            "preview_url": r.get("preview_url"),
            "thumbnail_url": r.get("thumbnail"),
        }
        for r in successful
    ]

    try:
        new_trip = await itinerary_builder.build_itinerary(video_metadata, analysis_results, request.trip_title)
    except ValueError as exc:
        logger.info("Falling back to media staging trip for %s: %s", workspace_id, exc)
        new_trip = _build_media_staging_trip(workspace_id, video_metadata, request.trip_title)
    runtime_state = await workspace_runtime.load_runtime_state(workspace_id)

    if existing_trip:
        _merge_source_videos(existing_trip, new_trip)
        pending_candidates = _filter_existing_trip_candidates(
            existing_trip,
            _build_pending_import_candidates(video_metadata, analysis_results, new_trip),
        )
        runtime_state = {
            **runtime_state,
            "pending_import_candidates": pending_candidates,
        }
        merged_trip = existing_trip
    else:
        pending_candidates = _filter_existing_trip_candidates(
            new_trip,
            _build_pending_import_candidates(video_metadata, analysis_results, new_trip),
        )
        runtime_state = {
            **runtime_state,
            "pending_import_candidates": pending_candidates,
        }
        merged_trip = new_trip

    await storage.save_trip(merged_trip)
    await workspace_runtime.bind_workspace_to_trip(workspace_id, merged_trip.trip_id, title=merged_trip.title)
    await workspace_runtime.save_runtime_state(workspace_id, runtime_state)
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
        "pending_candidates_count": len(runtime_state.get("pending_import_candidates") or []),
    }


async def _invoke_workspace_agent(workspace_id: str, message: str, user_id: str | None, source: str) -> ChatResponse:
    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    trip = await storage.load_trip(trip_id)

    if not trip:
        trip = _build_empty_workspace_trip(workspace_id)
        await storage.save_trip(trip)
        await workspace_runtime.bind_workspace_to_trip(workspace_id, trip.trip_id, title=trip.title)

    runtime_state = await workspace_runtime.load_runtime_state(workspace_id)
    pending_candidate, remaining_candidates = _select_pending_candidate(
        message,
        list(runtime_state.get("pending_import_candidates") or []),
    )
    if pending_candidate and _requests_pending_candidate_add(message):
        try:
            updated_trip, target_day_number, summary = await _apply_pending_candidate_to_trip(trip, pending_candidate)
        except ValueError as exc:
            summary = str(exc)
            await workspace_runtime.append_event(workspace_id, "user", message, {"user_id": user_id, "source": source})
            await workspace_runtime.append_event(workspace_id, "agent", summary, {"source": source})
            await workspace_runtime.build_workspace_snapshot(workspace_id, trip)
            return ChatResponse(
                messages=[
                    ChatMessage(
                        id=f"msg_{uuid.uuid4().hex[:8]}",
                        type="user",
                        content=message,
                        timestamp=datetime.now(),
                    ),
                    ChatMessage(
                        id=f"msg_{uuid.uuid4().hex[:8]}",
                        type="agent",
                        content=summary,
                        timestamp=datetime.now(),
                    ),
                ],
                updated_trip=trip,
            )
        runtime_state["pending_import_candidates"] = remaining_candidates
        await storage.save_trip(updated_trip)
        await workspace_runtime.bind_workspace_to_trip(workspace_id, updated_trip.trip_id, title=updated_trip.title)
        await workspace_runtime.save_runtime_state(workspace_id, runtime_state)
        await workspace_runtime.append_event(workspace_id, "user", message, {"user_id": user_id, "source": source})
        await workspace_runtime.append_event(workspace_id, "agent", summary, {"source": source, "day_number": target_day_number})
        await workspace_runtime.build_workspace_snapshot(workspace_id, updated_trip)
        return ChatResponse(
            messages=[
                ChatMessage(
                    id=f"msg_{uuid.uuid4().hex[:8]}",
                    type="user",
                    content=message,
                    timestamp=datetime.now(),
                ),
                ChatMessage(
                    id=f"msg_{uuid.uuid4().hex[:8]}",
                    type="agent",
                    content=summary,
                    timestamp=datetime.now(),
                ),
            ],
                updated_trip=updated_trip,
            )

    await workspace_runtime.clear_langgraph_state(workspace_id)
    runtime_state = await workspace_runtime.load_runtime_state(workspace_id)

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

    if _is_fresh_booking_search(message, trip, history_messages):
        runtime_state = {
            **runtime_state,
            "booking_context": {},
            "booking_offers": [],
            "selected_offer": {},
            "booking_result": {},
        }

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

    result = await app.ainvoke(
        initial_state,
        config={"recursion_limit": 50, "configurable": {"thread_id": workspace_id}},
    )
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

    await workspace_runtime.build_workspace_snapshot(workspace_id, updated_trip)

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


@router.websocket("/{workspace_id}/events/ws")
async def workspace_events_ws(websocket: WebSocket, workspace_id: str, token: str | None = None):
    if token:
        verified_workspace = workspace_runtime.verify_share_token(token)
        if verified_workspace != workspace_id:
            await websocket.close(code=4403)
            return

    await workspace_runtime.ensure_workspace(workspace_id)
    queue = workspace_runtime.subscribe(workspace_id)
    await websocket.accept()

    try:
        snapshot = await workspace_runtime.get_workspace_snapshot(workspace_id)
        if snapshot is None:
            trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
            trip = await storage.load_trip(trip_id)
            if trip:
                snapshot = await workspace_runtime.build_workspace_snapshot(workspace_id, trip)
        if snapshot is not None:
            await websocket.send_json({"type": "snapshot", "snapshot": snapshot})

        disconnect_task = asyncio.create_task(websocket.receive_text())
        try:
            while True:
                next_update = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    {disconnect_task, next_update},
                    return_when=asyncio.FIRST_COMPLETED,
                )

                if disconnect_task in done:
                    break

                if next_update in done:
                    await websocket.send_json(next_update.result())

                for task in pending:
                    task.cancel()
        finally:
            disconnect_task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        workspace_runtime.unsubscribe(workspace_id, queue)


@router.post("/{workspace_id}/share-link")
async def create_workspace_share_link(workspace_id: str):
    await workspace_runtime.ensure_workspace(workspace_id)
    token = workspace_runtime.make_share_token(workspace_id)
    return {
        "workspace_id": workspace_id,
        "token": token,
        "url_path": f"/?workspace={workspace_id}&token={token}",
    }
