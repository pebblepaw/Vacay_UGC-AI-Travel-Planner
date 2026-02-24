"""
FastAPI routers for trip CRUD operations.
Handles getting, listing, and deleting trips.
"""
from fastapi import APIRouter, HTTPException
from typing import List
import logging

from backend.models.schemas import Trip, TripListResponse
from backend.storage.supabase_storage import supabase_storage as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["trips"])


@router.get("", response_model=TripListResponse)
async def list_trips():
    """
    Get all saved trips.
    
    Returns:
        List of all trips from storage
    """
    try:
        trips = await storage.list_all_trips()
        return TripListResponse(trips=trips)
        
    except Exception as e:
        logger.error(f"Error listing trips: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list trips: {str(e)}"
        )


@router.get("/{trip_id}", response_model=Trip)
async def get_trip(trip_id: str):
    """
    Get a specific trip by ID.
    
    Args:
        trip_id: Trip identifier
        
    Returns:
        Trip object
    """
    try:
        trip = await storage.load_trip(trip_id)
        
        if not trip:
            raise HTTPException(
                status_code=404,
                detail=f"Trip '{trip_id}' not found"
            )
        
        return trip
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting trip {trip_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get trip: {str(e)}"
        )


@router.delete("/{trip_id}")
async def delete_trip(trip_id: str):
    """
    Delete a trip.
    
    Args:
        trip_id: Trip identifier
        
    Returns:
        Success message
    """
    try:
        # Check if trip exists first
        exists = await storage.trip_exists(trip_id)
        
        if not exists:
            raise HTTPException(
                status_code=404,
                detail=f"Trip '{trip_id}' not found"
            )
        
        # Delete trip
        deleted = await storage.delete_trip(trip_id)
        
        if not deleted:
            raise HTTPException(
                status_code=500,
                detail="Failed to delete trip"
            )
        
        return {"message": f"Trip '{trip_id}' deleted successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting trip {trip_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete trip: {str(e)}"
        )
