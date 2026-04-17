"""
Tavily Location Service for geocoding and place enrichment.
Uses Tavily API to get coordinates and details for locations.
"""
import asyncio
import httpx
import logging
import re
from typing import Optional
from urllib.parse import quote

from backend.config import settings

logger = logging.getLogger(__name__)


class TavilyLocationService:
    """Service for geocoding and enriching location data using Tavily."""

    _COUNTRY_HINTS = {
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
        "new zealand": "nz", "queenstown": "nz", "auckland": "nz", "wanaka": "nz",
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
    _STREET_TERMS = (
        "road", "rd", "street", "st", "avenue", "ave", "boulevard", "blvd",
        "lane", "ln", "drive", "dr", "way", "place", "pl", "terrace", "ter",
        "track", "loop", "highway", "hwy",
    )
    
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

            # Strategy 4: use Tavily search to discover a concrete address,
            # then geocode that address with Mapbox and Nominatim.
            address_candidates = await self._discover_location_candidates_with_tavily(place_name, city)
            for candidate in address_candidates:
                result = await self._geocode_with_mapbox(candidate, city)
                if result:
                    return result

                result = await self._geocode_with_nominatim(candidate, None)
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
                country_code = self._country_code_from_hint(city)
                if country_code:
                    params["countrycodes"] = country_code

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

    def _country_code_from_hint(self, city: Optional[str]) -> Optional[str]:
        """Infer a country code from a city or region hint."""
        if not city:
            return None

        city_lower = city.lower()
        for hint, code in self._COUNTRY_HINTS.items():
            if hint in city_lower:
                return code
        return None

    def _looks_like_address(self, candidate: str) -> bool:
        """Rough filter to avoid geocoding arbitrary prose as an address."""
        lowered = candidate.lower()
        has_number = bool(re.search(r"\d", candidate))
        has_street_term = any(term in lowered for term in self._STREET_TERMS)
        has_postcode = bool(re.search(r"\b\d{4,6}\b", candidate))
        return has_number and (has_street_term or has_postcode)

    def _normalize_address_candidate(self, candidate: str, city: Optional[str]) -> str:
        """Clean and complete an address candidate before geocoding."""
        cleaned = re.sub(r"\s+", " ", candidate).strip(" ,;:-")
        if city and city.lower() not in cleaned.lower():
            cleaned = f"{cleaned}, {city}"
        return cleaned

    def _extract_address_candidates(self, text: str, city: Optional[str]) -> list[str]:
        """Extract likely address strings from Tavily answer/result text."""
        if not text:
            return []

        cleaned = re.sub(r"\s+", " ", text)
        candidates: list[str] = []

        explicit_patterns = [
            re.compile(r"(?:located at|address(?: is|:)?|find us at)\s+([^.;]+)", re.IGNORECASE),
            re.compile(r"\b(\d{1,5}[A-Za-z]?\s+[^.;]+?)\b(?=(?:\.\s|$))"),
        ]

        for pattern in explicit_patterns:
            for match in pattern.finditer(cleaned):
                candidate = self._normalize_address_candidate(match.group(1), city)
                if self._looks_like_address(candidate):
                    candidates.append(candidate)

        for segment in re.split(r"[.\n]", cleaned):
            candidate = self._normalize_address_candidate(segment, city)
            if self._looks_like_address(candidate):
                candidates.append(candidate)

        # Preserve order, remove duplicates.
        return list(dict.fromkeys(candidates))

    async def _discover_location_candidates_with_tavily(
        self,
        place_name: str,
        city: Optional[str] = None,
    ) -> list[str]:
        """Use Tavily search to recover concrete address candidates for a venue."""
        if not self.api_key:
            return []

        query = f"\"{place_name}\""
        if city:
            query += f" {city}"
        query += " address"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.post(
                    f"{self.base_url}/search",
                    json={
                        "api_key": self.api_key,
                        "query": query,
                        "search_depth": "advanced",
                        "include_answer": True,
                        "include_raw_content": False,
                        "max_results": 5,
                    },
                )

            if response.status_code != 200:
                logger.warning(f"Tavily address search failed for {place_name}: {response.status_code}")
                return []

            data = response.json()
            candidates: list[str] = []

            answer = data.get("answer")
            candidates.extend(self._extract_address_candidates(answer or "", city))

            for result in data.get("results", []):
                candidates.extend(self._extract_address_candidates(result.get("title", ""), city))
                candidates.extend(self._extract_address_candidates(result.get("content", ""), city))

            unique_candidates = list(dict.fromkeys(candidates))
            if unique_candidates:
                logger.info("Recovered %s Tavily address candidate(s) for %s", len(unique_candidates), place_name)
            return unique_candidates

        except Exception as e:
            logger.warning(f"Tavily address discovery failed for {place_name}: {e}")
            return []

    async def _geocode_with_mapbox(
        self,
        query: str,
        city: Optional[str] = None,
    ) -> Optional[dict]:
        """Geocode a concrete address or venue query with Mapbox."""
        access_token = settings.MAPBOX_PUBLIC or settings.MAPBOX_SECRET
        if not access_token:
            return None

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                params: dict[str, str | int] = {
                    "access_token": access_token,
                    "limit": 1,
                    "autocomplete": "false",
                }
                country_code = self._country_code_from_hint(city)
                if country_code:
                    params["country"] = country_code

                response = await client.get(
                    f"https://api.mapbox.com/geocoding/v5/mapbox.places/{quote(query, safe='')}.json",
                    params=params,
                )

            if response.status_code != 200:
                logger.warning(f"Mapbox geocoding error for '{query}': {response.status_code}")
                return None

            features = response.json().get("features", [])
            if not features:
                return None

            result = features[0]
            place_types = set(result.get("place_type", []))

            # Reject broad place-level matches when we asked for a street address.
            if self._looks_like_address(query) and "address" not in place_types and "poi" not in place_types:
                logger.info("Mapbox returned a low-specificity match for '%s': %s", query, result.get("place_name"))
                return None

            coords = result.get("center")
            if not coords or len(coords) != 2:
                return None

            return {
                "coords": [float(coords[0]), float(coords[1])],
                "full_name": result.get("place_name", query),
                "address": result.get("place_name", query),
                "img": "",
            }

        except Exception as e:
            logger.warning(f"Mapbox geocoding failed for '{query}': {e}")
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
