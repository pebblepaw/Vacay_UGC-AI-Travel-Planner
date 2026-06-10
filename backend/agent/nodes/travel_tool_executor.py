'''

Standard LangGraph ToolNode executes tool functions in isolation, meaning they
can't access the graph's state (like a Trip object). 

Our tool-editing tools need to read and modify trip. 

This custom node: 
1. Reads tool_calls from last message
2. Pulls trip from state
3. Executes operation
4. Writes updated Trip back to state
5. Returns ToolMessages so agent sees the result

Necessary whenever TOols need share mutable state. 

'''

import uuid
import logging
import httpx
import asyncio
import textwrap
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt
# from backend.agent.tools.trip_tools import haversine_km
from langchain_core.messages import ToolMessage
from backend.models.schemas import Trip, POI, Day
from backend.agent.state import AgentState
from duckduckgo_search import DDGS
from backend.config import settings

logger = logging.getLogger(__name__)


# **Ideally we change this so it can be updated by the user. 
# For now, it's a hardcoded heuristic to give the agent some guidance on how to schedule POIs.

# Which time block each category "prefers" to be scheduled in.
CATEGORY_TIME_PREFERENCE = {
    "Nature": 0,      # Morning (9:00-12:00)  — gardens/parks are lovely in AM
    "Culture": 0,     # Morning              — temples, museums before crowds
    "Food": 1,        # Midday (12:00-14:00) — lunch is default; dinner handled separately
    "Art": 2,         # Afternoon (14:00-17:00) — galleries, museums
    "Shopping": 2,    # Afternoon            — shops are open, post-lunch energy
    "Nightlife": 3,   # Evening (17:00+)     — obvious
}

# Time blocks with start times (used to assign time_slots)
TIME_BLOCKS = [
    ("09:00", "Morning"),
    ("12:00", "Midday"),
    ("14:00", "Afternoon"),
    ("17:00", "Evening"),
]

# Intensity ordering for balancing (lower = place earlier after high-intensity)
INTENSITY_SCORE = {"high": 3, "normal": 2, "low": 1}
DAY_START_MINUTES = 9 * 60
DAY_END_MINUTES = (23 * 60) + 59
LUNCH_WINDOW = (11 * 60 + 30, 14 * 60 + 30)
DINNER_WINDOW = (18 * 60, 22 * 60)
MAX_CLUSTER_POIS_PER_DAY = 4
MAX_CLUSTER_MOVE_KM = 25.0
OVERPASS_INTERPRETER_URL = "https://overpass.kumi.systems/api/interpreter"
GENERIC_PLACE_RESULT_TOKENS = (
    "best ",
    "top ",
    "restaurants near",
    "lunch restaurants",
    "dinner restaurants",
    "tripadvisor",
    "opentable",
    "updated ",
    "guide",
    "spots for",
    "search restaurants",
    "restaurants &",
    "foodies",
    "yelp",
)

def _fetch_image(place_name: str) -> str:
    """Fetch a real image for a place using DuckDuckGo image search.
    Falls back to loremflickr placeholder if search fails."""
    try:
        query = f"{place_name} travel landmark"
        with DDGS() as ddgs:
            results = list(ddgs.images(
                keywords=query, max_results=1,
                safesearch="on", size="Medium", type_image="photo",
            ))
            if results:
                img_url = results[0].get("image")
                if img_url:
                    return img_url
    except Exception as e:
        logger.warning(f"Image search failed for '{place_name}': {e}")
    # Fallback
    query = place_name.replace(" ", ",").replace("'", "").lower()[:50]
    return f"https://loremflickr.com/800/600/{query},travel"


def _auto_geocode(place_name: str, city_hint: str) -> tuple[float, float] | None:
    """Synchronously geocode a place name using Nominatim. Returns (lon, lat) or None."""
    import time
    try:
        time.sleep(1.1)  # Nominatim rate limit
        with httpx.Client() as client:
            query = f"{place_name}, {city_hint}" if city_hint else place_name
            response = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                timeout=10.0,
            )
            if response.status_code == 200:
                data = response.json()
                if data:
                    return (float(data[0]["lon"]), float(data[0]["lat"]))
    except Exception as e:
        logger.warning(f"Auto-geocode failed for '{place_name}': {e}")
    return None


def _parse_time_slot(value: str) -> tuple[int, int] | None:
    try:
        start_raw, end_raw = [part.strip() for part in value.split("-", maxsplit=1)]
        start_h, start_m = [int(part) for part in start_raw.split(":")]
        end_h, end_m = [int(part) for part in end_raw.split(":")]
        return start_h * 60 + start_m, end_h * 60 + end_m
    except Exception:
        return None


def _format_minutes(total_minutes: int) -> str:
    hours, minutes = divmod(total_minutes, 60)
    return f"{hours:02d}:{minutes:02d}"


def _meal_anchor_window(poi: POI) -> tuple[int, int] | None:
    if poi.category != "Food":
        return None
    parsed = _parse_time_slot(poi.time_slot or "")
    if not parsed:
        return None
    start, end = parsed
    if LUNCH_WINDOW[0] <= start <= LUNCH_WINDOW[1]:
        return LUNCH_WINDOW
    if DINNER_WINDOW[0] <= start <= DINNER_WINDOW[1]:
        return DINNER_WINDOW
    return None


def _meal_anchor_priority(poi: POI) -> int:
    meal_window = _meal_anchor_window(poi)
    if meal_window == LUNCH_WINDOW:
        return 0
    if meal_window == DINNER_WINDOW:
        return 1
    return 2


def _sort_pois_by_start_time(pois: list[POI]) -> list[POI]:
    return sorted(
        pois,
        key=lambda poi: (
            (_parse_time_slot(poi.time_slot or "") or (99 * 60, 99 * 60))[0],
            poi.name.lower(),
        ),
    )


def _time_preference_for_poi(poi: POI) -> int:
    meal_window = _meal_anchor_window(poi)
    if meal_window == LUNCH_WINDOW:
        return 1
    if meal_window == DINNER_WINDOW:
        return 3

    parsed = _parse_time_slot(poi.time_slot or "")
    if parsed:
        start, _end = parsed
        if start < 11 * 60:
            return 0
        if start < 14 * 60:
            return 1
        if start < 17 * 60:
            return 2
        return 3

    time_pref = CATEGORY_TIME_PREFERENCE.get(poi.category, 2)
    if poi.category == "Food" and any(
        kw in poi.vibe.lower()
        for kw in ["night", "dinner", "bar", "late"]
    ):
        time_pref = 3
    return time_pref


def _estimate_transit_minutes(current: POI, next_poi: POI) -> tuple[str, int]:
    if (current.coords[0] == 0 and current.coords[1] == 0) or \
       (next_poi.coords[0] == 0 and next_poi.coords[1] == 0):
        return "🚶 10 min walk", 15
    dist_km = haversine_km(current.coords, next_poi.coords)
    if dist_km < 1.5:
        minutes = max(10, int(dist_km * 15))
        return f"🚶 {max(5, int(dist_km * 15))} min walk", minutes
    if dist_km < 10:
        minutes = max(15, int(dist_km * 3))
        return f"🚃 {max(10, int(dist_km * 3))} min train", minutes
    if dist_km < 50:
        minutes = max(20, int(dist_km * 1.5))
        return f"🚗 {max(15, int(dist_km * 1.5))} min drive", minutes
    minutes = min(180, int(dist_km * 1.5))
    return f"🚗 ~{int(dist_km / 60 * 60)} hr drive", minutes


def travel_tool_executor(state: AgentState) -> dict: 
    '''
    In Graph: 
        travel_editor agent -> (has tool_calls?) -> travel_tool_executor -> back to travel_editor
    
    Returns: 
        dict with 'messages' (ToolMessages) and 'trip' (Updated Trip)
    '''

    logger.info(f">>> TRAVEL_TOOL_EXECUTOR entered")
    last_message = state["messages"][-1]
    trip = state["trip"]

    if not trip: 
        return {
            "messages": [
                ToolMessage(
                    content="Error: No trip loaded. Cannot edit trip.",
                    tool_call_id=tc["id"]
                )
                for tc in last_message.tool_calls
            ]
        }

    # mutable copy
    trip_dict = trip.model_dump()
    updated_trip = Trip(**trip_dict)
    tool_messages = []

    for tc in last_message.tool_calls: 
        name = tc['name']
        args = tc['args']
        call_id = tc['id']

        try: 
            if name == "delete_poi":
                     updated_trip, msg = _execute_delete(updated_trip, args["poi_id"])

            elif name == "add_poi":
                updated_trip, msg = _execute_add(updated_trip, args)

            elif name == "swap_poi":
                updated_trip, msg = _execute_swap(updated_trip, args)

            elif name == "move_poi":
                updated_trip, msg = _execute_move(
                    updated_trip, args["poi_id"], args["target_day"]
                )

            elif name == "replan_day":
                updated_trip, msg = _execute_replan_day(
                    updated_trip, args["day_number"]
                )

            elif name == "optimize_trip":
                updated_trip, msg = _execute_optimize_trip(updated_trip)

            elif name == "resize_trip":
                updated_trip, msg = _execute_resize_trip(updated_trip, args["target_days"])

            elif name == "add_meal_stop":
                updated_trip, msg = _execute_add_meal_stop(
                    updated_trip,
                    args["day_number"],
                    args["meal_type"],
                    args.get("cuisine_hint", ""),
                )

            else:
                msg = f"Unknown tool: {name}"

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            msg = f"Error executing tool {name}: {str(e)}"
        
        tool_messages.append(ToolMessage(content=msg, tool_call_id=call_id))

    # ── Cleanup: remove empty days and renumber ──
    non_empty_days = [d for d in updated_trip.days if d.pois]
    if len(non_empty_days) < len(updated_trip.days):
        removed_count = len(updated_trip.days) - len(non_empty_days)
        updated_trip.days = non_empty_days
        for i, day in enumerate(updated_trip.days):
            day.day_number = i + 1
        tool_messages.append(
            ToolMessage(
                content=f"Cleaned up {removed_count} empty day(s). Trip now has {len(updated_trip.days)} days.",
                tool_call_id=call_id,  # Attach to last tool call
            )
        )

    return {'messages':tool_messages, 'trip':updated_trip}


def _execute_delete(trip: Trip, poi_id: str) -> tuple[Trip, str]:

    for day in trip.days: 
        for poi in day.pois: 
            if poi.id == poi_id: 
                day.pois.remove(poi)
                return trip, f"Deleted POI '{poi.name}' (ID: {poi.id}) from Day {day.day_number}"

    return trip, f"POI with ID {poi_id} not found. No deletion performed."

def _execute_add(trip: Trip, args: dict) -> tuple[Trip, str]:

    """Add a new POI to a specific day."""

    day_number = args["day_number"]

    # Find the target day
    target_day = None
    for day in trip.days:
        if day.day_number == day_number:
            target_day = day
            break

    if not target_day:
        return trip, f"Day {day_number} does not exist. Trip has {len(trip.days)} days."

    # Generate a unique POI ID
    all_ids = {poi.id for day in trip.days for poi in day.pois}
    new_id = f"poi_{uuid.uuid4().hex[:6]}"
    while new_id in all_ids:
        new_id = f"poi_{uuid.uuid4().hex[:6]}"

    # Auto-geocode if coords are missing or (0,0)
    lon = args.get("longitude", 0.0)
    lat = args.get("latitude", 0.0)
    if abs(lon) < 0.01 and abs(lat) < 0.01:
        # Try to geocode from place name + trip city
        city_hint = trip.title if trip.title else ""
        geocoded = _auto_geocode(args["name"], city_hint)
        if geocoded:
            lon, lat = geocoded
            logger.info(f"Auto-geocoded '{args['name']}' → ({lon}, {lat})")
        else:
            # Fallback: use average coords of existing POIs
            all_coords = [(p.coords[0], p.coords[1]) for d in trip.days for p in d.pois if p.coords and abs(p.coords[0]) > 0.01]
            if all_coords:
                lon = sum(c[0] for c in all_coords) / len(all_coords)
                lat = sum(c[1] for c in all_coords) / len(all_coords)
                logger.info(f"Using average coords for '{args['name']}' → ({lon}, {lat})")

    # Create the POI
    img_url = _fetch_image(args["name"])
    new_poi = POI(
        id=new_id,
        name=args["name"],
        category=args["category"],
        coords=(lon, lat),
        img=args.get("img", img_url),
        time_slot=args["time_slot"],
        vibe=args["vibe"],
        priority=args.get("priority", "normal"),
        intensity=args.get("intensity", "normal"),
        visit_duration=args.get("visit_duration", 60),
    )

    target_day.pois.append(new_poi)
    return trip, f"✅ Added '{new_poi.name}' (ID: {new_id}) to Day {day_number}."



def _execute_swap(trip: Trip, args: dict) -> tuple[Trip, str]:
    """Replace an existing POI with a new one at the same position."""

    old_id = args["old_poi_id"]

    for day in trip.days:
        for i, poi in enumerate(day.pois):
            if poi.id == old_id:
                # Generate new ID
                new_id = f"poi_{uuid.uuid4().hex[:6]}"

                new_poi = POI(
                    id=new_id,
                    name=args["new_name"],
                    category=args["new_category"],
                    coords=(args["new_longitude"], args["new_latitude"]),
                    img=args.get("new_img", _fetch_image(args["new_name"])),
                    time_slot=args.get("new_time_slot", poi.time_slot),
                    vibe=args["new_vibe"],
                    priority=args.get("new_priority", "normal"),
                    intensity=args.get("new_intensity", "normal"),
                    visit_duration=args.get("new_visit_duration", poi.visit_duration),
                )

                old_name = poi.name
                day.pois[i] = new_poi  # Replace in-place
                return trip, f"Swapped '{old_name}' → '{new_poi.name}' (new ID: {new_id}) on Day {day.day_number}."

    return trip, f"POI '{old_id}' not found in any day."


def _execute_move(trip: Trip, poi_id: str, target_day: int) -> tuple[Trip, str]:
    """Move a POI from its current day to a different day."""
    # Find and remove from source day
    moved_poi = None
    source_day = None

    for day in trip.days:
        for poi in day.pois:
            if poi.id == poi_id:
                moved_poi = poi
                source_day = day.day_number
                day.pois.remove(poi)
                break
        if moved_poi:
            break

    if not moved_poi:
        return trip, f"POI '{poi_id}' not found in any day."

    if source_day == target_day:
        # Put it back — it's already on the target day
        for day in trip.days:
            if day.day_number == source_day:
                day.pois.append(moved_poi)
        return trip, f"'{moved_poi.name}' is already on Day {target_day}."

    # Add to target day
    for day in trip.days:
        if day.day_number == target_day:
            day.pois.append(moved_poi)
            return trip, f"Moved '{moved_poi.name}' from Day {source_day} → Day {target_day}."

    return trip, f"Target Day {target_day} does not exist."

def _execute_replan_day(trip: Trip, day_number: int) -> tuple[Trip, str]:

    '''
    Algorithm: 
    1. Assign each POI a preferred time block based on cateogry 
    2. Sort POIs into time blocks
    3. Within each block, sort by geographic proximity
    4. Intensity balancing: If too consecutive high-intensoity POIs exist, 
    swap it with an adjacent low-intensity POI
    5. Assign new time_slots based on visit_duration
    '''

    target_day = None
    for day in trip.days:
        if day.day_number == day_number:
            target_day = day
            break

    if not target_day:
        return trip, f"Day {day_number} does not exist."

    if len(target_day.pois) <= 1:
        return trip, f"Day {day_number} has {len(target_day.pois)} POI(s) — nothing to reorder."

    pois = target_day.pois

    # ── Step 1: Bucket POIs by time preference ──
    buckets: dict[int, list[POI]] = {0: [], 1: [], 2: [], 3: []}
    for poi in pois:
        time_pref = _time_preference_for_poi(poi)
        buckets[time_pref].append(poi)

    # ── Step 2: Within each bucket, sort by proximity (nearest-neighbor) ──
    ordered: list[POI] = []
    for block_idx in sorted(buckets.keys()):
        block_pois = buckets[block_idx]
        if not block_pois:
            continue

        anchor_seed = min(block_pois, key=lambda poi: (_meal_anchor_priority(poi), poi.name.lower()))
        if _meal_anchor_priority(anchor_seed) < 2:
            ordered.append(anchor_seed)
            remaining = [poi for poi in block_pois if poi.id != anchor_seed.id]
        elif not ordered:
            # First block: start with the first POI (arbitrary seed)
            ordered.append(block_pois[0])
            remaining = block_pois[1:]
        else:
            remaining = block_pois[:]

        while remaining:
            last = ordered[-1]
            nearest = min(
                remaining,
                key=lambda p: haversine_km(last.coords, p.coords),
            )
            ordered.append(nearest)
            remaining.remove(nearest)

    # ── Step 3: Intensity balancing ──
    # If two consecutive high-intensity POIs, swap the second with next low/normal one
    for i in range(len(ordered) - 1):
        if (
            INTENSITY_SCORE.get(ordered[i].intensity, 2) >= 3
            and INTENSITY_SCORE.get(ordered[i + 1].intensity, 2) >= 3
        ):
            # Find next non-high-intensity POI to swap with
            for j in range(i + 2, len(ordered)):
                if INTENSITY_SCORE.get(ordered[j].intensity, 2) < 3:
                    ordered[i + 1], ordered[j] = ordered[j], ordered[i + 1]
                    break

    # ── Step 4: Assign new time_slots and travel_times ──
    scheduled_slots: list[tuple[int, int]] = []
    travel_segments: list[tuple[str, int]] = []
    current_time_minutes = DAY_START_MINUTES
    for idx, poi in enumerate(ordered):
        anchor_window = _meal_anchor_window(poi)
        if anchor_window:
            current_time_minutes = max(current_time_minutes, anchor_window[0])
            if current_time_minutes + poi.visit_duration > anchor_window[1]:
                return trip, (
                    f"Day {day_number} is too packed to keep {poi.name} in the requested meal window. "
                    "Move or remove another stop first."
                )

        end_minutes = current_time_minutes + poi.visit_duration
        if end_minutes > DAY_END_MINUTES:
            return trip, (
                f"Day {day_number} is too packed to fit all stops into real clock time. "
                "Move or remove another stop first."
            )
        scheduled_slots.append((current_time_minutes, end_minutes))

        if idx < len(ordered) - 1:
            travel_label, transit_minutes = _estimate_transit_minutes(poi, ordered[idx + 1])
            travel_segments.append((travel_label, transit_minutes))
            current_time_minutes = end_minutes + transit_minutes
        else:
            current_time_minutes = end_minutes

    for idx, poi in enumerate(ordered):
        start_minutes, end_minutes = scheduled_slots[idx]
        poi.time_slot = f"{_format_minutes(start_minutes)} - {_format_minutes(end_minutes)}"
        poi.travel_time = travel_segments[idx][0] if idx < len(travel_segments) else None

    target_day.pois = _sort_pois_by_start_time(ordered)

    names = [p.name for p in target_day.pois]
    return trip, f"Replanned Day {day_number}: {' → '.join(names)}"


def _execute_optimize_trip(trip: Trip) -> tuple[Trip, str]:
    """Cross-day optimization: reassign POIs to days by geographic clusters.

    ALGORITHM:
    1. Extract ALL POIs from all days (flatten)
    2. Separate high-priority "pinned" POIs (keep on their original day)
    3. Cluster remaining POIs geographically using simple centroid assignment
    4. Assign clusters to days
    5. Re-add pinned POIs back to their original days
    6. Replan each day
    """

    num_days = len(trip.days)
    if num_days <= 1:
        # Single day — just replan it
        return _execute_replan_day(trip, trip.days[0].day_number)

    # ── Step 1: Flatten all POIs, remember their origin ──
    all_pois: list[POI] = []
    pinned: dict[int, list[POI]] = {d.day_number: [] for d in trip.days}

    for day in trip.days:
        for poi in day.pois:
            if poi.priority == "high":
                # High priority stays on its original day
                pinned[day.day_number].append(poi)
            else:
                all_pois.append(poi)

    if not all_pois:
        # Everything is pinned — just replan each day
        for day in trip.days:
            trip, _ = _execute_replan_day(trip, day.day_number)
        return trip, "All POIs are high-priority (pinned). Replanned each day's order."

    # ── Step 2: Geographic clustering (simple k-means-ish) ──
    clusters = _geographic_cluster(all_pois, num_days)

    # ── Step 2b: Balance clusters so no day is overloaded ──
    clusters = _balance_clusters(clusters)

    # ── Step 3: Assign clusters to days ──
    for day in trip.days:
        cluster_idx = day.day_number - 1  # 0-indexed
        if cluster_idx < len(clusters):
            day.pois = pinned[day.day_number] + clusters[cluster_idx]
        else:
            day.pois = pinned[day.day_number]

    # ── Step 4: Remove empty days and renumber ──
    trip.days = [d for d in trip.days if d.pois]
    for i, day in enumerate(trip.days):
        day.day_number = i + 1

    # ── Step 5: Replan each day ──
    for day in trip.days:
        trip, _ = _execute_replan_day(trip, day.day_number)

    return trip, f"Optimized trip across {len(trip.days)} days. POIs reassigned by geography and replanned."


def _pick_drop_candidate(pois: list[POI]) -> POI | None:
    if not pois:
        return None

    priority_score = {"low": 0, "normal": 1, "high": 2}
    protected_food = {"12:00", "12:30", "19:00", "19:30"}

    return min(
        pois,
        key=lambda poi: (
            1 if poi.category == "Food" and any(token in poi.time_slot for token in protected_food) else 0,
            priority_score.get(poi.priority, 1),
            poi.visit_duration,
            poi.name.lower(),
        ),
    )


def _sync_geocode_nominatim(place_name: str, context_query: str = "") -> list[float] | None:
    query = f"{place_name}, {context_query}" if context_query else place_name
    try:
        with httpx.Client() as client:
            response = client.get(
                "https://nominatim.openstreetmap.org/search",
                params={"q": query, "format": "json", "limit": 1},
                headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                timeout=10.0,
            )
            response.raise_for_status()
            data = response.json()
    except Exception as exc:
        logger.warning("Nominatim geocode failed for %s: %s", query, exc)
        return None

    if not data:
        return None

    return [float(data[0]["lon"]), float(data[0]["lat"])]


def _looks_like_generic_place_result(name: str) -> bool:
    lowered = name.lower().strip()
    if not lowered:
        return True
    if any(token in lowered for token in GENERIC_PLACE_RESULT_TOKENS):
        return True
    return lowered.startswith(("the best ", "best ", "top ", "search ", "dining |"))


def _pick_named_place_result(results: list[dict], anchor_coords: tuple[float, float] | None) -> dict | None:
    valid_results = []
    for result in results:
        name = str(result.get("name") or "").strip()
        coords = result.get("coords")
        if not name or not coords or _looks_like_generic_place_result(name):
            continue
        valid_results.append(result)

    if not valid_results:
        return None

    return valid_results[0]


def _search_places_nearby_sync(
    anchor_coords: tuple[float, float] | None,
    meal_type: str,
    cuisine_hint: str = "",
    radius_meters: int = 1800,
) -> list[dict]:
    if not anchor_coords:
        return []

    lon, lat = anchor_coords
    amenity_pattern = {
        "lunch": "restaurant|cafe|fast_food",
        "dinner": "restaurant|pub|bar|cafe",
        "breakfast": "cafe|bakery|restaurant",
        "brunch": "cafe|restaurant|bakery",
    }.get(meal_type.lower(), "restaurant|cafe|pub|bar|fast_food")

    query = textwrap.dedent(
        f"""
        [out:json][timeout:25];
        (
          node["amenity"~"{amenity_pattern}"](around:{radius_meters},{lat},{lon});
          way["amenity"~"{amenity_pattern}"](around:{radius_meters},{lat},{lon});
          relation["amenity"~"{amenity_pattern}"](around:{radius_meters},{lat},{lon});
        );
        out center 60;
        """
    ).strip()

    amenity_rank = {
        "lunch": {"restaurant": 0, "cafe": 1, "fast_food": 2, "pub": 3, "bar": 4},
        "dinner": {"restaurant": 0, "pub": 1, "bar": 2, "cafe": 3, "fast_food": 4},
        "breakfast": {"cafe": 0, "bakery": 1, "restaurant": 2, "fast_food": 3},
        "brunch": {"cafe": 0, "restaurant": 1, "bakery": 2, "fast_food": 3},
    }.get(meal_type.lower(), {"restaurant": 0, "cafe": 1, "pub": 2, "bar": 3, "fast_food": 4})

    try:
        with httpx.Client() as client:
            response = client.get(
                OVERPASS_INTERPRETER_URL,
                params={"data": query},
                headers={"User-Agent": "VACAY-Travel-Planner/1.0", "Accept": "application/json"},
                timeout=15.0,
            )
            response.raise_for_status()
            payload = response.json()
    except Exception as exc:
        logger.warning("Nearby place lookup failed for %s around %s: %s", meal_type, anchor_coords, exc)
        return []

    results: list[dict] = []
    for item in payload.get("elements", []):
        tags = item.get("tags") or {}
        name = str(tags.get("name") or "").strip()
        if not name:
            continue

        center = item.get("center") or {}
        candidate_lon = item.get("lon", center.get("lon"))
        candidate_lat = item.get("lat", center.get("lat"))
        if candidate_lon is None or candidate_lat is None:
            continue

        cuisine = str(tags.get("cuisine") or "")
        if cuisine_hint and cuisine_hint.lower() not in cuisine.lower() and cuisine_hint.lower() not in name.lower():
            continue

        results.append(
            {
                "name": name,
                "amenity": tags.get("amenity") or "",
                "description": ", ".join(
                    part
                    for part in (
                        tags.get("amenity"),
                        tags.get("cuisine"),
                        tags.get("addr:street"),
                    )
                    if part
                )
                or f"Nearby {meal_type} stop",
                "coords": [float(candidate_lon), float(candidate_lat)],
                "url": tags.get("website") or tags.get("contact:website") or "",
                "image": "",
            }
        )

    filtered_results = [
        item
        for item in results
        if item.get("name") and not _looks_like_generic_place_result(str(item.get("name")))
    ]

    return sorted(
        filtered_results,
        key=lambda item: (
            amenity_rank.get(str(item.get("amenity") or ""), 99),
            haversine_km((item["coords"][0], item["coords"][1]), anchor_coords),
            str(item.get("name") or "").lower(),
        ),
    )


def _select_meal_anchor(day: Day, meal_type: str) -> POI | None:
    if not day.pois:
        return None

    target_minutes = {
        "breakfast": 9 * 60,
        "brunch": 11 * 60,
        "lunch": 12 * 60 + 30,
        "dinner": 19 * 60,
    }.get(meal_type.lower(), 12 * 60 + 30)

    best: tuple[int, POI] | None = None
    for poi in day.pois:
        parsed = _parse_time_slot(poi.time_slot or "")
        if parsed:
            midpoint = (parsed[0] + parsed[1]) // 2
            score = abs(midpoint - target_minutes)
        else:
            score = 9999
        if best is None or score < best[0]:
            best = (score, poi)
    return best[1] if best else day.pois[0]


def _fit_day_within_clock(trip: Trip, day_number: int) -> tuple[Trip, list[str]]:
    dropped: list[str] = []

    while True:
        trip, message = _execute_replan_day(trip, day_number)
        if "too packed" not in message.lower():
            return trip, dropped

        target_day = next((day for day in trip.days if day.day_number == day_number), None)
        if not target_day:
            return trip, dropped

        candidate = _pick_drop_candidate(target_day.pois)
        if not candidate or candidate.priority == "high":
            return trip, dropped

        target_day.pois = [poi for poi in target_day.pois if poi.id != candidate.id]
        dropped.append(candidate.name)


def _day_centroid(day: Day) -> tuple[float, float]:
    if not day.pois:
        return (0.0, 0.0)
    return (
        sum(poi.coords[0] for poi in day.pois) / len(day.pois),
        sum(poi.coords[1] for poi in day.pois) / len(day.pois),
    )


def _shrink_trip_days(trip: Trip, target_days: int) -> tuple[Trip, list[str]]:
    dropped_names: list[str] = []

    while len(trip.days) > target_days:
        centroids = {day.day_number: _day_centroid(day) for day in trip.days if day.pois}

        remote_candidates: list[tuple[float, int, int, Day]] = []
        for day in trip.days:
            if not day.pois or any(poi.priority == "high" for poi in day.pois):
                continue

            other_centroids = [
                centroids[other.day_number]
                for other in trip.days
                if other.day_number != day.day_number and other.pois
            ]
            if not other_centroids:
                continue

            nearest_distance = min(
                haversine_km(centroids[day.day_number], other_centroid)
                for other_centroid in other_centroids
            )
            remote_candidates.append((nearest_distance, len(day.pois), day.day_number, day))

        remote_day = next(
            (
                day
                for nearest_distance, day_size, _day_number, day in sorted(
                    remote_candidates,
                    key=lambda item: (-item[0], item[1], item[2]),
                )
                if nearest_distance >= MAX_CLUSTER_MOVE_KM * 2 and day_size <= 2
            ),
            None,
        )

        if remote_day is not None:
            dropped_names.extend(poi.name for poi in remote_day.pois)
            trip.days = [day for day in trip.days if day.day_number != remote_day.day_number]
            continue

        pair_distances: list[tuple[float, int, int]] = []
        for index, left_day in enumerate(trip.days):
            if not left_day.pois:
                continue
            for right_day in trip.days[index + 1 :]:
                if not right_day.pois:
                    continue
                pair_distances.append(
                    (
                        haversine_km(centroids[left_day.day_number], centroids[right_day.day_number]),
                        left_day.day_number,
                        right_day.day_number,
                    )
                )

        if not pair_distances:
            break

        _distance, left_day_number, right_day_number = min(pair_distances, key=lambda item: item[0])
        left_day = next(day for day in trip.days if day.day_number == left_day_number)
        right_day = next(day for day in trip.days if day.day_number == right_day_number)
        left_day.pois.extend(right_day.pois)
        trip.days = [day for day in trip.days if day.day_number != right_day_number]

    return trip, dropped_names


def _drop_remote_outlier_pois(pois: list[POI], target_days: int) -> tuple[list[POI], list[str]]:
    remaining = list(pois)
    dropped_names: list[str] = []

    while len(remaining) > target_days:
        probe_k = min(len(remaining), target_days + 1)
        if probe_k <= target_days:
            break

        probe_clusters = _geographic_cluster(remaining, probe_k)
        centroids = [
            (
                sum(poi.coords[0] for poi in cluster) / len(cluster),
                sum(poi.coords[1] for poi in cluster) / len(cluster),
            )
            for cluster in probe_clusters
            if cluster
        ]
        if len(centroids) <= target_days:
            break

        candidate_clusters: list[tuple[float, int, list[POI]]] = []
        for cluster in probe_clusters:
            if not cluster or len(cluster) > 2:
                continue

            cluster_centroid = (
                sum(poi.coords[0] for poi in cluster) / len(cluster),
                sum(poi.coords[1] for poi in cluster) / len(cluster),
            )
            other_centroids = [centroid for centroid in centroids if centroid != cluster_centroid]
            if not other_centroids:
                continue

            nearest_distance = min(
                haversine_km(cluster_centroid, other_centroid)
                for other_centroid in other_centroids
            )
            candidate_clusters.append((nearest_distance, len(cluster), cluster))

        if not candidate_clusters:
            break

        nearest_distance, _cluster_size, cluster = max(
            candidate_clusters,
            key=lambda item: (item[0], -item[1]),
        )
        target_clusters = _balance_clusters(_geographic_cluster(remaining, target_days))
        target_days_are_full = (
            len(remaining) >= target_days * MAX_CLUSTER_POIS_PER_DAY
            and bool(target_clusters)
            and all(cluster_items and len(cluster_items) >= MAX_CLUSTER_POIS_PER_DAY for cluster_items in target_clusters)
        )

        if nearest_distance < MAX_CLUSTER_MOVE_KM * 2:
            if not (target_days_are_full and len(cluster) == 1 and nearest_distance >= MAX_CLUSTER_MOVE_KM * 0.3):
                break

        if nearest_distance <= 0:
            break

        cluster_ids = {poi.id for poi in cluster}
        dropped_names.extend(poi.name for poi in cluster)
        remaining = [poi for poi in remaining if poi.id not in cluster_ids]

    return remaining, dropped_names


def _execute_resize_trip(trip: Trip, target_days: int) -> tuple[Trip, str]:
    if target_days < 1:
        return trip, "Trip must have at least 1 day."

    all_pois = [poi for day in trip.days for poi in day.pois]
    if not all_pois:
        return trip, "Trip has no locations to resize."

    try:
        base_date = datetime.strptime(trip.days[0].date, "%Y-%m-%d")
    except Exception:
        base_date = datetime.utcnow()

    dropped_names: list[str] = []
    if target_days < len(trip.days):
        all_pois, dropped_names = _drop_remote_outlier_pois(all_pois, target_days)

    cluster_count = min(target_days, len(all_pois))
    clusters = _balance_clusters(_geographic_cluster(all_pois, cluster_count))
    if target_days > cluster_count:
        clusters.extend([[] for _ in range(target_days - cluster_count)])

    rebuilt_days: list[Day] = []
    for index, cluster in enumerate(clusters[:target_days], start=1):
        rebuilt_days.append(
            Day(
                day_number=index,
                date=(base_date + timedelta(days=index - 1)).strftime("%Y-%m-%d"),
                pois=list(cluster),
            )
        )

    trip.days = rebuilt_days

    for day in trip.days:
        if not day.pois:
            continue
        trip, day_drops = _fit_day_within_clock(trip, day.day_number)
        dropped_names.extend(day_drops)

    non_empty_days = [day for day in trip.days if day.pois]
    if non_empty_days:
        trip.days = non_empty_days
        for index, day in enumerate(trip.days, start=1):
            day.day_number = index
            day.date = (base_date + timedelta(days=index - 1)).strftime("%Y-%m-%d")

    if dropped_names:
        return trip, f"Resized trip to {len(trip.days)} days and dropped: {', '.join(dropped_names)}."
    return trip, f"Resized trip to {len(trip.days)} days."


def _execute_add_meal_stop(
    trip: Trip,
    day_number: int,
    meal_type: str,
    cuisine_hint: str = "",
) -> tuple[Trip, str]:
    target_day = next((day for day in trip.days if day.day_number == day_number), None)
    if not target_day:
        return trip, f"Day {day_number} does not exist."

    anchor = _select_meal_anchor(target_day, meal_type)
    city_hint = trip.title or ""
    anchor_name = anchor.name if anchor else city_hint

    anchor_coords = anchor.coords if anchor else None
    results = _search_places_nearby_sync(anchor_coords, meal_type, cuisine_hint=cuisine_hint)
    existing_names = {poi.name.strip().lower() for poi in target_day.pois if poi.category == "Food"}
    unique_results = [
        result
        for result in results
        if str(result.get("name") or "").strip().lower() not in existing_names
    ]
    candidate_results = unique_results or results
    if not candidate_results:
        return trip, f"Could not find a {meal_type} place near {anchor_name}."

    ranked_results = sorted(
        candidate_results,
        key=lambda item: (
            item != _pick_named_place_result(candidate_results, anchor_coords),
            haversine_km((item.get("coords") or [0.0, 0.0])[0:2], anchor_coords) if anchor_coords and item.get("coords") else 0.0,
            str(item.get("name") or "").lower(),
        ),
    )
    meal_slots = {
        "breakfast": "09:00 - 10:00",
        "brunch": "11:00 - 12:15",
        "lunch": "12:30 - 13:45",
        "dinner": "19:00 - 20:30",
    }
    slot = meal_slots.get(meal_type.lower(), "12:30 - 13:45")
    duration = 75 if meal_type.lower() in {"lunch", "dinner", "brunch"} else 60

    for result in ranked_results:
        coords = result.get("coords") or [0.0, 0.0]
        vibe = result.get("description") or f"{meal_type.title()} stop near {anchor_name}"
        add_args = {
            "day_number": day_number,
            "name": result["name"],
            "category": "Food",
            "time_slot": slot,
            "vibe": vibe,
            "longitude": coords[0],
            "latitude": coords[1],
            "priority": "normal",
            "intensity": "low",
            "visit_duration": duration,
            "img": result.get("image") or _fetch_image(result["name"]),
        }
        trip, add_message = _execute_add(trip, add_args)
        trip, dropped_names = _fit_day_within_clock(trip, day_number)
        target_day = next((day for day in trip.days if day.day_number == day_number), None)
        if target_day and any(poi.name == result["name"] for poi in target_day.pois if poi.category == "Food"):
            return trip, add_message
        if result["name"] in dropped_names:
            logger.info("Dropped meal candidate after replanning: %s", result["name"])

    return trip, f"Could not keep a {meal_type} stop near {anchor_name} without overcrowding Day {day_number}."

def _geographic_cluster(pois: list[POI], k: int) -> list[list[POI]]:
    """Simple geographic clustering: assign POIs to k groups based on proximity.

    Uses a greedy approach:
    1. Pick k seed POIs that are furthest apart from each other
    2. Assign remaining POIs to nearest seed
    3. Result: k clusters of geographically grouped POIs

    This is simpler than full k-means but works well for city-scale travel.
    """

    if len(pois) <= k:
        # Fewer POIs than days — one per cluster
        return [[p] for p in pois] + [[] for _ in range(k - len(pois))]

    # ── Pick seeds: farthest-first traversal ──
    seeds = [pois[0]]
    remaining_for_seeds = pois[1:]

    while len(seeds) < k and remaining_for_seeds:
        # Find POI farthest from all current seeds
        farthest = max(
            remaining_for_seeds,
            key=lambda p: min(haversine_km(p.coords, s.coords) for s in seeds),
        )
        seeds.append(farthest)
        remaining_for_seeds.remove(farthest)

    # ── Assign each POI to nearest seed ──
    clusters: list[list[POI]] = [[] for _ in range(k)]

    # Seeds go into their own clusters
    for i, seed in enumerate(seeds):
        clusters[i].append(seed)

    # Assign the rest
    for poi in pois:
        if poi in seeds:
            continue
        nearest_idx = min(
            range(k),
            key=lambda i: haversine_km(poi.coords, seeds[i].coords),
        )
        clusters[nearest_idx].append(poi)

    return clusters


def _balance_clusters(clusters: list[list[POI]]) -> list[list[POI]]:
    """Rebalance clusters only when a day is overloaded.

    The old implementation forced cluster sizes toward equality, which could
    pull a city stop into a remote outlier day just to smooth the counts.
    Here we only rebalance when a day exceeds the practical per-day cap, and
    we move the best candidate to the geographically closest receiving cluster.
    """
    if not clusters or len(clusters) <= 1:
        return clusters

    def _centroid(pois: list[POI]) -> tuple[float, float]:
        if not pois:
            return (0.0, 0.0)
        avg_lon = sum(p.coords[0] for p in pois) / len(pois)
        avg_lat = sum(p.coords[1] for p in pois) / len(pois)
        return (avg_lon, avg_lat)

    max_iterations = 50  # Safety bound
    for _ in range(max_iterations):
        sizes = [len(c) for c in clusters]
        max_size = max(sizes)
        if max_size <= MAX_CLUSTER_POIS_PER_DAY:
            break

        biggest_idx = sizes.index(max_size)
        best_move: tuple[float, int, POI] | None = None
        for target_idx, target_cluster in enumerate(clusters):
            if target_idx == biggest_idx or len(target_cluster) >= MAX_CLUSTER_POIS_PER_DAY:
                continue

            target_centroid = _centroid(target_cluster)
            candidate = min(
                clusters[biggest_idx],
                key=lambda p: haversine_km(p.coords, target_centroid),
            )
            distance = haversine_km(candidate.coords, target_centroid)

            if best_move is None or distance < best_move[0]:
                best_move = (distance, target_idx, candidate)

        if best_move is None or best_move[0] > MAX_CLUSTER_MOVE_KM:
            break

        _, target_idx, best_poi = best_move
        clusters[biggest_idx].remove(best_poi)
        clusters[target_idx].append(best_poi)

    return clusters


def haversine_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Distance in km between two (longitude, latitude) points."""
    lon1, lat1 = radians(coord1[0]), radians(coord1[1])
    lon2, lat2 = radians(coord2[0]), radians(coord2[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))
