"""
Itinerary Builder Service.
Takes Gemini analysis results and builds a complete Trip itinerary.
"""
import uuid
from datetime import datetime, timedelta
import logging
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
        city = self._extract_city(analysis_results)
        
        # Generate trip title if not provided
        if not trip_title:
            trip_title = f"Curated {city} Experience" if city else "My Trip"
        
        # Combine all locations from all videos
        all_locations = []
        for result in analysis_results:
            all_locations.extend(result.locations)
        
        # Remove duplicates and geocode
        unique_pois = await self._build_pois_from_locations(all_locations, city)
        
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
        """Extract city name from analysis results."""
        for result in analysis_results:
            city = result.metadata.get('city')
            if city:
                return city
        return "Unknown City"
    
    async def _build_pois_from_locations(
        self,
        locations: list[dict],
        city: str
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
            geo_data = await tavily_location.geocode_location(name, city)
            
            if not geo_data:
                logger.warning(f"Could not geocode location: {name}")
                # Use default coords (city center placeholder)
                coords = (0.0, 0.0)
                img_url = await tavily_location.get_place_image(name) or ""
            else:
                coords = tuple(geo_data['coords'])
                img_url = geo_data.get('img') or await tavily_location.get_place_image(name) or ""
            
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
