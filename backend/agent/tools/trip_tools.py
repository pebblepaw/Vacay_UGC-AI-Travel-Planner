import json
import uuid
import logging
import httpx
from math import radians, cos, sin, asin, sqrt

from langchain_core.tools import tool
# from backend.models.schemas import Trip
# from backend.services.route_optimizer import route_optimizer
from duckduckgo_search import DDGS
# from backend.services.tavily_location import tavily_location 
from backend.config import settings

logger = logging.getLogger(__name__)

@tool
def delete_poi(poi_id: str) -> str: 
    # Execution handled by travel_tool_executor
    return f"delete_poi called with {poi_id}"

@tool
def add_poi(
    day_number: int,
    name: str, 
    category: str, 
    longitude: float,
    time_slot: str, 
    vibe: str,
    priority: str = "normal",
    intensity: str = "normal",
    visit_duration: int = 60, 
) -> str: 
    
    return f"add_poi called: {name} on Day {day_number}" 


@tool
def swap_poi(
    old_poi_id: str,
    new_name: str,
    new_category: str,
    new_longitude: float,
    new_latitude: float,
    new_time_slot: str,
    new_vibe: str,
    new_priority: str = "normal",
    new_intensity: str = "normal",
    new_visit_duration: int = 60,
) -> str:
    """Replace an existing POI with a new one, keeping the same position in the day.

    Args:
        old_poi_id: ID of the POI to replace (e.g. 'poi_2')
        new_name: Name of the replacement place
        new_category: One of: Food, Art, Nature, Culture, Shopping, Nightlife
        new_longitude: Longitude of the new place
        new_latitude: Latitude of the new place
        new_time_slot: Time range for the new place
        new_vibe: Description of why the new place is cool
        new_priority: 'high', 'normal', or 'low'
        new_intensity: 'high', 'normal', or 'low'
        new_visit_duration: Estimated visit time in minutes
    """
    return f"swap_poi called: replace {old_poi_id} with {new_name}"



@tool
def move_poi(poi_id: str, target_day: int) -> str:
    """Move a POI from its current day to a different day.

    The POI will be appended to the end of the target day's schedule.

    Args:
        poi_id: ID of the POI to move (e.g. 'poi_3')
        target_day: Day number to move the POI to (e.g. 2)
    """
    return f"move_poi called: {poi_id} to Day {target_day}"



@tool
def replan_day(day_number: int) -> str:
    """Re-sequence all POIs in a specific day for optimal ordering.

    Considers geography (minimize travel distance), time-of-day preferences
    (nature in morning, food at mealtimes, nightlife in evening), and
    intensity balancing (avoid consecutive high-intensity activities).

    **Call this AFTER adding, deleting, swapping, or moving POIs to clean up
    the day's schedule.

    Args:
        day_number: Which day to replan (e.g. 1)
    """
    return f"replan_day called for Day {day_number}"


@tool
def optimize_trip() -> str:
    """Optimize the entire trip across **ALL** days.

    This performs cross-day optimization:
    1. Groups POIs by geographic proximity
    2. Reassigns POIs to days based on clusters
    3. Replans each day for optimal ordering

    Call this when the user asks to "optimize my trip" or "fix the route"
    or when POIs seem assigned to the wrong days geographically.
    """
    return "optimize_trip called"

# @tool
# def optimize_route(trip_data: dict) -> dict: 
#     ''' Re-orders stops in the trip to minimize travel distance. 
#     Returns updated trip data. 
#     '''

#     # takes a dictionary and converts it to a Trip object
#     trip = Trip(**trip_data)
#     optimized_trip = route_optimizer.optimize_trip(trip)
#     return optimized_trip.model_dump() # pydantic v2 uses this instead of dict()

# @tool
# def shorten_trip(trip_data: dict) -> dict:
#     """Removes 'low' priority items if the day is too long (>4 items)."""
#     trip = Trip(**trip_data)
#     for day in trip.days:
#         if len(day.pois) > 4:
#             # Keep only high/normal priority
#             day.pois = [p for p in day.pois if p.priority in ['high', 'normal']]
#             # If still too many, keep top 4
#             if len(day.pois) > 4:
#                 day.pois = day.pois[:4]
#     return trip.model_dump()

@tool
async def search_places(query: str) -> str:

    """Search for places, restaurants, activities, or attractions.

    Returns structured results with names, descriptions, and coordinates
    that can be used with add_poi or swap_poi.

    Examples:
        - "sushi restaurants in Shinjuku Tokyo"
        - "art museums near Roppongi Tokyo"
        - "things to do in Shibuya Tokyo"

    Always include the city/area in your query for better results.

    Args:
        query: What to search for (include city/area name)
    """
     
    results = []

    # Step 1: Tavily first
    try: 
        async with httpx.AsyncClient() as client:
            response = await client.post(
                 "https://api.tavily.com/search",
                 json={
                      "api_key": settings.TAVLY_API,
                      "query": query, 
                      "search_depth": "basic",
                      "include_images": True, 
                      "max_results": 5
                 },
                 time_out = 15.0
            )

        if response.status_code == 200:
            data = response.json()
            for r in data.get("results",[]): 
                results.append(
                    {
                        "name": r.get("title",""),
                        "description": r.get("content",""),
                        "url": r.get("url",""),
                        "image": r.get("image_url","")
                    })
    except Exception as e:
        logger.error(f"Tavily search failed: {e}, falling back to DuckDuckGo")

    
    # Step 2: DuckDuckGo fallback

    if not results: 
        try: 
            with DDGS() as ddgs: 
                ddg_results = list(ddgs.text(query, max_results=5))
                for r in ddg_results: 
                    results.append(
                        {
                            "name": r.get("title",""),
                            "description": r.get("body",""),
                            "url": r.get("href",""),
                            "image": "",
                        }
                    )
        except Exception as e: 
            logger.error(f"DuckDuckGo search failed: {e}")
            return json.dumps({"error": f"All search providers failed: {e}"})
    
    if not results: 
        return json.dumps({"results": [], "message": "No results found"}))

    # Step 3: Geocode each result with Nominatim 

    geocoded_results = []

    async with httpx.AsyncClient() as client: 
        for r in results[:5]: 
            coords = await _geocode_nominatim(client,r['name'],query)
            geocoded_results.append({
                "name": r['name'],
                "description": r['description'],
                "url": r['url'],
                "image": r['image'],
                "coords": coords,
            })
    
    return json.dumps({"results": geocoded_results}, indent = 2)

async def _geocode_nominatim(
        client: httpx.AsyncClient, 
        place_name: str, 
        context_query: str) -> list[float] | None: 
    
    """
    Geocode a place name using OpenStreetMap Nominatim API (Open source)
    Returns [latitude, longitude] or None if geocoding fails.
    """
    
    try: 
        response = await client.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{place_name}, {context_query}",
                "format": "json",
                "limit": 1},
            headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
            timeout=10.0,)
        if response.status_code == 200: 
            data = response.json()
            if data: 
                return [float(data[0]['lon']), float(data[0]['lat'])]
    except Exception as e:
        logger.error(f"Nominatim geocoding failed for '{place_name}': {e}")
    return None

# Haversine distance (used by replan_day and optimize_trip logic)

def haversine_km(coord1: tuple[float,float], coord2: tuple[float,float]) -> float:
    """Calculate the great circle distance in kilometers between two points on the Earth."""
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    # convert decimal degrees to radians 
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    # haversine formula 
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    km = 6371 * c
    
    return km
        
    