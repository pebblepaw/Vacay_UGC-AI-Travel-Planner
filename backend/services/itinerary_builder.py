"""
Itinerary Builder Service.
Takes Gemini analysis results and builds a complete Trip itinerary.
"""
import asyncio
import uuid
from datetime import datetime, timedelta
import logging
import re
from typing import Any, Optional

from backend.models.schemas import (
    Trip, Day, POI, SourceVideo, Accommodation, GeminiAnalysisResult
)
from backend.services.tavily_location import tavily_location

logger = logging.getLogger(__name__)


class ItineraryBuilderService:
    """Service for building trip itineraries from analysis results."""

    MAX_IMPORT_DAYS = 3
    MAX_POIS_PER_DAY = 4
    MAX_IMPORT_POIS = 10
    GEO_CONCURRENCY = 4
    IMPORT_GEO_TIMEOUT_SECONDS = 15.0
    MAX_REBALANCE_DISTANCE_KM = 25.0
    
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
                title=video.get('title', 'Untitled'),
                preview_url=video.get('preview_url'),
                thumbnail_url=video.get('thumbnail_url'),
            ))
        
        # Extract city from analysis results
        scope = self._extract_location_scope(analysis_results)
        city = str(scope.get("scope_name") or "Unknown City")
        
        # Generate trip title if not provided
        if not trip_title:
            trip_title = f"Curated {city} Experience" if city else "My Trip"
        
        # Combine all locations from all videos
        all_locations = []
        for index, result in enumerate(analysis_results):
            video = video_data[index] if index < len(video_data) else {}
            source_url = str(video.get("url") or "").strip()
            for location in result.locations:
                enriched_location = dict(location)
                if source_url:
                    enriched_location["media_urls"] = [source_url]
                all_locations.append(enriched_location)

        logger.info("Building itinerary from %s extracted location candidates", len(all_locations))

        # Remove duplicates and geocode
        unique_pois = await self._build_pois_from_locations(all_locations, city, scope)
        if not unique_pois:
            raise ValueError("No extracted locations could be resolved inside the video's location scope.")

        logger.info("Resolved %s unique POIs for itinerary build", len(unique_pois))

        # Organize into days with geographic clustering and an import day cap.
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
        deduped_locations: dict[str, dict[str, Any]] = {}

        for order, loc in enumerate(locations):
            name = str(loc.get("name") or "").strip()
            if not name:
                continue

            bucket = deduped_locations.setdefault(
                name,
                {
                    **loc,
                    "name": name,
                    "media_urls": [],
                    "_mention_count": 0,
                    "_order": order,
                },
            )
            bucket["_mention_count"] = int(bucket.get("_mention_count", 0)) + 1
            merged_media = list(bucket.get("media_urls") or [])
            for media_url in loc.get("media_urls", []) or []:
                if media_url and media_url not in merged_media:
                    merged_media.append(media_url)
            bucket["media_urls"] = merged_media

            existing_priority = str(bucket.get("priority") or "normal")
            new_priority = str(loc.get("priority") or "normal")
            priority_rank = {"high": 2, "normal": 1, "low": 0}
            if priority_rank.get(new_priority, 1) > priority_rank.get(existing_priority, 1):
                bucket["priority"] = new_priority
            if not bucket.get("description") and loc.get("description"):
                bucket["description"] = loc["description"]

        category_rank = {
            "Culture": 3,
            "Nature": 3,
            "Art": 2,
            "Shopping": 1,
            "Nightlife": 1,
            "Food": 1,
        }

        ranked_locations = sorted(
            deduped_locations.values(),
            key=lambda loc: (
                -int(loc.get("_mention_count", 1)),
                -{"high": 2, "normal": 1, "low": 0}.get(str(loc.get("priority") or "normal"), 1),
                -category_rank.get(str(loc.get("type") or "Culture"), 2),
                int(loc.get("_order", 0)),
            ),
        )[: self.MAX_IMPORT_POIS]

        semaphore = asyncio.Semaphore(self.GEO_CONCURRENCY)
        query_hint = scope.get("query_hint") or city
        resolved = await asyncio.gather(
            *[
                self._resolve_ranked_location(loc, query_hint, scope, semaphore)
                for loc in ranked_locations
            ]
        )

        pois.extend([poi for poi in resolved if poi is not None])
        
        return pois

    async def _resolve_ranked_location(
        self,
        loc: dict[str, Any],
        query_hint: str,
        scope: dict[str, str],
        semaphore: asyncio.Semaphore,
    ) -> Optional[POI]:
        name = str(loc.get("name") or "").strip()
        if not name:
            return None

        async with semaphore:
            geo_data = await tavily_location.geocode_location(
                name,
                query_hint,
                scope=scope,
                timeout_seconds=self.IMPORT_GEO_TIMEOUT_SECONDS,
            )

        if not geo_data:
            logger.warning("Dropping unresolved or out-of-scope location: %s", name)
            return None

        coords = tuple(geo_data["coords"])
        img_url = geo_data.get("img") or await tavily_location.get_place_image(name, query_hint) or ""

        category = loc.get("type", "Culture")
        category_map = {
            "Landmark": "Culture",
            "Attraction": "Culture",
            "Museum": "Art",
            "Restaurant": "Food",
            "Cafe": "Food",
            "Bar": "Nightlife",
            "Club": "Nightlife",
            "Park": "Nature",
            "Garden": "Nature",
            "Market": "Shopping",
            "Mall": "Shopping",
            "Temple": "Culture",
            "Shrine": "Culture",
        }
        if category not in ["Food", "Art", "Nature", "Culture", "Shopping", "Nightlife"]:
            category = category_map.get(category, "Culture")

        return POI(
            id=f"poi_{uuid.uuid4().hex[:8]}",
            name=name,
            category=category,
            coords=coords,
            img=img_url,
            time_slot="",
            vibe=loc.get("description", "A must-visit spot!"),
            travel_time=None,
            priority=loc.get("priority", "normal"),
            intensity=loc.get("intensity", "normal"),
            visit_duration=loc.get("visit_duration", 60),
            media_urls=list(loc.get("media_urls") or []),
        )
    
    def _organize_into_days(self, pois: list[POI]) -> list[Day]:
        """Organize POIs into geographically sensible day clusters."""
        if not pois:
            return []

        min_days = max(1, (len(pois) + self.MAX_POIS_PER_DAY - 1) // self.MAX_POIS_PER_DAY)
        max_days = min(self.MAX_IMPORT_DAYS, len(pois))
        num_days = min(min_days, max_days)
        clusters: list[list[POI]] = []

        while num_days <= max_days:
            candidate_clusters = self._balance_clusters(self._geographic_cluster(pois, num_days))
            clusters = candidate_clusters
            if all(len(cluster) <= self.MAX_POIS_PER_DAY for cluster in candidate_clusters):
                break
            num_days += 1

        days = []
        start_date = datetime.now() + timedelta(days=30)  # Trip starts in 30 days

        for day_num, cluster in enumerate(clusters, start=1):
            day_pois = self._order_day_cluster(cluster)[: self.MAX_POIS_PER_DAY]
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
                    poi.travel_time = self._travel_label(day_pois[i - 1], poi)
            
            # Create day
            day_date = start_date + timedelta(days=day_num - 1)
            day = Day(
                day_number=day_num,
                date=day_date.strftime("%Y-%m-%d"),
                pois=day_pois
            )
            
            days.append(day)
        
        return days

    def _geographic_cluster(self, pois: list[POI], k: int) -> list[list[POI]]:
        if len(pois) <= k:
            return [[poi] for poi in pois] + [[] for _ in range(k - len(pois))]

        seeds = [pois[0]]
        remaining = pois[1:]
        while len(seeds) < k and remaining:
            farthest = max(
                remaining,
                key=lambda poi: min(self._haversine_km(poi.coords, seed.coords) for seed in seeds),
            )
            seeds.append(farthest)
            remaining.remove(farthest)

        clusters: list[list[POI]] = [[] for _ in range(k)]
        for index, seed in enumerate(seeds):
            clusters[index].append(seed)

        for poi in pois:
            if poi in seeds:
                continue
            nearest_index = min(
                range(k),
                key=lambda idx: self._haversine_km(poi.coords, seeds[idx].coords),
            )
            clusters[nearest_index].append(poi)

        return clusters

    def _balance_clusters(self, clusters: list[list[POI]]) -> list[list[POI]]:
        if len(clusters) <= 1:
            return clusters

        def centroid(items: list[POI]) -> tuple[float, float]:
            if not items:
                return (0.0, 0.0)
            return (
                sum(poi.coords[0] for poi in items) / len(items),
                sum(poi.coords[1] for poi in items) / len(items),
            )

        for _ in range(50):
            sizes = [len(cluster) for cluster in clusters]
            if max(sizes) <= self.MAX_POIS_PER_DAY:
                break

            biggest = sizes.index(max(sizes))
            best_move: tuple[float, int, POI] | None = None

            for target_idx, target_cluster in enumerate(clusters):
                if target_idx == biggest or len(target_cluster) >= self.MAX_POIS_PER_DAY:
                    continue

                target = centroid(target_cluster)
                candidate = min(
                    clusters[biggest],
                    key=lambda poi: self._haversine_km(poi.coords, target),
                )
                distance = self._haversine_km(candidate.coords, target)

                if best_move is None or distance < best_move[0]:
                    best_move = (distance, target_idx, candidate)

            if best_move is None or best_move[0] > self.MAX_REBALANCE_DISTANCE_KM:
                break

            _, target_idx, candidate = best_move
            clusters[biggest].remove(candidate)
            clusters[target_idx].append(candidate)

        return clusters

    def _order_day_cluster(self, pois: list[POI]) -> list[POI]:
        if len(pois) <= 1:
            return list(pois)

        centroid = (
            sum(poi.coords[0] for poi in pois) / len(pois),
            sum(poi.coords[1] for poi in pois) / len(pois),
        )
        start = min(pois, key=lambda poi: self._haversine_km(poi.coords, centroid))
        ordered = [start]
        remaining = [poi for poi in pois if poi.id != start.id]

        while remaining:
            current = ordered[-1]
            next_poi = min(remaining, key=lambda poi: self._haversine_km(current.coords, poi.coords))
            ordered.append(next_poi)
            remaining.remove(next_poi)

        return ordered

    def _travel_label(self, current: POI, next_poi: POI) -> str:
        distance = self._haversine_km(current.coords, next_poi.coords)
        if distance < 1.5:
            return f"🚶 {max(5, int(distance * 15))} min walk"
        if distance < 10:
            return f"🚃 {max(10, int(distance * 3))} min train"
        return f"🚗 {max(20, int(distance * 1.5))} min drive"

    def _haversine_km(self, coord1: tuple[float, float], coord2: tuple[float, float]) -> float:
        from math import radians, cos, sin, asin, sqrt

        lon1, lat1 = radians(coord1[0]), radians(coord1[1])
        lon2, lat2 = radians(coord2[0]), radians(coord2[1])
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
        return 2 * 6371 * asin(sqrt(a))
    
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
