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
from math import radians, cos, sin, asin, sqrt
# from backend.agent.tools.trip_tools import haversine_km
from langchain_core.messages import ToolMessage
from backend.models.schemas import Trip, POI, Day
from backend.agent.state import AgentState

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

def travel_tool_executor(state: AgentState) -> dict: 
    '''
    In Graph: 
        travel_editor agent -> (has tool_calls?) -> travel_tool_executor -> back to travel_editor
    
    Returns: 
        dict with 'messages' (ToolMessages) and 'trip' (Updated Trip)
    '''

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

            else:
                msg = f"Unknown tool: {name}"

        except Exception as e:
            logger.error(f"Error executing tool {name}: {e}")
            msg = f"Error executing tool {name}: {str(e)}"
        
        tool_messages.append(ToolMessage(content=msg, tool_call_id=call_id))

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

    # Create the POI
    new_poi = POI(
        id=new_id,
        name=args["name"],
        category=args["category"],
        coords=(args["longitude"], args["latitude"]),
        img=args.get("img", f"https://loremflickr.com/800/600/{args['name'].replace(' ', ',')},travel"),
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
                    # Free placeholder images
                    # **Link to duckduckgo search later
                    img=args.get("new_img", f"https://loremflickr.com/800/600/{args['new_name'].replace(' ', ',')},travel"),
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
        time_pref = CATEGORY_TIME_PREFERENCE.get(poi.category, 2)

        # Special case: Food POIs with evening-ish vibes → evening bucket
        if poi.category == "Food" and any(
            kw in poi.vibe.lower()
            for kw in ["night", "dinner", "bar", "late"]
        ):
            time_pref = 3

        buckets[time_pref].append(poi)

    # ── Step 2: Within each bucket, sort by proximity (nearest-neighbor) ──
    ordered: list[POI] = []
    for block_idx in sorted(buckets.keys()):
        block_pois = buckets[block_idx]
        if not block_pois:
            continue

        if not ordered:
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

    # ── Step 4: Assign new time_slots ──
    current_time_minutes = 9 * 60  # Start at 09:00
    for poi in ordered:
        start_h, start_m = divmod(current_time_minutes, 60)
        end_minutes = current_time_minutes + poi.visit_duration
        end_h, end_m = divmod(end_minutes, 60)
        poi.time_slot = f"{start_h:02d}:{start_m:02d} - {end_h:02d}:{end_m:02d}"

        # Add 30 min transit buffer between POIs
        current_time_minutes = end_minutes + 30

    target_day.pois = ordered

    names = [p.name for p in ordered]
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

    # ── Step 3: Assign clusters to days ──
    for day in trip.days:
        cluster_idx = day.day_number - 1  # 0-indexed
        if cluster_idx < len(clusters):
            day.pois = pinned[day.day_number] + clusters[cluster_idx]
        else:
            day.pois = pinned[day.day_number]

    # ── Step 4: Replan each day ──
    for day in trip.days:
        trip, _ = _execute_replan_day(trip, day.day_number)

    return trip, f"Optimized trip across {num_days} days. POIs reassigned by geography and replanned."

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

def haversine_km(coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
    """Distance in km between two (longitude, latitude) points."""
    lon1, lat1 = radians(coord1[0]), radians(coord1[1])
    lon2, lat2 = radians(coord2[0]), radians(coord2[1])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371 * asin(sqrt(a))
