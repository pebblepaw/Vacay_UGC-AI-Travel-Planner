"""
Pydantic models/schemas for VACAY API.
These match the frontend TypeScript interfaces in frontend/src/data/mockData.ts
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime


# ============================================================================
# REQUEST/RESPONSE SCHEMAS FOR VIDEO PROCESSING
# ============================================================================

class VideoProcessRequest(BaseModel):
    """Request to process one or more video URLs."""
    urls: list[str] = Field(..., min_length=1, description="List of video URLs to process")
    trip_title: Optional[str] = Field(None, description="Optional custom trip title")


class GeminiAnalysisResult(BaseModel):
    """Raw analysis result from Gemini."""
    locations: list[dict] = Field(default_factory=list, description="Locations extracted from video")
    activities: list[str] = Field(default_factory=list, description="Activities mentioned")
    vibes: list[str] = Field(default_factory=list, description="Vibe keywords")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")


# ============================================================================
# CORE TRIP DATA MODELS (match frontend TypeScript exactly)
# ============================================================================

class SourceVideo(BaseModel):
    """A source video that contributed to the trip."""
    platform: Literal['tiktok', 'douyin', 'youtube', 'rednote']
    url: str
    title: str


class POI(BaseModel):
    """A Point of Interest (place to visit)."""
    id: str
    name: str
    category: Literal['Food', 'Art', 'Nature', 'Culture', 'Shopping', 'Nightlife']
    coords: tuple[float, float] = Field(..., description="[longitude, latitude]")
    img: str = Field(..., description="Image URL")
    time_slot: str = Field(..., description="e.g. '10:00 - 13:00'")
    vibe: str = Field(..., description="Description of why this place is cool")
    travel_time: Optional[str] = Field(None, description="e.g. '🚃 25 min train'")
    priority: Literal['high','normal','low'] = Field('normal', description = "Importance of visiting this spot")
    intensity: Literal['high','normal','low'] = Field('normal', description = "Energy level required")
    visit_duration: int = Field(60, description = "Estimated visit time in minutes")

class Day(BaseModel):
    """One day of the itinerary."""
    day_number: int
    date: str = Field(..., description="ISO format: YYYY-MM-DD")
    pois: list[POI]


class Accommodation(BaseModel):
    """Accommodation for the trip."""
    name: str
    price_per_night: float
    status: str = Field(..., description="e.g. 'Found via Playwright - Best Match'")
    img: str
    coords: tuple[float, float] = Field(..., description="[longitude, latitude]")


class Trip(BaseModel):
    """A complete trip itinerary."""
    trip_id: str
    title: str
    source_videos: list[SourceVideo]
    days: list[Day]
    accommodation: Accommodation


# ============================================================================
# CHAT MODELS
# ============================================================================

class ChatOption(BaseModel):
    """An option in an interrupt message (e.g. hotel choices)."""
    id: str
    name: str
    price: float
    description: str


class ChatMessage(BaseModel):
    """A message in the chat sidebar."""
    id: str
    type: Literal['user', 'agent', 'interrupt']
    content: str
    timestamp: datetime
    interrupt_type: Optional[
        Literal['hotel_selection', 'poi_selection', 'confirmation', 'open_url']
    ] = None
    options: Optional[list[ChatOption]] = None
    status: Optional[Literal['pending', 'approved', 'rejected']] = None


# ============================================================================
# API RESPONSE SCHEMAS
# ============================================================================

class VideoProcessResponse(BaseModel):
    """Response after processing video(s)."""
    trip_id: str
    status: Literal['processing', 'completed', 'failed']
    message: str
    trip: Optional[Trip] = None
    error: Optional[str] = None


class TripListResponse(BaseModel):
    """List of all trips."""
    trips: list[Trip]


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    history: Optional[list[dict]] = None  # [{"role": "user"|"agent", "content": "..."}]


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    messages: list[ChatMessage]
    updated_trip: Optional[Trip] = None
