"""
Itinerary Builder Service.
Takes Gemini analysis results and builds a complete Trip itinerary.
"""
import uuid
from datetime import datetime, timedelta
import logging
import re
from typing import Optional

from backend.models.schemas import (
    Trip, Day, POI, SourceVideo, Accommodation, GeminiAnalysisResult
)
from backend.services.tavily_location import tavily_location

logger = logging.getLogger(__name__)


class ItineraryBuilderService:
    """Service for building trip itineraries from analysis results."""
    
    def __init__(self):
        pass
    
    async def build_itinerary(
        self,
        video_data: list[dict],
        analysis_results: list[GeminiAnalysisResult],
        trip_title: Optional[str] = None
    ) -> Trip:
        """
        Build a complete trip itinerary from analysis results.
        
        Args:
            video_data: List of dicts with video info (url, title, platform)
            analysis_results: List of GeminiAnalysisResult from Gemini
            trip_title: Optional custom trip title
            
        Returns:
            Complete Trip object
        """
        # Generate trip ID
        trip_id = f"trip_{uuid.uuid4().hex[:12]}"
        
        # Build source videos list
        source_videos = []
        for video in video_data:
            source_videos.append(SourceVideo(
                platform=video.get('platform', 'tiktok'),
                url=video.get('url', ''),
                title=video.get('title', 'Untitled')
            ))
        
        # Extract city from analysis results
        scope = self._extract_location_scope(analysis_results)
        city = str(scope.get("scope_name") or "Unknown City")
        
        # Generate trip title if not provided
        if not trip_title:
            trip_title = f"Curated {city} Experience" if city else "My Trip"
        
        # Combine all locations from all videos
        all_locations = []
        for result in analysis_results:
            all_locations.extend(result.locations)
        
        # Remove duplicates and geocode
        unique_pois = await self._build_pois_from_locations(all_locations, city, scope)
        if not unique_pois:
            raise ValueError("No extracted locations could be resolved inside the video's location scope.")
        
        # Organize into days (simple algorithm: ~3-4 POIs per day)
        days = self._organize_into_days(unique_pois)
        
        # Create accommodation (mock for Phase 1)
        accommodation = self._create_mock_accommodation(city, len(days))
        
        # Build final trip
        trip = Trip(
            trip_id=trip_id,
            title=trip_title,
            source_videos=source_videos,
            days=days,
            accommodation=accommodation
        )
        
        return trip
    
    def _extract_city(self, analysis_results: list[GeminiAnalysisResult]) -> str:
        """Extract a user-facing scope label from analysis results."""
        return str(self._extract_location_scope(analysis_results).get("scope_name") or "Unknown City")

    def _extract_location_scope(self, analysis_results: list[GeminiAnalysisResult]) -> dict[str, str]:
        """Resolve the narrowest safe place scope for imported POIs."""
        city_counts: dict[str, int] = {}
        country_counts: dict[str, int] = {}

        for result in analysis_results:
            metadata = result.metadata or {}
            city = str(metadata.get("city") or "").strip()
            country = str(metadata.get("country") or "").strip()
            if city:
                city_counts[city] = city_counts.get(city, 0) + 1
            if country:
                country_counts[country] = country_counts.get(country, 0) + 1

        scope_name = max(city_counts, key=city_counts.get) if city_counts else ""
        country = max(country_counts, key=country_counts.get) if country_counts else ""
        country_code = tavily_location._country_code_from_hint(country or scope_name) or ""
        scope_type = "city"

        if not scope_name and country:
            scope_type = "country"
            scope_name = country
        elif self._looks_like_region(scope_name):
            scope_type = "region"
        elif country and len(city_counts) > 1:
            scope_type = "country"
            scope_name = country
        elif not country and self._looks_like_country(scope_name):
            scope_type = "country"
            country = scope_name
        elif not scope_name:
            scope_name = "Unknown City"

        query_parts = [scope_name]
        if country and country.lower() not in scope_name.lower():
            query_parts.append(country)

        return {
            "scope_name": scope_name,
            "country": country,
            "country_code": country_code,
            "scope_type": scope_type,
            "query_hint": ", ".join(part for part in query_parts if part),
        }

    def _looks_like_region(self, value: str) -> bool:
        lowered = value.lower()
        return any(
            term in lowered
            for term in (
                "lake ",
                " island",
                " islands",
                " region",
                " province",
                " coast",
                " countryside",
                "district",
                "county",
                "bay",
                "south of",
                "north of",
                "east of",
                "west of",
            )
        )

    def _looks_like_country(self, value: str) -> bool:
        lowered = value.lower()
        return bool(re.fullmatch(r"[a-z][a-z\s'.-]+", lowered)) and tavily_location._country_code_from_hint(value) is not None

    async def _build_pois_from_locations(
        self,
        locations: list[dict],
        city: str,
        scope: dict[str, str],
    ) -> list[POI]:
        """Convert location dicts to POI objects with geocoding."""
        pois = []
        seen_names = set()
        
        for loc in locations:
            name = loc.get('name', '')
            if not name or name in seen_names:
                continue
            
            seen_names.add(name)
            
            # Geocode location
            geo_data = await tavily_location.geocode_location(name, scope.get("query_hint") or city, scope=scope)
            
            if not geo_data:
                logger.warning("Dropping unresolved or out-of-scope location: %s", name)
                continue
            else:
                coords = tuple(geo_data['coords'])
                img_url = geo_data.get('img') or await tavily_location.get_place_image(name, scope.get("query_hint") or city) or ""
            
            # Create POI
            # Map any invalid categories to valid ones
            category = loc.get('type', 'Culture')
            category_map = {
                'Landmark': 'Culture',
                'Attraction': 'Culture',
                'Museum': 'Art',
                'Restaurant': 'Food',
                'Cafe': 'Food',
                'Bar': 'Nightlife',
                'Club': 'Nightlife',
                'Park': 'Nature',
                'Garden': 'Nature',
                'Market': 'Shopping',
                'Mall': 'Shopping',
                'Temple': 'Culture',
                'Shrine': 'Culture',
            }
            if category not in ['Food', 'Art', 'Nature', 'Culture', 'Shopping', 'Nightlife']:
                category = category_map.get(category, 'Culture')
            
            poi = POI(
                id=f"poi_{uuid.uuid4().hex[:8]}",
                name=name,
                category=category,
                coords=coords,
                img=img_url,
                time_slot="",  # Will be filled when organizing into days
                vibe=loc.get('description', 'A must-visit spot!'),
                travel_time=None,
                priority=loc.get('priority', 'normal'),
                intensity=loc.get('intensity', 'normal'),
                visit_duration=loc.get('visit_duration', 60)
            )
            
            pois.append(poi)
        
        return pois
    
    def _organize_into_days(self, pois: list[POI]) -> list[Day]:
        """Organize POIs into days with time slots."""
        if not pois:
            return []
        
        # Simple algorithm: 3-4 POIs per day
        pois_per_day = 4
        num_days = max(1, (len(pois) + pois_per_day - 1) // pois_per_day)
        
        days = []
        start_date = datetime.now() + timedelta(days=30)  # Trip starts in 30 days
        
        for day_num in range(num_days):
            # Get POIs for this day
            start_idx = day_num * pois_per_day
            end_idx = min(start_idx + pois_per_day, len(pois))
            day_pois = pois[start_idx:end_idx]
            
            # Assign time slots
            time_slots = [
                "09:00 - 11:00",
                "11:30 - 13:30",
                "14:00 - 16:00",
                "16:30 - 18:30",
                "19:00 - 21:00"
            ]
            
            for i, poi in enumerate(day_pois):
                if i < len(time_slots):
                    poi.time_slot = time_slots[i]
                else:
                    poi.time_slot = "Flexible"
                
                # Add travel time for non-first POIs
                if i > 0:
                    poi.travel_time = "🚶 10 min walk"  # Placeholder
            
            # Create day
            day_date = start_date + timedelta(days=day_num)
            day = Day(
                day_number=day_num + 1,
                date=day_date.strftime("%Y-%m-%d"),
                pois=day_pois
            )
            
            days.append(day)
        
        return days
    
    def _create_mock_accommodation(self, city: str, num_nights: int) -> Accommodation:
        """Create mock accommodation (Phase 1 - no real booking)."""
        return Accommodation(
            name=f"{city} Central Airbnb",
            price_per_night=120.0,
            status="Mock Data - Booking not implemented yet",
            img="https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
            coords=(0.0, 0.0)  # Placeholder
        )


# Singleton instance
itinerary_builder = ItineraryBuilderService()
