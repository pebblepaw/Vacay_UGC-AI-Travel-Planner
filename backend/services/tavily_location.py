"""
Tavily Location Service for geocoding and place enrichment.
Uses Tavily API to get coordinates and details for locations.
"""
import asyncio
import httpx
import logging
from typing import Optional

from backend.config import settings

logger = logging.getLogger(__name__)


class TavilyLocationService:
    """Service for geocoding and enriching location data using Tavily."""
    
    def __init__(self):
        self.api_key = settings.TAVLY_API
        self.base_url = "https://api.tavily.com"
        
        # Fallback to Nominatim (OpenStreetMap) if Tavily fails
        self.nominatim_url = "https://nominatim.openstreetmap.org/search"
    
    async def geocode_location(
        self,
        place_name: str,
        city: Optional[str] = None
    ) -> Optional[dict]:
        """
        Get coordinates and details for a place.
        
        Args:
            place_name: Name of the place (e.g. "TeamLab Borderless")
            city: Optional city context (e.g. "Tokyo")
            
        Returns:
            dict with:
                - coords: [longitude, latitude]
                - full_name: Full name of place
                - address: Full address
                - img: Image URL (if available)
            or None if not found
        """
        try:
            # Nominatim is the most reliable geocoder for place names.
            # We try multiple query strategies in order of specificity.

            # Strategy 1: structured query with country-code hint (most precise)
            if city:
                result = await self._geocode_with_nominatim_structured(place_name, city)
                if result:
                    return result

            # Strategy 2: free-form "place_name, city"
            result = await self._geocode_with_nominatim(place_name, city)
            if result:
                return result

            # Strategy 3: place_name only (drops overly broad city like "South of France")
            if city:
                logger.info(f"Nominatim retry without city for: {place_name}")
                result = await self._geocode_with_nominatim(place_name, None)
                if result:
                    return result

            logger.warning(f"All geocoding strategies failed for: {place_name}")
            return None
            
        except Exception as e:
            logger.error(f"Error geocoding {place_name}: {e}")
            return None
    
    async def _geocode_with_nominatim(
        self,
        place_name: str,
        city: Optional[str] = None
    ) -> Optional[dict]:
        """Geocode using OpenStreetMap Nominatim (free fallback)."""
        try:
            # Nominatim requires max 1 req/sec
            await asyncio.sleep(1.1)
            async with httpx.AsyncClient() as client:
                query = f"{place_name}"
                if city:
                    query += f", {city}"
                
                response = await client.get(
                    self.nominatim_url,
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 1,
                        "addressdetails": 1,
                    },
                    headers={
                        "User-Agent": "VACAY-Travel-Planner/1.0"
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Nominatim API error: {response.status_code}")
                    return None
                
                data = response.json()
                if not data:
                    return None
                
                result = data[0]
                
                return {
                    "coords": [float(result["lon"]), float(result["lat"])],
                    "full_name": result.get("display_name", place_name),
                    "address": result.get("display_name", ""),
                    "img": ""  # Nominatim doesn't provide images
                }
                
        except Exception as e:
            logger.error(f"Nominatim geocoding error: {e}")
            return None
    
    async def _geocode_with_nominatim_structured(
        self,
        place_name: str,
        city: Optional[str] = None
    ) -> Optional[dict]:
        """
        Geocode using Nominatim structured query.
        Useful when free-form query fails for specific POIs.
        Tries to extract a country from the city hint and searches the POI within it.
        """
        try:
            await asyncio.sleep(1.1)
            async with httpx.AsyncClient() as client:
                # Build structured params – put the place_name in 'q'
                # and any city/region/country hint in 'countrycodes' or 'viewbox'
                params: dict = {
                    "q": place_name,
                    "format": "json",
                    "limit": 3,
                    "addressdetails": 1,
                }

                # Try to detect a country code from the city hint
                country_hints = {
                    # France
                    "france": "fr", "french": "fr", "paris": "fr", "nice": "fr",
                    "provence": "fr", "riviera": "fr", "côte": "fr", "cote": "fr",
                    "marseille": "fr", "lyon": "fr", "bordeaux": "fr", "cannes": "fr",
                    "south of france": "fr", "côte d'azur": "fr",
                    # Japan
                    "japan": "jp", "tokyo": "jp", "osaka": "jp", "kyoto": "jp",
                    "hokkaido": "jp", "okinawa": "jp",
                    # Italy
                    "italy": "it", "rome": "it", "milan": "it", "florence": "it",
                    "venice": "it", "naples": "it", "amalfi": "it", "sicily": "it",
                    "tuscany": "it",
                    # Spain
                    "spain": "es", "barcelona": "es", "madrid": "es", "seville": "es",
                    "ibiza": "es", "mallorca": "es",
                    # UK
                    "uk": "gb", "london": "gb", "england": "gb", "scotland": "gb",
                    "edinburgh": "gb",
                    # Germany
                    "germany": "de", "berlin": "de", "munich": "de",
                    # Asia
                    "thailand": "th", "bangkok": "th", "phuket": "th", "chiang mai": "th",
                    "indonesia": "id", "bali": "id", "jakarta": "id",
                    "vietnam": "vn", "hanoi": "vn", "ho chi minh": "vn",
                    "singapore": "sg",
                    "malaysia": "my", "kuala lumpur": "my",
                    # Mediterranean / Islands
                    "greece": "gr", "athens": "gr", "santorini": "gr", "mykonos": "gr",
                    "croatia": "hr", "dubrovnik": "hr",
                    "turkey": "tr", "istanbul": "tr", "cappadocia": "tr",
                    "portugal": "pt", "lisbon": "pt", "porto": "pt",
                    # Americas
                    "mexico": "mx", "cancun": "mx", "tulum": "mx",
                    "colombia": "co", "brazil": "br",
                    "peru": "pe", "argentina": "ar",
                    "costa rica": "cr",
                    # Oceania
                    "australia": "au", "sydney": "au", "melbourne": "au",
                    "new zealand": "nz",
                    # Others
                    "korea": "kr", "seoul": "kr",
                    "morocco": "ma", "marrakech": "ma",
                    "egypt": "eg", "cairo": "eg",
                    "dubai": "ae", "abu dhabi": "ae",
                    "iceland": "is",
                    "norway": "no", "sweden": "se", "denmark": "dk",
                    "netherlands": "nl", "amsterdam": "nl",
                    "switzerland": "ch", "zurich": "ch",
                    "austria": "at", "vienna": "at",
                    "czech": "cz", "prague": "cz",
                    "hungary": "hu", "budapest": "hu",
                    "philippines": "ph", "manila": "ph",
                    "india": "in", "sri lanka": "lk",
                    "hawaii": "us", "new york": "us", "california": "us",
                }
                if city:
                    city_lower = city.lower()
                    for hint, code in country_hints.items():
                        if hint in city_lower:
                            params["countrycodes"] = code
                            break

                response = await client.get(
                    self.nominatim_url,
                    params=params,
                    headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                    timeout=10.0,
                )

                if response.status_code != 200:
                    return None

                data = response.json()
                if not data:
                    return None

                result = data[0]
                return {
                    "coords": [float(result["lon"]), float(result["lat"])],
                    "full_name": result.get("display_name", place_name),
                    "address": result.get("display_name", ""),
                    "img": "",
                }

        except Exception as e:
            logger.error(f"Nominatim structured geocoding error: {e}")
            return None
    
    async def get_place_image(self, place_name: str, city: Optional[str] = None) -> Optional[str]:
        """
        Get an image URL for a place.  Tries multiple sources in order:
        1. Tavily search (include_images) — uses existing API key
        2. Wikipedia / Wikimedia Commons API — free, stable URLs
        3. Deterministic placeholder
        """

        # ── 1. Tavily image search ──────────────────────────────────
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                query = f"{place_name} travel photo"
                if city:
                    query += f" {city}"

                resp = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "include_images": True,
                        "max_results": 1,
                    },
                )
                if resp.status_code == 200:
                    data = resp.json()
                    images = data.get("images", [])
                    if images:
                        url = images[0] if isinstance(images[0], str) else images[0].get("url", "")
                        if url:
                            logger.info(f"Tavily image for {place_name}: {url}")
                            return url
        except Exception as e:
            logger.warning(f"Tavily image search failed for {place_name}: {e}")

        # ── 2. Wikipedia / Wikimedia Commons ────────────────────────
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                # Search Wikipedia for the place and grab the page thumbnail
                query = f"{place_name}"
                if city:
                    query += f" {city}"

                resp = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "query",
                        "titles": place_name,
                        "prop": "pageimages",
                        "format": "json",
                        "pithumbsize": 800,
                        "redirects": 1,
                    },
                    headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                )
                if resp.status_code == 200:
                    pages = resp.json().get("query", {}).get("pages", {})
                    for page in pages.values():
                        thumb = page.get("thumbnail", {}).get("source")
                        if thumb:
                            logger.info(f"Wikipedia image for {place_name}: {thumb}")
                            return thumb

                # Try opensearch → then fetch thumbnail for best match
                resp2 = await client.get(
                    "https://en.wikipedia.org/w/api.php",
                    params={
                        "action": "opensearch",
                        "search": query,
                        "limit": 1,
                        "format": "json",
                    },
                    headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                )
                if resp2.status_code == 200:
                    os_data = resp2.json()
                    if len(os_data) >= 2 and os_data[1]:
                        title = os_data[1][0]
                        resp3 = await client.get(
                            "https://en.wikipedia.org/w/api.php",
                            params={
                                "action": "query",
                                "titles": title,
                                "prop": "pageimages",
                                "format": "json",
                                "pithumbsize": 800,
                                "redirects": 1,
                            },
                            headers={"User-Agent": "VACAY-Travel-Planner/1.0"},
                        )
                        if resp3.status_code == 200:
                            pages = resp3.json().get("query", {}).get("pages", {})
                            for page in pages.values():
                                thumb = page.get("thumbnail", {}).get("source")
                                if thumb:
                                    logger.info(f"Wikipedia opensearch image for {place_name}: {thumb}")
                                    return thumb

        except Exception as e:
            logger.warning(f"Wikipedia image search failed for {place_name}: {e}")

        # ── 3. Stable placeholder ───────────────────────────────────
        logger.info(f"No image found for {place_name}, using placeholder")
        encoded = place_name.replace(" ", "+")[:40]
        return f"https://placehold.co/800x600/1a1a2e/eaeaea?text={encoded}"


# Singleton instance
tavily_location = TavilyLocationService()
