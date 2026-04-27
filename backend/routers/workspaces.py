"""Workspace-scoped API endpoints for VacayClaw runtime."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
import logging
import re
import uuid

from fastapi import APIRouter, HTTPException, Query, WebSocket, WebSocketDisconnect
from langchain_core.messages import AIMessage, HumanMessage

from backend.agent.graph import app
from backend.agent.nodes.travel_tool_executor import (
    _execute_replan_day,
    _search_places_nearby_sync,
    _select_meal_anchor,
)
from backend.config import settings
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
from backend.services.telegram_bot import telegram_bot
from backend.services.video_downloader import video_downloader
from backend.services.workspace_runtime import workspace_runtime
from backend.storage.supabase_storage import supabase_storage as storage

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/workspaces", tags=["workspaces"])
TELEGRAM_MESSAGE_LIMIT = 4096
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
WORKSPACE_RESET_RE = re.compile(
    r"\b(reset|start over|new trip|restart trip|fresh trip|clear trip)\b",
    re.IGNORECASE,
)
MEAL_REQUEST_RE = re.compile(
    r"\b(breakfast|brunch|lunch|dinner|restaurant|restaurants|food|meal|meals)\b",
    re.IGNORECASE,
)
MEAL_OPTIONS_ACTION_RE = re.compile(
    r"\b(find|show|suggest|recommend|options?|places?|locations?|restaurants?)\b",
    re.IGNORECASE,
)


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


def _new_graph_thread_id(workspace_id: str) -> str:
    return f"{workspace_id}:turn_{uuid.uuid4().hex[:12]}"


def _requests_workspace_restart(message: str) -> bool:
    return bool(WORKSPACE_RESET_RE.search(message or ""))


def _workspace_share_url(workspace_id: str) -> str:
    token = workspace_runtime.make_share_token(workspace_id)
    base = settings.PUBLIC_WEB_BASE_URL.rstrip("/")
    return f"{base}/?workspace={workspace_id}&token={token}"


def _workspace_telegram_target(workspace_id: str) -> tuple[int, int | None] | None:
    if not workspace_id.startswith("telegram:"):
        return None
    parts = workspace_id.split(":", 2)
    if len(parts) != 3:
        return None
    try:
        chat_id = int(parts[1])
    except ValueError:
        return None
    thread_part = parts[2]
    if thread_part == "main":
        return chat_id, None
    try:
        return chat_id, int(thread_part)
    except ValueError:
        return chat_id, None


def _parse_slot_start_minutes(slot: str | None) -> int | None:
    if not slot or "-" not in slot:
        return None
    start_raw = slot.split("-", maxsplit=1)[0].strip()
    try:
        hour_raw, minute_raw = start_raw.split(":", maxsplit=1)
        return (int(hour_raw) * 60) + int(minute_raw)
    except ValueError:
        return None


def _classify_meal_from_slot(slot: str | None) -> str | None:
    start_minutes = _parse_slot_start_minutes(slot)
    if start_minutes is None:
        return None
    if start_minutes < 11 * 60:
        return "breakfast"
    if start_minutes < 15 * 60:
        return "lunch"
    if start_minutes < 18 * 60:
        return "afternoon meal"
    return "dinner"


def _summarize_multi_meal_additions(message: str, previous_trip: Trip, updated_trip: Trip, fallback: str) -> str:
    if not MEAL_REQUEST_RE.search(message or ""):
        return fallback

    previous_food_ids = {
        poi.id
        for day in previous_trip.days
        for poi in day.pois
        if poi.category == "Food"
    }
    added_foods_by_day: dict[int, list[POI]] = defaultdict(list)
    for day in updated_trip.days:
        for poi in day.pois:
            if poi.category != "Food" or poi.id in previous_food_ids:
                continue
            added_foods_by_day[day.day_number].append(poi)

    added_food_count = sum(len(pois) for pois in added_foods_by_day.values())
    if added_food_count <= 1:
        return fallback

    summary_lines = ["Added meal stops for your trip:"]
    for day_number in sorted(added_foods_by_day):
        pois = sorted(
            added_foods_by_day[day_number],
            key=lambda poi: (
                _parse_slot_start_minutes(poi.time_slot) if _parse_slot_start_minutes(poi.time_slot) is not None else 99 * 60,
                poi.name.lower(),
            ),
        )
        formatted_entries = []
        for poi in pois:
            meal_label = _classify_meal_from_slot(poi.time_slot)
            if meal_label:
                formatted_entries.append(f"{meal_label} at {poi.name}")
            else:
                formatted_entries.append(poi.name)
        summary_lines.append(f"Day {day_number}: {', '.join(formatted_entries)}.")

    return "\n".join(summary_lines)


def _requested_meal_types(message: str) -> list[str]:
    lowered = (message or "").lower()
    meal_types = [meal for meal in ("breakfast", "brunch", "lunch", "dinner") if meal in lowered]
    if not meal_types and MEAL_REQUEST_RE.search(message or ""):
        meal_types = ["lunch"]
    return meal_types


def _requested_meal_days(message: str, trip: Trip) -> list[Day]:
    lowered = (message or "").lower()
    if not trip.days:
        return []
    if re.search(r"\b(both|all|each|every)\s+days?\b", lowered):
        return list(trip.days)
    day_match = re.search(r"\bday\s*(\d+)\b", lowered)
    if day_match:
        day_number = int(day_match.group(1))
        return [day for day in trip.days if day.day_number == day_number]
    return list(trip.days)


def _requests_meal_options(message: str, trip: Trip) -> bool:
    return bool(
        trip.days
        and MEAL_REQUEST_RE.search(message or "")
        and MEAL_OPTIONS_ACTION_RE.search(message or "")
        and _requested_meal_types(message)
    )


def _normalize_meal_candidate(candidate: dict, meal_type: str, anchor_name: str) -> dict:
    coords = list(candidate.get("coords") or [0.0, 0.0])
    if len(coords) != 2:
        coords = [0.0, 0.0]
    return {
        "name": str(candidate.get("name") or f"{meal_type.title()} stop near {anchor_name}"),
        "coords": [float(coords[0]), float(coords[1])],
        "description": str(candidate.get("description") or f"{meal_type.title()} near {anchor_name}"),
        "image": str(candidate.get("image") or candidate.get("img") or "https://placehold.co/600x400/f5ede8/372f2f?text=Meal"),
        "source_url": str(candidate.get("source_url") or candidate.get("url") or ""),
    }


def _build_pending_meal_options(trip: Trip, message: str) -> dict:
    meal_types = _requested_meal_types(message)
    days = _requested_meal_days(message, trip)
    recommended_items: list[dict] = []
    single_items: list[dict] = []

    for day in days:
        for meal_type in meal_types:
            anchor = _select_meal_anchor(day, meal_type)
            anchor_coords = anchor.coords if anchor else trip.accommodation.coords
            anchor_name = anchor.name if anchor else trip.title
            results = _search_places_nearby_sync(anchor_coords, meal_type, cuisine_hint="")[:3]
            normalized_results = [
                {
                    "day_number": day.day_number,
                    "meal_type": meal_type,
                    "anchor_name": anchor_name,
                    "candidate": _normalize_meal_candidate(result, meal_type, anchor_name),
                }
                for result in results
                if str(result.get("name") or "").strip()
            ]
            if not normalized_results:
                continue
            recommended_items.append(normalized_results[0])
            single_items.extend(normalized_results)

    choices: list[dict] = []
    if recommended_items:
        choices.append(
            {
                "number": 1,
                "kind": "recommended_set",
                "label": "Recommended set",
                "items": recommended_items,
            }
        )
    for item in single_items:
        choices.append(
            {
                "number": len(choices) + 1,
                "kind": "single",
                "label": (
                    f"Day {item['day_number']} {item['meal_type']}: "
                    f"{item['candidate']['name']}"
                ),
                "items": [item],
            }
        )
    return {"kind": "meal_options", "choices": choices}


def _format_meal_options(pending_meal_options: dict) -> str:
    choices = list(pending_meal_options.get("choices") or [])
    if not choices:
        return "I could not find meal options near the current route."

    lines = ["Meal options. Reply with a number to add one.", ""]
    for choice in choices:
        if choice.get("kind") == "recommended_set":
            items = [
                (
                    f"Day {item['day_number']} {item['meal_type']} - "
                    f"{item['candidate']['name']}"
                )
                for item in choice.get("items") or []
            ]
            lines.append(f"{choice['number']}. Recommended set: {'; '.join(items)}")
            continue

        item = (choice.get("items") or [{}])[0]
        candidate = item.get("candidate") or {}
        description = str(candidate.get("description") or "").strip()
        suffix = f" — {description}" if description else ""
        lines.append(
            f"{choice['number']}. Day {item.get('day_number')} "
            f"{item.get('meal_type')}: {candidate.get('name')}{suffix}"
        )
    return "\n".join(lines)


def _select_pending_meal_choice(message: str, pending_meal_options: dict | None) -> dict | None:
    choices = list((pending_meal_options or {}).get("choices") or [])
    if not choices:
        return None

    lowered = (message or "").strip().lower()
    number_match = re.search(
        r"(?:^|\b)(?:option|choice|number|no\.?|#)?\s*(\d+)\b",
        lowered,
    )
    if number_match:
        number = int(number_match.group(1))
        for choice in choices:
            if int(choice.get("number") or 0) == number:
                return choice

    for choice in choices:
        for item in choice.get("items") or []:
            candidate_name = str((item.get("candidate") or {}).get("name") or "").strip().lower()
            if candidate_name and candidate_name in lowered:
                return choice
    return None


def _meal_time_slot(meal_type: str) -> str:
    return {
        "breakfast": "09:00 - 10:00",
        "brunch": "11:00 - 12:15",
        "lunch": "12:30 - 13:45",
        "dinner": "19:00 - 20:30",
    }.get(meal_type.lower(), "12:30 - 13:45")


def _apply_pending_meal_choice(trip: Trip, choice: dict) -> tuple[Trip, str]:
    updated_trip = trip.model_copy(deep=True)
    added: list[tuple[int, str, str]] = []
    changed_days: set[int] = set()

    for item in choice.get("items") or []:
        day_number = int(item.get("day_number") or 0)
        meal_type = str(item.get("meal_type") or "lunch")
        candidate = dict(item.get("candidate") or {})
        target_day = next((day for day in updated_trip.days if day.day_number == day_number), None)
        if target_day is None:
            continue

        candidate_name = str(candidate.get("name") or "").strip()
        if not candidate_name:
            continue
        existing_names = {poi.name.strip().lower() for poi in target_day.pois if poi.category == "Food"}
        if candidate_name.lower() in existing_names:
            continue

        coords = list(candidate.get("coords") or [0.0, 0.0])
        target_day.pois.append(
            POI(
                id=f"poi_{uuid.uuid4().hex[:8]}",
                name=candidate_name,
                category="Food",
                coords=(float(coords[0]), float(coords[1])),
                img=str(candidate.get("image") or "https://placehold.co/600x400/f5ede8/372f2f?text=Meal"),
                time_slot=_meal_time_slot(meal_type),
                vibe=str(candidate.get("description") or f"{meal_type.title()} stop"),
                priority="normal",
                intensity="low",
                visit_duration=75 if meal_type in {"brunch", "lunch", "dinner"} else 60,
            )
        )
        added.append((day_number, meal_type, candidate_name))
        changed_days.add(day_number)

    for day_number in sorted(changed_days):
        updated_trip, _ = _execute_replan_day(updated_trip, day_number)

    if not added:
        return updated_trip, "Those meal stops are already in the trip."

    lines = ["Added meal stops:"]
    for day_number, meal_type, candidate_name in added:
        lines.append(f"Day {day_number} {meal_type}: {candidate_name}.")
    return updated_trip, "\n".join(lines)


def _format_interrupt_options(response: ChatResponse) -> str:
    lines: list[str] = []
    for msg in response.messages:
        if msg.type != "interrupt" or not msg.options:
            continue
        lines.append("")
        lines.append("Options:")
        for idx, opt in enumerate(msg.options, start=1):
            lines.append(f"{idx}. {opt.name} — ${opt.price:.2f}")
    return "\n".join(lines)


def _split_long_telegram_section(section: str, limit: int = TELEGRAM_MESSAGE_LIMIT) -> list[str]:
    normalized = section.strip()
    if not normalized:
        return []
    if len(normalized) <= limit:
        return [normalized]

    chunks: list[str] = []
    remaining = normalized
    while len(remaining) > limit:
        split_at = remaining.rfind("\n\n", 0, limit + 1)
        if split_at == -1:
            split_at = remaining.rfind("\n", 0, limit + 1)
        if split_at == -1:
            split_at = remaining.rfind(" ", 0, limit + 1)
        if split_at == -1 or split_at < max(limit // 2, 1):
            split_at = limit

        chunk = remaining[:split_at].rstrip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].lstrip()

    if remaining:
        chunks.append(remaining)
    return chunks


def _pack_telegram_sections(
    sections: list[str],
    *,
    limit: int = TELEGRAM_MESSAGE_LIMIT,
) -> list[str]:
    chunks: list[str] = []
    current = ""

    for section in sections:
        normalized = section.strip()
        if not normalized:
            continue

        if len(normalized) <= limit:
            candidate = f"{current}\n\n{normalized}" if current else normalized
            if len(candidate) <= limit:
                current = candidate
                continue
            if current:
                chunks.append(current)
            current = normalized
            continue

        if current:
            chunks.append(current)
            current = ""

        split_chunks = _split_long_telegram_section(normalized, limit=limit)
        if not split_chunks:
            continue
        chunks.extend(split_chunks[:-1])
        current = split_chunks[-1]

    if current:
        chunks.append(current)

    return chunks


def _build_workspace_reply_sections(
    workspace_id: str,
    response: ChatResponse,
    *,
    default_text: str | None = "Done.",
) -> list[str]:
    agent_text = next((msg.content for msg in reversed(response.messages) if msg.type == "agent" and msg.content), "")
    sections: list[str] = []
    if agent_text:
        sections.append(agent_text)
    elif default_text:
        sections.append(default_text)

    options_text = _format_interrupt_options(response)
    if options_text:
        sections.append(options_text)
    open_url = next(
        (
            msg.content
            for msg in response.messages
            if msg.type == "interrupt" and msg.interrupt_type == "open_url" and msg.content
        ),
        "",
    )
    if open_url:
        sections.append(f"Link: {open_url}")
    sections.append(f"Workspace: {_workspace_share_url(workspace_id)}")
    return sections


def _build_workspace_reply_for_telegram_chunks(workspace_id: str, response: ChatResponse) -> list[str]:
    return _pack_telegram_sections(_build_workspace_reply_sections(workspace_id, response))


async def _send_telegram_chunks(
    *,
    chat_id: int | str,
    message_thread_id: int | None,
    chunks: list[str],
) -> None:
    for chunk in chunks:
        await telegram_bot.send_message(
            chat_id=chat_id,
            text=chunk,
            message_thread_id=message_thread_id,
        )


async def _mirror_web_turn_to_telegram(workspace_id: str, message: str, response: ChatResponse) -> None:
    if not telegram_bot.enabled:
        return
    target = _workspace_telegram_target(workspace_id)
    if target is None:
        return
    chat_id, message_thread_id = target
    try:
        await _send_telegram_chunks(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            chunks=[f"Web user: {message}"],
        )
        await _send_telegram_chunks(
            chat_id=chat_id,
            message_thread_id=message_thread_id,
            chunks=_build_workspace_reply_for_telegram_chunks(workspace_id, response),
        )
    except Exception as exc:
        logger.error("Telegram web mirror send failed for %s: %s", workspace_id, exc)


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


def _has_committed_itinerary(trip: Trip | None) -> bool:
    return bool(trip and any(day.pois for day in trip.days))


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

    if existing_trip and not _has_committed_itinerary(existing_trip):
        _merge_source_videos(new_trip, existing_trip)
        new_trip.trip_id = existing_trip.trip_id
        merged_trip = new_trip
        pending_candidates = _filter_existing_trip_candidates(
            merged_trip,
            _build_pending_import_candidates(video_metadata, analysis_results, merged_trip),
        )
        runtime_state = {
            **runtime_state,
            "pending_import_candidates": pending_candidates,
        }
    elif existing_trip:
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
    if _requests_workspace_restart(message):
        trip = _build_empty_workspace_trip(workspace_id)
        await storage.save_trip(trip)
        await workspace_runtime.restart_workspace(workspace_id, title=trip.title)
        await workspace_runtime.bind_workspace_to_trip(workspace_id, trip.trip_id, title=trip.title)
        await workspace_runtime.append_event(
            workspace_id,
            "agent",
            "Started a fresh trip workspace. Send new travel links or ask for flights to continue.",
            {"source": source, "reset": True},
        )
        await workspace_runtime.build_workspace_snapshot(workspace_id, trip)
        return ChatResponse(
            messages=[
                ChatMessage(
                    id=f"msg_{uuid.uuid4().hex[:8]}",
                    type="agent",
                    content="Started a fresh trip workspace. Send new travel links or ask for flights to continue.",
                    timestamp=datetime.now(),
                )
            ],
            updated_trip=trip,
        )

    trip_id = await workspace_runtime.get_workspace_trip_id(workspace_id)
    trip = await storage.load_trip(trip_id)

    if not trip:
        trip = _build_empty_workspace_trip(workspace_id)
        await storage.save_trip(trip)
        await workspace_runtime.bind_workspace_to_trip(workspace_id, trip.trip_id, title=trip.title)
    previous_trip = trip.model_copy(deep=True)

    runtime_state = await workspace_runtime.load_runtime_state(workspace_id)
    pending_meal_choice = _select_pending_meal_choice(
        message,
        runtime_state.get("pending_meal_options"),
    )
    if pending_meal_choice:
        updated_trip, summary = _apply_pending_meal_choice(trip, pending_meal_choice)
        runtime_state = {**runtime_state, "pending_meal_options": None}
        await storage.save_trip(updated_trip)
        await workspace_runtime.bind_workspace_to_trip(workspace_id, updated_trip.trip_id, title=updated_trip.title)
        await workspace_runtime.save_runtime_state(workspace_id, runtime_state)
        await workspace_runtime.append_event(workspace_id, "user", message, {"user_id": user_id, "source": source})
        await workspace_runtime.append_event(workspace_id, "agent", summary, {"source": source})
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

    if _requests_meal_options(message, trip):
        pending_meal_options = _build_pending_meal_options(trip, message)
        summary = _format_meal_options(pending_meal_options)
        if pending_meal_options.get("choices"):
            runtime_state = {**runtime_state, "pending_meal_options": pending_meal_options}
            await workspace_runtime.save_runtime_state(workspace_id, runtime_state)
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
        metadata = ev.get("metadata") or {}
        if not content:
            continue
        if metadata.get("hidden_from_agent_history"):
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
        config={"recursion_limit": 50, "configurable": {"thread_id": _new_graph_thread_id(workspace_id)}},
    )
    final_content = "I'm not sure how to help with that."
    for msg in reversed(result.get("messages", [])):
        if isinstance(msg, AIMessage) and msg.content:
            final_content = msg.content
            break

    updated_trip = result.get("trip") or trip
    if isinstance(updated_trip, dict):
        updated_trip = Trip(**updated_trip)
    final_content = _summarize_multi_meal_additions(message, previous_trip, updated_trip, final_content)

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

    chat_interrupt = result.get("chat_interrupt")
    if isinstance(chat_interrupt, dict) and chat_interrupt.get("interrupt_type") == "open_url" and chat_interrupt.get("content"):
        await workspace_runtime.append_event(
            workspace_id,
            "agent",
            str(chat_interrupt.get("content")),
            {
                "source": source,
                "interrupt_type": "open_url",
                "hidden_from_agent_history": True,
            },
        )

    if "budget" in message.lower():
        await workspace_runtime.upsert_memory(workspace_id, user_id, "budget_preference", message)
    if "flight" in message.lower() or "airline" in message.lower():
        await workspace_runtime.upsert_memory(workspace_id, None, "last_flight_intent", message)

    await workspace_runtime.build_workspace_snapshot(workspace_id, updated_trip)
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


@router.post("/{workspace_id}/restart")
async def restart_workspace_trip(workspace_id: str):
    trip = _build_empty_workspace_trip(workspace_id)
    await storage.save_trip(trip)
    await workspace_runtime.restart_workspace(workspace_id, title=trip.title)
    await workspace_runtime.bind_workspace_to_trip(workspace_id, trip.trip_id, title=trip.title)
    await workspace_runtime.append_event(
        workspace_id,
        "agent",
        "Started a fresh trip workspace. Send new travel links or ask for flights to continue.",
        {"source": "api", "reset": True},
    )
    snapshot = await workspace_runtime.build_workspace_snapshot(workspace_id, trip)
    return {
        "workspace_id": workspace_id,
        "trip_id": trip.trip_id,
        "snapshot": snapshot,
    }


@router.post("/{workspace_id}/chat", response_model=ChatResponse)
async def send_workspace_message(workspace_id: str, request: WorkspaceChatRequest):
    await workspace_runtime.ensure_workspace(workspace_id)
    response = await _invoke_workspace_agent(
        workspace_id=workspace_id,
        message=request.message,
        user_id=request.user_id,
        source=request.source,
    )
    if request.source == "web":
        await _mirror_web_turn_to_telegram(workspace_id, request.message, response)
    return response


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
