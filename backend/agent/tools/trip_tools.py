from langchain_core.tools import tool
from backend.models.schemas import Trip
from backend.services.route_optimizer import route_optimizer
from duckduckgo_search import DDGS
# from backend.services.tavily_location import tavily_location 

@tool
def optimize_route(trip_data: dict) -> dict: 
    ''' Re-orders stops in the trip to minimize travel distance. 
    Returns updated trip data. 
    '''

    # takes a dictionary and converts it to a Trip object
    trip = Trip(**trip_data)
    optimized_trip = route_optimizer.optimize_trip(trip)
    return optimized_trip.model_dump() # pydantic v2 uses this instead of dict()

# Fix: Update this to take into account timings too
@tool
def shorten_trip(trip_data: dict) -> dict:
    """Removes 'low' priority items if the day is too long (>4 items)."""
    trip = Trip(**trip_data)
    for day in trip.days:
        if len(day.pois) > 4:
            # Keep only high/normal priority
            day.pois = [p for p in day.pois if p.priority in ['high', 'normal']]
            # If still too many, keep top 4
            if len(day.pois) > 4:
                day.pois = day.pois[:4]
    return trip.model_dump()

@tool
async def search_places(query: str) -> str: 

    '''
    Search for places, restaurants, activities
    e.g. "find a western restaurant" or "find more things to do in Shanghai" 
    ''' 

    # result = await tavily_location.geocode_location(query,city)

    # if result: 
    #     return f"Found {result['full_name']} at {result['address']}"
    # return "Location not found" 

    # full_query = f"{query} in {location}"
    # location should now already be in the query prompt

    try: 
        with DDGS() as ddgs: 
            results = list(ddgs.text(query, max_results = 5))

        if not results: 
            return "No places found."
        
        formatted = "\n".join([f"- {r['title']}: {r['body']}" for r in results])
        
        return formatted 
    except Exception as e: 
        return f"Search failed: {e}"




    