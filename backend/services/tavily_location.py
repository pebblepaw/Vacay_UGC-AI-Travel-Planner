"""
Tavily Location Service for geocoding and place enrichment.
Uses Tavily API to get coordinates and details for locations.
"""
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
            # Try Tavily first
            result = await self._geocode_with_tavily(place_name, city)
            if result:
                return result
            
            # Fallback to Nominatim
            logger.info(f"Tavily failed, trying Nominatim for: {place_name}")
            result = await self._geocode_with_nominatim(place_name, city)
            return result
            
        except Exception as e:
            logger.error(f"Error geocoding {place_name}: {e}")
            return None
    
    async def _geocode_with_tavily(
        self,
        place_name: str,
        city: Optional[str] = None
    ) -> Optional[dict]:
        """Geocode using Tavily API."""
        try:
            async with httpx.AsyncClient() as client:
                # Construct search query
                query = f"{place_name}"
                if city:
                    query += f" {city}"
                
                # Tavily search endpoint
                response = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "basic",
                        "include_images": True,
                        "max_results": 1
                    },
                    timeout=10.0
                )
                
                if response.status_code != 200:
                    logger.warning(f"Tavily API error: {response.status_code}")
                    return None
                
                data = response.json()
                
                # Extract location data from Tavily response
                results = data.get("results", [])
                if not results:
                    return None
                
                first_result = results[0]
                
                # Tavily doesn't always return coords, so we may need to parse
                # For now, we'll extract what we can and use Nominatim as fallback
                # This is a simplified implementation
                
                # Check if Tavily provides structured location data
                # (Tavily's API varies, this may need adjustment)
                coords = first_result.get("coordinates")
                if not coords:
                    # Fallback to Nominatim
                    return None
                
                return {
                    "coords": [coords["longitude"], coords["latitude"]],
                    "full_name": first_result.get("title", place_name),
                    "address": first_result.get("url", ""),
                    "img": first_result.get("image_url", "")
                }
                
        except Exception as e:
            logger.error(f"Tavily geocoding error: {e}")
            return None
    
    async def _geocode_with_nominatim(
        self,
        place_name: str,
        city: Optional[str] = None
    ) -> Optional[dict]:
        """Geocode using OpenStreetMap Nominatim (free fallback)."""
        try:
            async with httpx.AsyncClient() as client:
                query = f"{place_name}"
                if city:
                    query += f", {city}"
                
                response = await client.get(
                    self.nominatim_url,
                    params={
                        "q": query,
                        "format": "json",
                        "limit": 1
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
    
    async def get_place_image(self, place_name: str) -> Optional[str]:
        """
        Get an image URL for a place using DuckDuckGo Search.
        
        Args:
            place_name: Name of the place
            
        Returns:
            Image URL or None
        """
        try:
            # Try DuckDuckGo Image Search first (real images)
            from duckduckgo_search import DDGS
            
            # Clean query and add travel context
            query = f"{place_name} travel landmark"
            
            # Use synchronous DDGS (it's fast enough for this use case)
            with DDGS() as ddgs:
                results = list(ddgs.images(
                    keywords=query,
                    max_results=1,
                    safesearch='on',
                    size='Medium',
                    type_image='photo'
                ))
                
                if results and len(results) > 0:
                    image_url = results[0].get('image')
                    if image_url:
                        logger.info(f"Found image for {place_name}: {image_url}")
                        return image_url
            
            # Fallback to LoremFlickr if DDG fails
            logger.info(f"No image found for {place_name}, using fallback")
            query = place_name.replace(" ", ",").replace("'", "").lower()[:50]
            return f"https://loremflickr.com/800/600/{query},travel"
            
        except Exception as e:
            logger.error(f"Error getting image for {place_name}: {e}")
            # Final fallback
            query = place_name.replace(" ", ",").replace("'", "").lower()[:50]
            return f"https://loremflickr.com/800/600/{query},travel"


# Singleton instance
tavily_location = TavilyLocationService()
