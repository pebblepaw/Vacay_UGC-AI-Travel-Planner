"""
Supabase Storage Service.
Handles saving and loading trip data in Supabase Postgres.
Replaces local_storage.py (Phase 7).
"""
import logging
from typing import Optional

from supabase import create_client, Client

from backend.config import settings
from backend.models.schemas import Trip

logger = logging.getLogger(__name__)

# ── Placeholder trip shown when the DB is empty ──
PLACEHOLDER_TRIP = {
    "trip_id": "placeholder-welcome",
    "title": "Welcome to VACAY!",
    "source_videos": [
        {
            "platform": "tiktok",
            "url": "https://example.com",
            "title": "Paste a TikTok link to get started"
        }
    ],
    "days": [
        {
            "day_number": 1,
            "date": "2025-01-01",
            "pois": [
                {
                    "id": "poi_welcome_1",
                    "name": "The Eiffel Tower",
                    "category": "Culture",
                    "coords": [2.2945, 48.8584],
                    "img": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/85/Tour_Eiffel_Wikimedia_Commons_%28cropped%29.jpg/600px-Tour_Eiffel_Wikimedia_Commons_%28cropped%29.jpg",
                    "time_slot": "10:00 - 12:00",
                    "vibe": "Start your journey here! Paste a TikTok travel video to create your own itinerary.",
                    "travel_time": None,
                    "priority": "high",
                    "intensity": "normal",
                    "visit_duration": 120
                },
                {
                    "id": "poi_welcome_2",
                    "name": "Louvre Museum",
                    "category": "Art",
                    "coords": [2.3376, 48.8606],
                    "img": "https://images.unsplash.com/photo-1499856871958-5b9627545d1a?w=600&h=400&fit=crop",
                    "time_slot": "13:00 - 16:00",
                    "vibe": "Explore world-class art. This is a sample itinerary — upload your own video to replace it!",
                    "travel_time": "🚶 25 min walk",
                    "priority": "high",
                    "intensity": "normal",
                    "visit_duration": 180
                },
                {
                    "id": "poi_welcome_3",
                    "name": "Café de Flore",
                    "category": "Food",
                    "coords": [2.3325, 48.8540],
                    "img": "https://images.unsplash.com/photo-1514933651103-005eec06c04b?w=600&h=400&fit=crop",
                    "time_slot": "17:00 - 18:30",
                    "vibe": "Classic Parisian café. Grab a croissant and plan your next adventure.",
                    "travel_time": "🚶 10 min walk",
                    "priority": "normal",
                    "intensity": "low",
                    "visit_duration": 90
                }
            ]
        }
    ],
    "accommodation": {
        "name": "Sample Hotel — Upload a video to get started!",
        "price_per_night": 0.0,
        "status": "Placeholder",
        "img": "https://images.unsplash.com/photo-1551882547-ff40c63fe5fa?w=600&h=400&fit=crop",
        "coords": [2.3522, 48.8566]
    }
}


class SupabaseStorageService:
    """Service for Supabase Postgres storage of trips."""

    def __init__(self):
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Lazy-init the Supabase client."""
        if self._client is None:
            self._client = create_client(
                settings.SUPABASE_PROJECT_URL,
                self._resolve_api_key(),
            )
        return self._client

    def _resolve_api_key(self) -> str:
        return settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_SECRET_KEY

    # ── CRUD operations ──────────────────────────────────────────

    async def save_trip(self, trip: Trip) -> bool:
        """
        Upsert a trip into Supabase.
        Uses on-conflict to insert or update.
        """
        try:
            trip_dict = trip.model_dump(mode="json")
            row = {
                "id": trip.trip_id,
                "title": trip.title,
                "data": trip_dict,
            }
            self.client.table("trips").upsert(row).execute()
            logger.info(f"Saved trip {trip.trip_id} to Supabase")
            return True

        except Exception as e:
            logger.error(f"Error saving trip {trip.trip_id}: {e}")
            return False

    async def load_trip(self, trip_id: str) -> Optional[Trip]:
        """Load a trip by ID."""
        try:
            result = (
                self.client.table("trips")
                .select("data")
                .eq("id", trip_id)
                .execute()
            )
            if not result.data:
                logger.warning(f"Trip not found: {trip_id}")
                return None

            trip = Trip(**result.data[0]["data"])
            logger.info(f"Loaded trip {trip_id} from Supabase")
            return trip

        except Exception as e:
            logger.error(f"Error loading trip {trip_id}: {e}")
            return None

    async def list_all_trips(self) -> list[Trip]:
        """List all saved trips, most recent first."""
        try:
            result = (
                self.client.table("trips")
                .select("data")
                .order("updated_at", desc=True)
                .execute()
            )
            trips = []
            for row in result.data:
                try:
                    trips.append(Trip(**row["data"]))
                except Exception as e:
                    logger.error(f"Error parsing trip row: {e}")
            logger.info(f"Listed {len(trips)} trips from Supabase")
            return trips

        except Exception as e:
            logger.error(f"Error listing trips: {e}")
            return []

    async def delete_trip(self, trip_id: str) -> bool:
        """Delete a trip by ID."""
        try:
            self.client.table("trips").delete().eq("id", trip_id).execute()
            logger.info(f"Deleted trip {trip_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting trip {trip_id}: {e}")
            return False

    async def trip_exists(self, trip_id: str) -> bool:
        """Check if a trip exists."""
        try:
            result = (
                self.client.table("trips")
                .select("id")
                .eq("id", trip_id)
                .execute()
            )
            return len(result.data) > 0

        except Exception as e:
            logger.error(f"Error checking trip {trip_id}: {e}")
            return False

    # ── Placeholder seeding ──────────────────────────────────────

    async def seed_placeholder_if_empty(self) -> None:
        """
        If the trips table is empty, insert a placeholder trip
        so the app has something to display on first launch.
        Always upsert so the placeholder stays up-to-date.
        """
        try:
            result = (
                self.client.table("trips")
                .select("id")
                .limit(1)
                .execute()
            )
            placeholder = Trip(**PLACEHOLDER_TRIP)
            if not result.data:
                logger.info("No trips found — seeding placeholder trip")
                await self.save_trip(placeholder)
                logger.info("Placeholder trip seeded successfully")
            else:
                # Always upsert to keep placeholder images/data current
                await self.save_trip(placeholder)
                logger.info("Placeholder trip refreshed")

        except Exception as e:
            logger.error(f"Error seeding placeholder: {e}")


# Singleton instance
supabase_storage = SupabaseStorageService()
