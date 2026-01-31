"""
Local Storage Service.
Handles saving and loading trip data as JSON files.
Phase 1: Uses local filesystem storage.
Phase 2: Will be replaced with Supabase database.
"""
import json
from pathlib import Path
import logging
from typing import Optional

from backend.config import settings
from backend.models.schemas import Trip

logger = logging.getLogger(__name__)


class LocalStorageService:
    """Service for local JSON file storage of trips."""
    
    def __init__(self):
        self.storage_dir = settings.TRIPS_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)
    
    def _get_trip_file_path(self, trip_id: str) -> Path:
        """Get file path for a trip."""
        return self.storage_dir / f"{trip_id}.json"
    
    async def save_trip(self, trip: Trip) -> bool:
        """
        Save a trip to local JSON file.
        
        Args:
            trip: Trip object to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_trip_file_path(trip.trip_id)
            
            # Convert Trip to dict
            trip_dict = trip.model_dump(mode='json')
            
            # Save to JSON file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(trip_dict, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved trip {trip.trip_id} to {file_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error saving trip {trip.trip_id}: {e}")
            return False
    
    async def load_trip(self, trip_id: str) -> Optional[Trip]:
        """
        Load a trip from local JSON file.
        
        Args:
            trip_id: Trip ID to load
            
        Returns:
            Trip object or None if not found
        """
        try:
            file_path = self._get_trip_file_path(trip_id)
            
            if not file_path.exists():
                logger.warning(f"Trip file not found: {file_path}")
                return None
            
            # Load JSON file
            with open(file_path, 'r', encoding='utf-8') as f:
                trip_dict = json.load(f)
            
            # Convert to Trip object
            trip = Trip(**trip_dict)
            
            logger.info(f"Loaded trip {trip_id} from {file_path}")
            return trip
            
        except Exception as e:
            logger.error(f"Error loading trip {trip_id}: {e}")
            return None
    
    async def list_all_trips(self) -> list[Trip]:
        """
        List all saved trips.
        
        Returns:
            List of Trip objects
        """
        try:
            trips = []
            
            # Find all JSON files
            for file_path in self.storage_dir.glob("*.json"):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        trip_dict = json.load(f)
                    
                    trip = Trip(**trip_dict)
                    trips.append(trip)
                    
                except Exception as e:
                    logger.error(f"Error loading trip from {file_path}: {e}")
                    continue
            
            logger.info(f"Loaded {len(trips)} trips from storage")
            return trips
            
        except Exception as e:
            logger.error(f"Error listing trips: {e}")
            return []
    
    async def delete_trip(self, trip_id: str) -> bool:
        """
        Delete a trip.
        
        Args:
            trip_id: Trip ID to delete
            
        Returns:
            True if successful, False otherwise
        """
        try:
            file_path = self._get_trip_file_path(trip_id)
            
            if not file_path.exists():
                logger.warning(f"Trip file not found: {file_path}")
                return False
            
            file_path.unlink()
            
            logger.info(f"Deleted trip {trip_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting trip {trip_id}: {e}")
            return False
    
    async def trip_exists(self, trip_id: str) -> bool:
        """Check if a trip exists."""
        file_path = self._get_trip_file_path(trip_id)
        return file_path.exists()


# Singleton instance
local_storage = LocalStorageService()
