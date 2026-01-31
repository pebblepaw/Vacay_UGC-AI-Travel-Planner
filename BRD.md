# VACAY - AI Agent Development Instructions

> **You are an autonomous coding agent building VACAY, an AI travel planner that converts TikTok videos into travel itineraries.**

---

## 🚨 BEFORE YOU START - MANDATORY READING

1. **Read this entire BRD.md file** to understand the project
2. **Read `PROGRESS.md`** - Check the "Codebase Patterns" section first, then recent progress entries
3. **Check current git branch** - Should be `main` for now
4. **Find the next uncompleted task** - Look for `[ ]` checkboxes below
5. **Complete ONE task at a time**, then commit and update PROGRESS.md

---

## 📋 Project Overview

**VACAY** converts short-form travel videos (TikTok, YouTube Shorts) into structured travel itineraries.

### User Flow
```
User pastes TikTok URL → Backend downloads video → Gemini AI extracts locations 
→ Tavily geocodes places → Frontend displays interactive map + itinerary
```

### Current State
- ✅ Frontend exists (React + Vite + Shadcn) - built by Lovable
- ❌ Backend does not exist - needs to be built
- ❌ Frontend uses mock data - needs to connect to real API

---

## 🏗️ Project Structure

```
VACAY/
├── .env                      # API keys (NEVER COMMIT)
├── .gitignore
├── BRD.md                    # THIS FILE - Agent instructions
├── PROGRESS.md               # Progress log and learnings
├── README.md                 # User-facing documentation
├── Sample_Inputs/
│   └── TikTok-Links.md       # Test URLs for development
│
├── backend/                  # Python FastAPI (TO BUILD)
│   ├── requirements.txt
│   ├── main.py               # FastAPI entry point
│   ├── config.py             # Environment config
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── videos.py         # POST /api/videos/process
│   │   └── trips.py          # GET/POST /api/trips
│   ├── services/
│   │   ├── __init__.py
│   │   ├── video_downloader.py   # yt-dlp wrapper
│   │   ├── gemini_analyzer.py    # Gemini 1.5 Pro
│   │   ├── location_service.py   # Tavily geocoding
│   │   └── itinerary_builder.py  # Day planning logic
│   ├── models/
│   │   ├── __init__.py
│   │   └── schemas.py        # Pydantic models
│   ├── storage/
│   │   ├── __init__.py
│   │   └── local_storage.py  # JSON file persistence
│   └── tests/
│       ├── __init__.py
│       ├── conftest.py
│       ├── test_video_downloader.py
│       ├── test_gemini_analyzer.py
│       ├── test_location_service.py
│       └── test_api.py
│
└── frontend/                 # React + Vite (EXISTS)
    ├── src/
    │   ├── services/
    │   │   └── api.ts        # TO CREATE: Backend API client
    │   ├── contexts/
    │   │   └── TripContext.tsx   # TO MODIFY: Connect to API
    │   └── components/
    │       └── trip/
    │           ├── AddUrlModal.tsx   # TO MODIFY: Real processing
    │           └── MapView.tsx       # TO MODIFY: Real Mapbox
    └── ...
```

---

## 🔑 Environment Variables

The `.env` file in project root contains (DO NOT LOG THESE):
```
GEMINI_API_KEY=...     # Google Gemini 1.5 Pro
TAVLY_API=...          # Tavily search API  
MAPBOX_PUBLIC=...      # Mapbox public token (frontend)
MAPBOX_SECRET=...      # Mapbox secret token (backend if needed)
```

---

## 🧪 Test URLs

Use these TikTok URLs for testing (from `Sample_Inputs/TikTok-Links.md`):

| Description | URL |
|-------------|-----|
| 25 second video | `https://www.tiktok.com/@roadynz/video/7440193649578659090` |
| Single restaurant | `https://www.tiktok.com/@miaandtheworld/video/7506102845653962002` |
| Photo slides | `https://www.tiktok.com/@christinaelle_/photo/7544978045929622792` |
| 2.5 min video | `https://www.tiktok.com/@ashlinpria/video/7595259514400673055` |

---

## ✅ IMPLEMENTATION CHECKLIST

Work through these tasks IN ORDER. Complete ONE task, commit, update PROGRESS.md, then move to the next.

---

### PHASE 1: Backend Foundation

#### Task 1.1: Python Environment Setup
- [ ] **Status**: Not started

**What to do:**
1. Create Python virtual environment in project root
2. Create `backend/` folder structure as shown above
3. Create `backend/requirements.txt` with dependencies
4. Install dependencies and verify

**Commands:**
```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/VACAY
python3 -m venv venv
source venv/bin/activate
mkdir -p backend/{routers,services,models,storage,tests}
touch backend/__init__.py
touch backend/routers/__init__.py
touch backend/services/__init__.py  
touch backend/models/__init__.py
touch backend/storage/__init__.py
touch backend/tests/__init__.py
touch backend/tests/conftest.py
```

**Create `backend/requirements.txt`:**
```
fastapi>=0.109.0
uvicorn[standard]>=0.27.0
python-dotenv>=1.0.0
yt-dlp>=2024.1.1
google-generativeai>=0.3.2
httpx>=0.26.0
pydantic>=2.5.3
python-multipart>=0.0.6
pytest>=7.4.4
pytest-asyncio>=0.23.3
```

**Verification:**
```bash
pip install -r backend/requirements.txt
python -c "import fastapi; import yt_dlp; import google.generativeai; print('All imports OK')"
```

**Done when:**
- [ ] `venv/` folder exists
- [ ] All `backend/` folders created
- [ ] `pip install` completes without errors
- [ ] Verification command prints "All imports OK"

**Commit message:** `feat: 1.1 - Python environment and backend folder structure`

---

#### Task 1.2: Configuration Module
- [ ] **Status**: Not started

**What to do:**
Create `backend/config.py` that loads environment variables from parent `.env` file.

**Create `backend/config.py`:**
```python
"""
Configuration module for VACAY backend.
Loads environment variables from ../.env file.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root (parent of backend/)
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(env_path)

class Settings:
    """Application settings loaded from environment variables."""
    
    # API Keys
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    TAVILY_API_KEY: str = os.getenv("TAVLY_API", "")  # Note: env var has typo "TAVLY"
    MAPBOX_PUBLIC: str = os.getenv("MAPBOX_PUBLIC", "")
    MAPBOX_SECRET: str = os.getenv("MAPBOX_SECRET", "")
    
    # Paths
    PROJECT_ROOT: Path = Path(__file__).parent.parent
    BACKEND_ROOT: Path = Path(__file__).parent
    DOWNLOADS_DIR: Path = PROJECT_ROOT / "downloads"
    DATA_DIR: Path = BACKEND_ROOT / "data"
    TRIPS_DIR: Path = DATA_DIR / "trips"
    
    # API Settings
    API_HOST: str = os.getenv("API_HOST", "0.0.0.0")
    API_PORT: int = int(os.getenv("API_PORT", "8000"))
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    
    def __init__(self):
        """Validate required settings and create directories."""
        self._validate()
        self._create_directories()
    
    def _validate(self):
        """Check that required API keys are present."""
        missing = []
        if not self.GEMINI_API_KEY:
            missing.append("GEMINI_API_KEY")
        if not self.TAVILY_API_KEY:
            missing.append("TAVLY_API")
        if not self.MAPBOX_PUBLIC:
            missing.append("MAPBOX_PUBLIC")
        
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    def _create_directories(self):
        """Create required directories if they don't exist."""
        self.DOWNLOADS_DIR.mkdir(exist_ok=True)
        self.DATA_DIR.mkdir(exist_ok=True)
        self.TRIPS_DIR.mkdir(exist_ok=True)

# Singleton instance
settings = Settings()
```

**Verification:**
```bash
cd backend
python -c "from config import settings; print(f'Gemini key loaded: {len(settings.GEMINI_API_KEY) > 0}')"
```

**Done when:**
- [ ] `backend/config.py` exists
- [ ] Verification prints `Gemini key loaded: True`
- [ ] `downloads/` and `backend/data/trips/` folders created

**Commit message:** `feat: 1.2 - Configuration module with environment loading`

---

#### Task 1.3: Pydantic Models/Schemas
- [ ] **Status**: Not started

**What to do:**
Create `backend/models/schemas.py` with all data models matching the frontend's TypeScript types.

**Create `backend/models/schemas.py`:**
```python
"""
Pydantic models for VACAY API.
These match the TypeScript interfaces in frontend/src/data/mockData.ts
"""
from datetime import datetime
from typing import List, Optional, Literal
from pydantic import BaseModel, Field
import uuid

# === Enums and Literals ===
Platform = Literal["tiktok", "youtube", "douyin", "rednote"]
Category = Literal["Food", "Art", "Nature", "Culture", "Shopping", "Nightlife"]
MessageType = Literal["user", "agent", "interrupt"]
InterruptType = Literal["hotel_selection", "poi_selection", "confirmation"]
MessageStatus = Literal["pending", "approved", "rejected"]


# === Source Video ===
class SourceVideo(BaseModel):
    """A video source that was processed to create the trip."""
    platform: Platform
    url: str
    title: str
    thumbnail: Optional[str] = None


# === Point of Interest ===
class POI(BaseModel):
    """A location/place extracted from videos."""
    id: str = Field(default_factory=lambda: f"poi_{uuid.uuid4().hex[:8]}")
    name: str
    category: Category
    coords: tuple[float, float]  # [longitude, latitude]
    img: str = ""
    address: Optional[str] = None
    time_slot: Optional[str] = None
    vibe: str = ""
    travel_time: Optional[str] = None
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "poi_abc123",
                "name": "TeamLab Borderless",
                "category": "Art",
                "coords": [139.7834, 35.6267],
                "img": "https://example.com/image.jpg",
                "address": "1-3-8 Aomi, Koto City, Tokyo",
                "time_slot": "10:00 - 13:00",
                "vibe": "Immersive digital art museum with infinity rooms",
                "travel_time": "🚃 25 min train"
            }
        }


# === Day ===
class Day(BaseModel):
    """A single day in the itinerary."""
    day_number: int
    date: str  # ISO format date string
    pois: List[POI] = []


# === Accommodation ===
class Accommodation(BaseModel):
    """Accommodation/hotel information."""
    name: str
    price_per_night: float
    status: str = ""
    img: str = ""
    coords: tuple[float, float]


# === Trip ===
class Trip(BaseModel):
    """A complete trip itinerary."""
    trip_id: str = Field(default_factory=lambda: f"trip_{uuid.uuid4().hex[:8]}")
    title: str
    source_videos: List[SourceVideo] = []
    days: List[Day] = []
    accommodation: Optional[Accommodation] = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


# === Chat ===
class ChatOption(BaseModel):
    """An option presented to user in interrupt messages."""
    id: str
    name: str
    price: float
    description: str


class ChatMessage(BaseModel):
    """A message in the chat interface."""
    id: str = Field(default_factory=lambda: f"msg_{uuid.uuid4().hex[:8]}")
    type: MessageType
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    interrupt_type: Optional[InterruptType] = None
    options: Optional[List[ChatOption]] = None
    status: Optional[MessageStatus] = None


# === API Request/Response Models ===
class VideoProcessRequest(BaseModel):
    """Request to process a video URL."""
    url: str
    platform: Optional[Platform] = None  # Auto-detected if not provided


class VideoProcessResponse(BaseModel):
    """Response from video processing."""
    status: Literal["success", "processing", "error"]
    trip_id: Optional[str] = None
    trip: Optional[Trip] = None
    message: Optional[str] = None
    error: Optional[str] = None


class ChatRequest(BaseModel):
    """Request to send a chat message."""
    message: str


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    message: ChatMessage


# === Gemini Analysis Result ===
class ExtractedLocation(BaseModel):
    """A location extracted by Gemini from video analysis."""
    name: str
    category: Optional[Category] = None
    description: str = ""
    time_recommendation: Optional[str] = None
    confidence: float = 0.8


class GeminiAnalysisResult(BaseModel):
    """Result from Gemini video analysis."""
    city: str
    country: str
    locations: List[ExtractedLocation]
    overall_vibe: str = ""
    trip_title_suggestion: str = ""
```

**Verification:**
```bash
cd backend
python -c "from models.schemas import Trip, POI, VideoProcessRequest; print('Models OK')"
```

**Done when:**
- [ ] `backend/models/schemas.py` exists
- [ ] Verification prints "Models OK"
- [ ] All models match frontend TypeScript interfaces

**Commit message:** `feat: 1.3 - Pydantic models matching frontend types`

---

#### Task 1.4: Video Downloader Service
- [ ] **Status**: Not started

**What to do:**
Create `backend/services/video_downloader.py` using yt-dlp to download TikTok videos.

**Create `backend/services/video_downloader.py`:**
```python
"""
Video download service using yt-dlp.
Downloads TikTok/YouTube videos to local storage for Gemini analysis.
"""
import os
import tempfile
from pathlib import Path
from typing import Optional
from dataclasses import dataclass
import yt_dlp

from config import settings


@dataclass
class DownloadResult:
    """Result of a video download operation."""
    success: bool
    video_path: Optional[Path] = None
    thumbnail_url: Optional[str] = None
    title: Optional[str] = None
    duration: Optional[int] = None  # seconds
    error: Optional[str] = None


def detect_platform(url: str) -> str:
    """Detect the platform from a URL."""
    url_lower = url.lower()
    if "tiktok.com" in url_lower:
        return "tiktok"
    elif "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "douyin.com" in url_lower:
        return "douyin"
    elif "xiaohongshu.com" in url_lower:
        return "rednote"
    else:
        return "unknown"


def download_video(url: str, output_dir: Optional[Path] = None) -> DownloadResult:
    """
    Download a video from TikTok, YouTube, etc.
    
    Args:
        url: The video URL to download
        output_dir: Directory to save the video (defaults to settings.DOWNLOADS_DIR)
    
    Returns:
        DownloadResult with video path and metadata
    """
    if output_dir is None:
        output_dir = settings.DOWNLOADS_DIR
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate unique filename
    import uuid
    video_id = uuid.uuid4().hex[:12]
    output_template = str(output_dir / f"{video_id}.%(ext)s")
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',  # Prefer mp4 for Gemini compatibility
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        # For TikTok, we might need these options
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Extract info first
            info = ydl.extract_info(url, download=True)
            
            if info is None:
                return DownloadResult(
                    success=False,
                    error="Could not extract video information"
                )
            
            # Find the downloaded file
            ext = info.get('ext', 'mp4')
            video_path = output_dir / f"{video_id}.{ext}"
            
            # Handle potential different extensions
            if not video_path.exists():
                # Look for any file with our video_id
                for f in output_dir.glob(f"{video_id}.*"):
                    video_path = f
                    break
            
            if not video_path.exists():
                return DownloadResult(
                    success=False,
                    error="Download completed but file not found"
                )
            
            return DownloadResult(
                success=True,
                video_path=video_path,
                thumbnail_url=info.get('thumbnail'),
                title=info.get('title', 'Untitled'),
                duration=info.get('duration'),
            )
            
    except yt_dlp.utils.DownloadError as e:
        return DownloadResult(
            success=False,
            error=f"Download error: {str(e)}"
        )
    except Exception as e:
        return DownloadResult(
            success=False,
            error=f"Unexpected error: {str(e)}"
        )


def cleanup_video(video_path: Path) -> bool:
    """Delete a downloaded video file."""
    try:
        if video_path.exists():
            video_path.unlink()
            return True
        return False
    except Exception:
        return False
```

**Create test file `backend/tests/test_video_downloader.py`:**
```python
"""Tests for video downloader service."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.video_downloader import download_video, detect_platform, cleanup_video, DownloadResult


class TestDetectPlatform:
    """Tests for platform detection."""
    
    def test_detect_tiktok(self):
        assert detect_platform("https://www.tiktok.com/@user/video/123") == "tiktok"
        assert detect_platform("https://tiktok.com/@user/video/123") == "tiktok"
    
    def test_detect_youtube(self):
        assert detect_platform("https://www.youtube.com/shorts/abc") == "youtube"
        assert detect_platform("https://youtu.be/abc") == "youtube"
    
    def test_detect_unknown(self):
        assert detect_platform("https://example.com/video") == "unknown"


class TestDownloadVideo:
    """Tests for video downloading."""
    
    @pytest.mark.slow
    def test_download_tiktok_short_video(self, tmp_path):
        """Test downloading the 25-second TikTok video."""
        url = "https://www.tiktok.com/@roadynz/video/7440193649578659090"
        result = download_video(url, output_dir=tmp_path)
        
        assert result.success, f"Download failed: {result.error}"
        assert result.video_path is not None
        assert result.video_path.exists()
        assert result.title is not None
        
        # Cleanup
        cleanup_video(result.video_path)
    
    @pytest.mark.slow
    def test_download_invalid_url(self, tmp_path):
        """Test handling of invalid URL."""
        url = "https://www.tiktok.com/@user/video/invalid123"
        result = download_video(url, output_dir=tmp_path)
        
        # Should fail gracefully
        assert result.success == False
        assert result.error is not None
```

**Verification:**
```bash
cd backend
# Quick test (no network)
python -c "from services.video_downloader import detect_platform; print(detect_platform('https://tiktok.com/x'))"

# Full test (downloads video - slow)
python -m pytest tests/test_video_downloader.py -v -m "not slow" 
python -m pytest tests/test_video_downloader.py::TestDownloadVideo::test_download_tiktok_short_video -v
```

**Done when:**
- [ ] `backend/services/video_downloader.py` exists
- [ ] `backend/tests/test_video_downloader.py` exists
- [ ] Platform detection tests pass
- [ ] Can download the 25-second TikTok video successfully

**Commit message:** `feat: 1.4 - Video downloader service with yt-dlp`

---

#### Task 1.5: Gemini Analyzer Service
- [ ] **Status**: Not started

**What to do:**
Create `backend/services/gemini_analyzer.py` to analyze videos with Gemini 1.5 Pro.

**Create `backend/services/gemini_analyzer.py`:**
```python
"""
Gemini AI video analysis service.
Uses Gemini 1.5 Pro to extract travel locations from videos.
"""
import json
import time
from pathlib import Path
from typing import Optional
import google.generativeai as genai

from config import settings
from models.schemas import GeminiAnalysisResult, ExtractedLocation, Category

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)

# The prompt for extracting travel information
EXTRACTION_PROMPT = """You are a travel content analyzer. Analyze this travel video/image and extract location information.

Your task:
1. Identify the city and country featured
2. Extract ALL specific locations mentioned or shown (restaurants, attractions, hotels, cafes, shops, etc.)
3. For each location, provide:
   - Exact name (as specific as possible)
   - Category: one of [Food, Art, Nature, Culture, Shopping, Nightlife]
   - Brief "vibe" description (atmosphere, what makes it special, 1-2 sentences)
   - Time recommendation if mentioned (e.g., "2-3 hours", "best at sunset")

Return your response as valid JSON in this exact format:
{
  "city": "Tokyo",
  "country": "Japan",
  "trip_title_suggestion": "Hidden Gems of Tokyo",
  "overall_vibe": "A mix of traditional culture and modern experiences",
  "locations": [
    {
      "name": "TeamLab Borderless",
      "category": "Art",
      "description": "Immersive digital art museum with stunning infinity mirror rooms",
      "time_recommendation": "2-3 hours"
    }
  ]
}

Important:
- Be as specific as possible with location names
- If you can't identify a specific place, describe what type of place it is
- Include ALL locations you can identify, even briefly shown ones
- If this is a food video, the main dish/restaurant is most important
- Return ONLY the JSON, no other text"""


def analyze_video(video_path: Path) -> Optional[GeminiAnalysisResult]:
    """
    Analyze a video file using Gemini 1.5 Pro.
    
    Args:
        video_path: Path to the video file
        
    Returns:
        GeminiAnalysisResult with extracted locations, or None if failed
    """
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")
    
    # Upload video to Gemini
    print(f"Uploading video to Gemini: {video_path}")
    video_file = genai.upload_file(path=str(video_path))
    
    # Wait for processing
    print("Waiting for Gemini to process video...")
    while video_file.state.name == "PROCESSING":
        time.sleep(2)
        video_file = genai.get_file(video_file.name)
    
    if video_file.state.name == "FAILED":
        raise RuntimeError(f"Gemini video processing failed: {video_file.state.name}")
    
    # Generate content
    print("Analyzing video content...")
    model = genai.GenerativeModel("gemini-1.5-pro")
    
    response = model.generate_content(
        [video_file, EXTRACTION_PROMPT],
        generation_config=genai.GenerationConfig(
            temperature=0.2,  # Lower temperature for more consistent JSON
            max_output_tokens=2048,
        )
    )
    
    # Parse response
    try:
        # Clean up response text (remove markdown code blocks if present)
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        
        # Convert to our models
        locations = []
        for loc in data.get("locations", []):
            # Validate category
            category = loc.get("category", "Culture")
            if category not in ["Food", "Art", "Nature", "Culture", "Shopping", "Nightlife"]:
                category = "Culture"
            
            locations.append(ExtractedLocation(
                name=loc.get("name", "Unknown Location"),
                category=category,
                description=loc.get("description", ""),
                time_recommendation=loc.get("time_recommendation"),
                confidence=0.8
            ))
        
        return GeminiAnalysisResult(
            city=data.get("city", "Unknown"),
            country=data.get("country", "Unknown"),
            locations=locations,
            overall_vibe=data.get("overall_vibe", ""),
            trip_title_suggestion=data.get("trip_title_suggestion", f"Trip to {data.get('city', 'Unknown')}")
        )
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response as JSON: {e}")
        print(f"Response was: {response.text[:500]}")
        return None
    
    finally:
        # Clean up uploaded file
        try:
            genai.delete_file(video_file.name)
        except Exception:
            pass


def analyze_image(image_path: Path) -> Optional[GeminiAnalysisResult]:
    """
    Analyze an image file using Gemini 1.5 Pro.
    Used for photo slideshows from TikTok.
    """
    if not image_path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")
    
    # Upload image
    image_file = genai.upload_file(path=str(image_path))
    
    # Generate content (images process instantly, no waiting needed)
    model = genai.GenerativeModel("gemini-1.5-pro")
    
    response = model.generate_content(
        [image_file, EXTRACTION_PROMPT],
        generation_config=genai.GenerationConfig(
            temperature=0.2,
            max_output_tokens=2048,
        )
    )
    
    # Parse response (same logic as video)
    try:
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        data = json.loads(text)
        
        locations = []
        for loc in data.get("locations", []):
            category = loc.get("category", "Culture")
            if category not in ["Food", "Art", "Nature", "Culture", "Shopping", "Nightlife"]:
                category = "Culture"
            
            locations.append(ExtractedLocation(
                name=loc.get("name", "Unknown Location"),
                category=category,
                description=loc.get("description", ""),
                time_recommendation=loc.get("time_recommendation"),
                confidence=0.8
            ))
        
        return GeminiAnalysisResult(
            city=data.get("city", "Unknown"),
            country=data.get("country", "Unknown"),
            locations=locations,
            overall_vibe=data.get("overall_vibe", ""),
            trip_title_suggestion=data.get("trip_title_suggestion", f"Trip to {data.get('city', 'Unknown')}")
        )
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse Gemini response: {e}")
        return None
    
    finally:
        try:
            genai.delete_file(image_file.name)
        except Exception:
            pass
```

**Create test file `backend/tests/test_gemini_analyzer.py`:**
```python
"""Tests for Gemini analyzer service."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.gemini_analyzer import analyze_video
from services.video_downloader import download_video, cleanup_video


class TestGeminiAnalyzer:
    """Tests for Gemini video analysis."""
    
    @pytest.mark.slow
    @pytest.mark.api
    def test_analyze_short_tiktok(self, tmp_path):
        """Test analyzing the 25-second TikTok video."""
        # First download the video
        url = "https://www.tiktok.com/@roadynz/video/7440193649578659090"
        download_result = download_video(url, output_dir=tmp_path)
        
        assert download_result.success, f"Download failed: {download_result.error}"
        
        try:
            # Analyze with Gemini
            result = analyze_video(download_result.video_path)
            
            assert result is not None, "Analysis returned None"
            assert result.city != "", "City should be extracted"
            assert len(result.locations) > 0, "Should extract at least one location"
            
            print(f"Extracted city: {result.city}")
            print(f"Locations found: {len(result.locations)}")
            for loc in result.locations:
                print(f"  - {loc.name} ({loc.category})")
                
        finally:
            cleanup_video(download_result.video_path)
    
    @pytest.mark.slow
    @pytest.mark.api
    def test_analyze_restaurant_video(self, tmp_path):
        """Test analyzing a restaurant-focused video."""
        url = "https://www.tiktok.com/@miaandtheworld/video/7506102845653962002"
        download_result = download_video(url, output_dir=tmp_path)
        
        assert download_result.success, f"Download failed: {download_result.error}"
        
        try:
            result = analyze_video(download_result.video_path)
            
            assert result is not None
            # Restaurant video should identify at least one Food location
            food_locations = [loc for loc in result.locations if loc.category == "Food"]
            print(f"Food locations found: {len(food_locations)}")
            
        finally:
            cleanup_video(download_result.video_path)
```

**Verification:**
```bash
cd backend
# Test imports
python -c "from services.gemini_analyzer import analyze_video; print('Gemini analyzer OK')"

# Run actual test (uses API - costs tokens)
python -m pytest tests/test_gemini_analyzer.py::TestGeminiAnalyzer::test_analyze_short_tiktok -v -s
```

**Done when:**
- [ ] `backend/services/gemini_analyzer.py` exists
- [ ] `backend/tests/test_gemini_analyzer.py` exists
- [ ] Can analyze the 25-second TikTok and extract at least 1 location
- [ ] Response is properly parsed into GeminiAnalysisResult

**Commit message:** `feat: 1.5 - Gemini video analyzer service`

---

#### Task 1.6: Tavily Location Service
- [ ] **Status**: Not started

**What to do:**
Create `backend/services/location_service.py` to geocode locations using Tavily API.

**Create `backend/services/location_service.py`:**
```python
"""
Location service using Tavily API.
Verifies location names and retrieves coordinates.
"""
import httpx
from typing import Optional, List, Tuple
from dataclasses import dataclass

from config import settings


@dataclass
class LocationData:
    """Geocoded location data."""
    name: str
    address: Optional[str] = None
    coords: Optional[Tuple[float, float]] = None  # (longitude, latitude)
    place_type: Optional[str] = None
    source_url: Optional[str] = None
    confidence: float = 0.5


async def search_location(query: str, city: str = "", country: str = "") -> Optional[LocationData]:
    """
    Search for a location using Tavily API.
    
    Args:
        query: Location name to search for
        city: City context to improve search
        country: Country context to improve search
        
    Returns:
        LocationData with coordinates if found, None otherwise
    """
    # Build search query with context
    search_query = f"{query}"
    if city:
        search_query += f" {city}"
    if country:
        search_query += f" {country}"
    search_query += " address location coordinates"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": settings.TAVILY_API_KEY,
                    "query": search_query,
                    "search_depth": "basic",
                    "include_answer": True,
                    "max_results": 5
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract location info from results
            answer = data.get("answer", "")
            results = data.get("results", [])
            
            # Try to extract coordinates from answer or results
            coords = extract_coordinates_from_text(answer)
            if not coords and results:
                for result in results:
                    content = result.get("content", "")
                    coords = extract_coordinates_from_text(content)
                    if coords:
                        break
            
            # If we still don't have coords, use a geocoding fallback
            if not coords:
                coords = await geocode_with_nominatim(query, city, country)
            
            return LocationData(
                name=query,
                address=extract_address_from_results(results),
                coords=coords,
                source_url=results[0].get("url") if results else None,
                confidence=0.8 if coords else 0.3
            )
            
        except httpx.HTTPError as e:
            print(f"Tavily API error: {e}")
            # Fallback to Nominatim
            coords = await geocode_with_nominatim(query, city, country)
            return LocationData(
                name=query,
                coords=coords,
                confidence=0.5 if coords else 0.1
            )


async def geocode_with_nominatim(query: str, city: str = "", country: str = "") -> Optional[Tuple[float, float]]:
    """
    Fallback geocoding using OpenStreetMap Nominatim (free).
    
    Returns:
        Tuple of (longitude, latitude) or None
    """
    search_query = query
    if city:
        search_query += f", {city}"
    if country:
        search_query += f", {country}"
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": search_query,
                    "format": "json",
                    "limit": 1
                },
                headers={
                    "User-Agent": "VACAY-Travel-Planner/1.0"
                },
                timeout=10.0
            )
            response.raise_for_status()
            results = response.json()
            
            if results:
                lat = float(results[0]["lat"])
                lon = float(results[0]["lon"])
                return (lon, lat)  # Return as (longitude, latitude)
            
            return None
            
        except Exception as e:
            print(f"Nominatim geocoding error: {e}")
            return None


def extract_coordinates_from_text(text: str) -> Optional[Tuple[float, float]]:
    """
    Try to extract coordinates from text using regex.
    Looks for patterns like "35.6762° N, 139.6503° E" or "35.6762, 139.6503"
    """
    import re
    
    # Pattern for decimal coordinates
    pattern = r'(-?\d+\.?\d*)[°]?\s*[,\s]\s*(-?\d+\.?\d*)[°]?'
    matches = re.findall(pattern, text)
    
    for match in matches:
        try:
            lat = float(match[0])
            lon = float(match[1])
            
            # Validate ranges
            if -90 <= lat <= 90 and -180 <= lon <= 180:
                return (lon, lat)
            # Try swapped
            if -90 <= lon <= 90 and -180 <= lat <= 180:
                return (lat, lon)
        except ValueError:
            continue
    
    return None


def extract_address_from_results(results: List[dict]) -> Optional[str]:
    """Extract an address from Tavily search results."""
    for result in results:
        content = result.get("content", "")
        # Look for address-like patterns
        # This is a simple heuristic
        if any(word in content.lower() for word in ["address", "located at", "street", "avenue"]):
            # Return first ~100 chars that might be an address
            return content[:200] + "..." if len(content) > 200 else content
    return None


async def batch_geocode(
    locations: List[str], 
    city: str = "", 
    country: str = ""
) -> List[LocationData]:
    """
    Geocode multiple locations.
    
    Args:
        locations: List of location names
        city: City context
        country: Country context
        
    Returns:
        List of LocationData for each location
    """
    results = []
    for loc_name in locations:
        result = await search_location(loc_name, city, country)
        results.append(result)
        # Small delay to avoid rate limiting
        import asyncio
        await asyncio.sleep(0.5)
    return results
```

**Create test file `backend/tests/test_location_service.py`:**
```python
"""Tests for location service."""
import pytest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from services.location_service import search_location, geocode_with_nominatim, batch_geocode


class TestGeocoding:
    """Tests for geocoding functionality."""
    
    @pytest.mark.asyncio
    async def test_nominatim_tokyo_tower(self):
        """Test geocoding Tokyo Tower with Nominatim."""
        coords = await geocode_with_nominatim("Tokyo Tower", "Tokyo", "Japan")
        
        assert coords is not None, "Should find Tokyo Tower"
        lon, lat = coords
        
        # Tokyo Tower is approximately at 35.6586° N, 139.7454° E
        assert 35.6 < lat < 35.7, f"Latitude should be near 35.65, got {lat}"
        assert 139.7 < lon < 139.8, f"Longitude should be near 139.74, got {lon}"
    
    @pytest.mark.asyncio
    async def test_nominatim_unknown_location(self):
        """Test geocoding an unknown location."""
        coords = await geocode_with_nominatim("Definitely Not A Real Place XYZ123")
        assert coords is None, "Should return None for unknown location"
    
    @pytest.mark.asyncio
    @pytest.mark.api
    async def test_search_location_with_tavily(self):
        """Test full location search with Tavily."""
        result = await search_location("TeamLab Borderless", "Tokyo", "Japan")
        
        assert result is not None
        assert result.name == "TeamLab Borderless"
        
        if result.coords:
            lon, lat = result.coords
            # TeamLab is in Odaiba, Tokyo
            assert 35.6 < lat < 35.7
            assert 139.7 < lon < 139.9
    
    @pytest.mark.asyncio
    async def test_batch_geocode(self):
        """Test batch geocoding multiple locations."""
        locations = ["Tokyo Tower", "Senso-ji Temple"]
        results = await batch_geocode(locations, "Tokyo", "Japan")
        
        assert len(results) == 2
        assert all(r.name for r in results)
```

**Verification:**
```bash
cd backend
# Test imports
python -c "from services.location_service import search_location; print('Location service OK')"

# Run tests
python -m pytest tests/test_location_service.py -v
```

**Done when:**
- [ ] `backend/services/location_service.py` exists
- [ ] `backend/tests/test_location_service.py` exists
- [ ] Can geocode "Tokyo Tower" and get coordinates near (139.74, 35.65)
- [ ] Nominatim fallback works when Tavily fails

**Commit message:** `feat: 1.6 - Tavily location service with Nominatim fallback`

---

#### Task 1.7: Itinerary Builder Service
- [ ] **Status**: Not started

**What to do:**
Create `backend/services/itinerary_builder.py` to organize POIs into a day-by-day itinerary.

**Create `backend/services/itinerary_builder.py`:**
```python
"""
Itinerary builder service.
Organizes POIs into logical day-by-day plans based on location clustering.
"""
from datetime import datetime, timedelta
from typing import List, Tuple
import math

from models.schemas import POI, Day, Trip, SourceVideo, GeminiAnalysisResult, ExtractedLocation
from services.location_service import LocationData


def haversine_distance(coord1: Tuple[float, float], coord2: Tuple[float, float]) -> float:
    """
    Calculate the distance between two points on Earth using Haversine formula.
    
    Args:
        coord1: (longitude, latitude) of first point
        coord2: (longitude, latitude) of second point
        
    Returns:
        Distance in kilometers
    """
    lon1, lat1 = coord1
    lon2, lat2 = coord2
    
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lon = math.radians(lon2 - lon1)
    
    a = math.sin(delta_lat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    
    return R * c


def estimate_travel_time(distance_km: float) -> str:
    """
    Estimate travel time based on distance.
    
    Returns a human-readable travel time string.
    """
    if distance_km < 1:
        return "🚶 5 min walk"
    elif distance_km < 3:
        minutes = int(distance_km * 12)  # ~5km/h walking
        return f"🚶 {minutes} min walk"
    elif distance_km < 10:
        minutes = int(distance_km * 3)  # ~20km/h including waiting
        return f"🚃 {minutes} min transit"
    else:
        minutes = int(distance_km * 2)  # ~30km/h average
        return f"🚃 {minutes} min train"


def cluster_pois_by_proximity(pois: List[POI], max_per_day: int = 4) -> List[List[POI]]:
    """
    Cluster POIs by geographic proximity for day planning.
    Uses a simple greedy algorithm.
    
    Args:
        pois: List of POIs with coordinates
        max_per_day: Maximum POIs per day
        
    Returns:
        List of POI lists, one per day
    """
    if not pois:
        return []
    
    # Filter POIs with valid coordinates
    valid_pois = [p for p in pois if p.coords and p.coords[0] != 0 and p.coords[1] != 0]
    if not valid_pois:
        # If no valid coords, just split evenly
        return [pois[i:i+max_per_day] for i in range(0, len(pois), max_per_day)]
    
    remaining = valid_pois.copy()
    days = []
    
    while remaining:
        # Start a new day with the first remaining POI
        current_day = [remaining.pop(0)]
        
        while len(current_day) < max_per_day and remaining:
            # Find the closest POI to the last one in current day
            last_poi = current_day[-1]
            min_distance = float('inf')
            closest_idx = 0
            
            for i, poi in enumerate(remaining):
                dist = haversine_distance(last_poi.coords, poi.coords)
                if dist < min_distance:
                    min_distance = dist
                    closest_idx = i
            
            # Add the closest POI to current day
            current_day.append(remaining.pop(closest_idx))
        
        days.append(current_day)
    
    return days


def add_travel_times(pois: List[POI]) -> List[POI]:
    """
    Add travel time estimates between consecutive POIs.
    """
    if len(pois) < 2:
        return pois
    
    result = []
    for i, poi in enumerate(pois):
        if i > 0:
            prev_poi = pois[i-1]
            if poi.coords and prev_poi.coords:
                distance = haversine_distance(prev_poi.coords, poi.coords)
                poi.travel_time = estimate_travel_time(distance)
        result.append(poi)
    
    return result


def assign_time_slots(pois: List[POI], start_hour: int = 9) -> List[POI]:
    """
    Assign time slots to POIs based on category.
    """
    time_durations = {
        "Food": 1.5,      # 1.5 hours for meals
        "Art": 2.5,       # 2.5 hours for museums
        "Nature": 2.0,    # 2 hours for parks
        "Culture": 2.0,   # 2 hours for temples/shrines
        "Shopping": 2.0,  # 2 hours for shopping
        "Nightlife": 3.0, # 3 hours for nightlife
    }
    
    current_time = start_hour
    result = []
    
    for poi in pois:
        duration = time_durations.get(poi.category, 2.0)
        
        # Format time slot
        start = f"{int(current_time):02d}:{int((current_time % 1) * 60):02d}"
        end_time = current_time + duration
        end = f"{int(end_time):02d}:{int((end_time % 1) * 60):02d}"
        
        poi.time_slot = f"{start} - {end}"
        result.append(poi)
        
        # Add travel time (30 min average) plus duration
        current_time = end_time + 0.5
    
    return result


def build_trip(
    analysis: GeminiAnalysisResult,
    location_data: List[LocationData],
    source_video: SourceVideo
) -> Trip:
    """
    Build a complete Trip from analysis results and geocoded locations.
    
    Args:
        analysis: Gemini analysis result
        location_data: Geocoded location data
        source_video: The source video that was processed
        
    Returns:
        Complete Trip object
    """
    # Create POIs from analysis and location data
    pois = []
    for i, (extracted, geo_data) in enumerate(zip(analysis.locations, location_data)):
        # Get image placeholder based on category
        category_images = {
            "Food": "https://images.unsplash.com/photo-1557872943-16a5ac26437e?w=600&h=400&fit=crop",
            "Art": "https://images.unsplash.com/photo-1549887534-1541e9326642?w=600&h=400&fit=crop",
            "Nature": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&h=400&fit=crop",
            "Culture": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600&h=400&fit=crop",
            "Shopping": "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600&h=400&fit=crop",
            "Nightlife": "https://images.unsplash.com/photo-1554797589-7241bb691973?w=600&h=400&fit=crop",
        }
        
        poi = POI(
            name=extracted.name,
            category=extracted.category or "Culture",
            coords=geo_data.coords or (0, 0),
            img=category_images.get(extracted.category, category_images["Culture"]),
            address=geo_data.address,
            vibe=extracted.description,
        )
        pois.append(poi)
    
    # Cluster POIs into days
    daily_clusters = cluster_pois_by_proximity(pois)
    
    # Build days
    days = []
    start_date = datetime.now() + timedelta(days=30)  # Trip starts 30 days from now
    
    for i, day_pois in enumerate(daily_clusters):
        # Add travel times and time slots
        day_pois = add_travel_times(day_pois)
        day_pois = assign_time_slots(day_pois)
        
        day = Day(
            day_number=i + 1,
            date=(start_date + timedelta(days=i)).strftime("%Y-%m-%d"),
            pois=day_pois
        )
        days.append(day)
    
    # Create trip
    trip = Trip(
        title=analysis.trip_title_suggestion or f"Trip to {analysis.city}",
        source_videos=[source_video],
        days=days,
    )
    
    return trip
```

**Verification:**
```bash
cd backend
python -c "from services.itinerary_builder import build_trip, cluster_pois_by_proximity; print('Itinerary builder OK')"
```

**Done when:**
- [ ] `backend/services/itinerary_builder.py` exists
- [ ] POI clustering works based on proximity
- [ ] Travel times are estimated between POIs
- [ ] Time slots are assigned to POIs

**Commit message:** `feat: 1.7 - Itinerary builder with POI clustering`

---

#### Task 1.8: Local Storage Service
- [ ] **Status**: Not started

**What to do:**
Create `backend/storage/local_storage.py` for saving trips as JSON files.

**Create `backend/storage/local_storage.py`:**
```python
"""
Local storage service for persisting trips as JSON files.
"""
import json
from pathlib import Path
from typing import Optional, List
from datetime import datetime

from config import settings
from models.schemas import Trip


def _get_trip_path(trip_id: str) -> Path:
    """Get the file path for a trip."""
    return settings.TRIPS_DIR / f"{trip_id}.json"


def save_trip(trip: Trip) -> bool:
    """
    Save a trip to local storage.
    
    Args:
        trip: Trip object to save
        
    Returns:
        True if successful, False otherwise
    """
    try:
        path = _get_trip_path(trip.trip_id)
        
        # Convert to dict, handling datetime serialization
        trip_dict = trip.model_dump()
        trip_dict["created_at"] = trip.created_at.isoformat()
        trip_dict["updated_at"] = datetime.now().isoformat()
        
        with open(path, "w") as f:
            json.dump(trip_dict, f, indent=2, default=str)
        
        return True
    except Exception as e:
        print(f"Error saving trip: {e}")
        return False


def get_trip(trip_id: str) -> Optional[Trip]:
    """
    Load a trip from local storage.
    
    Args:
        trip_id: ID of the trip to load
        
    Returns:
        Trip object if found, None otherwise
    """
    try:
        path = _get_trip_path(trip_id)
        if not path.exists():
            return None
        
        with open(path, "r") as f:
            data = json.load(f)
        
        # Parse datetime strings
        if "created_at" in data and isinstance(data["created_at"], str):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if "updated_at" in data and isinstance(data["updated_at"], str):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        
        return Trip(**data)
    except Exception as e:
        print(f"Error loading trip: {e}")
        return None


def list_trips() -> List[Trip]:
    """
    List all saved trips.
    
    Returns:
        List of Trip objects
    """
    trips = []
    for path in settings.TRIPS_DIR.glob("*.json"):
        trip_id = path.stem
        trip = get_trip(trip_id)
        if trip:
            trips.append(trip)
    
    # Sort by creation date, newest first
    trips.sort(key=lambda t: t.created_at, reverse=True)
    return trips


def delete_trip(trip_id: str) -> bool:
    """
    Delete a trip from local storage.
    
    Args:
        trip_id: ID of the trip to delete
        
    Returns:
        True if deleted, False otherwise
    """
    try:
        path = _get_trip_path(trip_id)
        if path.exists():
            path.unlink()
            return True
        return False
    except Exception as e:
        print(f"Error deleting trip: {e}")
        return False
```

**Verification:**
```bash
cd backend
python -c "from storage.local_storage import save_trip, get_trip, list_trips; print('Storage OK')"
```

**Done when:**
- [ ] `backend/storage/local_storage.py` exists
- [ ] Can save and retrieve a Trip object
- [ ] Trips stored as JSON in `backend/data/trips/`

**Commit message:** `feat: 1.8 - Local storage service for trips`

---

### PHASE 2: API Endpoints

#### Task 2.1: FastAPI Main Application
- [ ] **Status**: Not started

**What to do:**
Create `backend/main.py` with FastAPI app, CORS, and health check.

**Create `backend/main.py`:**
```python
"""
VACAY Backend API
FastAPI application for processing travel videos into itineraries.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import videos, trips

# Create FastAPI app
app = FastAPI(
    title="VACAY API",
    description="AI-powered travel itinerary generator from social media videos",
    version="1.0.0",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.FRONTEND_URL,
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(videos.router, prefix="/api/videos", tags=["Videos"])
app.include_router(trips.router, prefix="/api/trips", tags=["Trips"])


@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "service": "VACAY API",
        "version": "1.0.0"
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=True
    )
```

**Verification:**
```bash
cd backend
python -c "from main import app; print('FastAPI app OK')"
```

**Note:** This will fail until routers are created in next tasks.

**Done when:**
- [ ] `backend/main.py` exists
- [ ] CORS configured for frontend origin

**Commit message:** `feat: 2.1 - FastAPI main application with CORS`

---

#### Task 2.2: Videos Router
- [ ] **Status**: Not started

**What to do:**
Create `backend/routers/videos.py` with the video processing endpoint.

**Create `backend/routers/videos.py`:**
```python
"""
Video processing API endpoints.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional

from models.schemas import (
    VideoProcessRequest, 
    VideoProcessResponse, 
    Trip,
    SourceVideo
)
from services.video_downloader import download_video, detect_platform, cleanup_video
from services.gemini_analyzer import analyze_video
from services.location_service import batch_geocode
from services.itinerary_builder import build_trip
from storage.local_storage import save_trip

router = APIRouter()


@router.post("/process", response_model=VideoProcessResponse)
async def process_video(request: VideoProcessRequest):
    """
    Process a video URL and generate a travel itinerary.
    
    This endpoint:
    1. Downloads the video
    2. Analyzes it with Gemini AI
    3. Geocodes extracted locations
    4. Builds an itinerary
    5. Saves and returns the trip
    """
    url = request.url
    platform = request.platform or detect_platform(url)
    
    if platform == "unknown":
        raise HTTPException(
            status_code=400,
            detail="Unsupported platform. Please use TikTok, YouTube, Douyin, or Rednote URLs."
        )
    
    # Step 1: Download video
    print(f"Downloading video from {platform}...")
    download_result = download_video(url)
    
    if not download_result.success:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to download video: {download_result.error}"
        )
    
    try:
        # Step 2: Analyze with Gemini
        print("Analyzing video with Gemini...")
        analysis = analyze_video(download_result.video_path)
        
        if not analysis:
            raise HTTPException(
                status_code=500,
                detail="Failed to analyze video content"
            )
        
        if not analysis.locations:
            raise HTTPException(
                status_code=400,
                detail="No locations found in video. Try a different travel video."
            )
        
        # Step 3: Geocode locations
        print(f"Geocoding {len(analysis.locations)} locations...")
        location_names = [loc.name for loc in analysis.locations]
        geo_results = await batch_geocode(
            location_names, 
            city=analysis.city, 
            country=analysis.country
        )
        
        # Step 4: Build itinerary
        print("Building itinerary...")
        source_video = SourceVideo(
            platform=platform,
            url=url,
            title=download_result.title or "Untitled Video",
            thumbnail=download_result.thumbnail_url
        )
        
        trip = build_trip(analysis, geo_results, source_video)
        
        # Step 5: Save trip
        save_trip(trip)
        
        return VideoProcessResponse(
            status="success",
            trip_id=trip.trip_id,
            trip=trip,
            message=f"Successfully extracted {len(analysis.locations)} locations from video"
        )
        
    finally:
        # Clean up downloaded video
        if download_result.video_path:
            cleanup_video(download_result.video_path)


@router.get("/platforms")
async def get_supported_platforms():
    """Get list of supported video platforms."""
    return {
        "platforms": [
            {"id": "tiktok", "name": "TikTok", "icon": "📱"},
            {"id": "youtube", "name": "YouTube", "icon": "▶️"},
            {"id": "douyin", "name": "Douyin", "icon": "🎵"},
            {"id": "rednote", "name": "Rednote", "icon": "📕"},
        ]
    }
```

**Verification:**
```bash
cd backend
python -c "from routers.videos import router; print('Videos router OK')"
```

**Done when:**
- [ ] `backend/routers/videos.py` exists
- [ ] POST `/api/videos/process` endpoint works

**Commit message:** `feat: 2.2 - Videos router with process endpoint`

---

#### Task 2.3: Trips Router
- [ ] **Status**: Not started

**What to do:**
Create `backend/routers/trips.py` with trip retrieval and chat endpoints.

**Create `backend/routers/trips.py`:**
```python
"""
Trip management API endpoints.
"""
from fastapi import APIRouter, HTTPException
from typing import List

from models.schemas import Trip, ChatRequest, ChatResponse, ChatMessage
from storage.local_storage import get_trip, list_trips, delete_trip

router = APIRouter()


@router.get("/", response_model=List[Trip])
async def get_all_trips():
    """Get all saved trips."""
    return list_trips()


@router.get("/{trip_id}", response_model=Trip)
async def get_trip_by_id(trip_id: str):
    """Get a specific trip by ID."""
    trip = get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip


@router.delete("/{trip_id}")
async def delete_trip_by_id(trip_id: str):
    """Delete a trip."""
    if delete_trip(trip_id):
        return {"status": "deleted", "trip_id": trip_id}
    raise HTTPException(status_code=404, detail="Trip not found")


@router.post("/{trip_id}/chat", response_model=ChatResponse)
async def chat_with_trip(trip_id: str, request: ChatRequest):
    """
    Chat with AI about a trip.
    
    This is a simplified implementation that returns mock responses.
    Full implementation would use Gemini for contextual responses.
    """
    trip = get_trip(trip_id)
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")
    
    user_message = request.message.lower()
    
    # Simple keyword-based responses (placeholder for full AI implementation)
    if any(word in user_message for word in ["cheaper", "budget", "affordable"]):
        response = ChatMessage(
            type="agent",
            content=f"I'll look for more budget-friendly options in {trip.title}! 💰 Would you like me to find alternative accommodations or dining spots?"
        )
    elif any(word in user_message for word in ["add", "include", "also"]):
        response = ChatMessage(
            type="agent",
            content="I can help you add more places! What type of activity are you looking for? (Food, Art, Nature, Culture, Shopping, Nightlife)"
        )
    elif any(word in user_message for word in ["remove", "delete", "skip"]):
        response = ChatMessage(
            type="agent",
            content="Sure! Which location would you like to remove from your itinerary?"
        )
    else:
        response = ChatMessage(
            type="agent",
            content=f"I'm here to help you customize your {trip.title} trip! You can ask me to add places, find budget options, or adjust the schedule. What would you like to change?"
        )
    
    return ChatResponse(message=response)
```

**Verification:**
```bash
cd backend
python -c "from routers.trips import router; print('Trips router OK')"
```

**Done when:**
- [ ] `backend/routers/trips.py` exists
- [ ] GET `/api/trips/{trip_id}` works
- [ ] Basic chat endpoint responds

**Commit message:** `feat: 2.3 - Trips router with chat endpoint`

---

#### Task 2.4: API Integration Test
- [ ] **Status**: Not started

**What to do:**
Create integration test and verify the full API works end-to-end.

**Create `backend/tests/test_api.py`:**
```python
"""
API integration tests.
"""
import pytest
from fastapi.testclient import TestClient
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import app


client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints."""
    
    def test_root(self):
        response = client.get("/")
        assert response.status_code == 200
        assert response.json()["status"] == "healthy"
    
    def test_health(self):
        response = client.get("/health")
        assert response.status_code == 200


class TestVideoEndpoints:
    """Test video processing endpoints."""
    
    def test_get_platforms(self):
        response = client.get("/api/videos/platforms")
        assert response.status_code == 200
        assert "platforms" in response.json()
    
    @pytest.mark.slow
    @pytest.mark.api
    def test_process_short_video(self):
        """Test processing the 25-second TikTok video."""
        response = client.post(
            "/api/videos/process",
            json={"url": "https://www.tiktok.com/@roadynz/video/7440193649578659090"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["trip_id"] is not None
        assert data["trip"] is not None
        assert len(data["trip"]["days"]) > 0


class TestTripEndpoints:
    """Test trip management endpoints."""
    
    def test_list_trips(self):
        response = client.get("/api/trips/")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_nonexistent_trip(self):
        response = client.get("/api/trips/nonexistent123")
        assert response.status_code == 404
```

**Verification:**
```bash
cd backend

# Start the server in background
uvicorn main:app --port 8000 &

# Wait for startup
sleep 3

# Test health endpoint
curl http://localhost:8000/health

# Test platforms endpoint
curl http://localhost:8000/api/videos/platforms

# Kill server
pkill -f "uvicorn main:app"

# Run pytest
python -m pytest tests/test_api.py -v -m "not slow"
```

**Done when:**
- [ ] `backend/tests/test_api.py` exists
- [ ] Health endpoints return 200
- [ ] Server starts without errors

**Commit message:** `feat: 2.4 - API integration tests`

---

### PHASE 3: Frontend Integration

#### Task 3.1: API Client Service
- [ ] **Status**: Not started

**What to do:**
Create `frontend/src/services/api.ts` to communicate with the backend.

**Create `frontend/src/services/api.ts`:**
```typescript
/**
 * API client for VACAY backend.
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export interface ApiError {
  detail: string;
}

/**
 * Process a video URL and get back a trip itinerary.
 */
export async function processVideoUrl(url: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/videos/process`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ url }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to process video');
  }

  return response.json();
}

/**
 * Get a trip by ID.
 */
export async function getTrip(tripId: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}`);

  if (!response.ok) {
    throw new Error('Trip not found');
  }

  return response.json();
}

/**
 * Get all trips.
 */
export async function getAllTrips(): Promise<any[]> {
  const response = await fetch(`${API_BASE_URL}/api/trips/`);

  if (!response.ok) {
    throw new Error('Failed to fetch trips');
  }

  return response.json();
}

/**
 * Send a chat message about a trip.
 */
export async function sendChatMessage(tripId: string, message: string): Promise<any> {
  const response = await fetch(`${API_BASE_URL}/api/trips/${tripId}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ message }),
  });

  if (!response.ok) {
    throw new Error('Failed to send message');
  }

  return response.json();
}

/**
 * Health check.
 */
export async function checkHealth(): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/health`);
    return response.ok;
  } catch {
    return false;
  }
}
```

**Add to `frontend/.env.local` (create if doesn't exist):**
```
VITE_API_URL=http://localhost:8000
```

**Verification:**
```bash
cd frontend
cat src/services/api.ts
# Should show the API client code
```

**Done when:**
- [ ] `frontend/src/services/api.ts` exists
- [ ] All API methods typed and exported

**Commit message:** `feat: 3.1 - Frontend API client service`

---

#### Task 3.2: Update AddUrlModal
- [ ] **Status**: Not started

**What to do:**
Modify `frontend/src/components/trip/AddUrlModal.tsx` to call the real backend API.

**Key changes:**
1. Import the API client
2. Replace simulated processing with real API call
3. Add proper error handling with toast notifications
4. Update context with real trip data on success

**See current file first, then apply changes.**

**Done when:**
- [ ] AddUrlModal calls `processVideoUrl()` from API client
- [ ] Shows loading state during processing
- [ ] Shows error toast on failure
- [ ] Updates TripContext with real data on success

**Commit message:** `feat: 3.2 - Connect AddUrlModal to backend API`

---

#### Task 3.3: Update TripContext
- [ ] **Status**: Not started

**What to do:**
Modify `frontend/src/contexts/TripContext.tsx` to:
1. Support loading trip from API
2. Add `setTrip` function to update with real data
3. Connect chat to real API

**Done when:**
- [ ] TripContext has `setTrip(trip)` function
- [ ] Chat calls real API
- [ ] Loading states handled

**Commit message:** `feat: 3.3 - Connect TripContext to backend API`

---

#### Task 3.4: Mapbox Integration
- [ ] **Status**: Not started

**What to do:**
Replace the placeholder map in `frontend/src/components/trip/MapView.tsx` with real Mapbox GL JS.

**Install Mapbox:**
```bash
cd frontend
npm install mapbox-gl @types/mapbox-gl
```

**Key changes:**
1. Initialize Mapbox with access token from env
2. Add markers at POI coordinates
3. Fly to POI on selection
4. Draw route lines between POIs

**Done when:**
- [ ] Real Mapbox map renders
- [ ] POI markers visible at correct locations
- [ ] Map flies to selected POI
- [ ] Route lines connect POIs in order

**Commit message:** `feat: 3.4 - Real Mapbox integration`

---

### PHASE 4: Testing & Polish

#### Task 4.1: End-to-End Test
- [ ] **Status**: Not started

**What to do:**
Test the complete flow with all 4 sample TikTok URLs.

**Test each URL:**
1. 25-second video - should complete in ~30 seconds
2. Restaurant video - should identify Food category
3. Photo slides - should handle images
4. 2.5-minute video - should extract multiple locations

**Done when:**
- [ ] All 4 sample URLs process successfully
- [ ] Each returns at least 1 POI with valid coordinates
- [ ] Frontend displays results correctly

**Commit message:** `test: 4.1 - End-to-end test with sample URLs`

---

#### Task 4.2: Error Handling & Polish
- [ ] **Status**: Not started

**What to do:**
1. Add proper error messages throughout
2. Add loading skeletons
3. Handle edge cases (empty results, API down, etc.)

**Done when:**
- [ ] All errors show user-friendly messages
- [ ] Loading states are smooth
- [ ] App doesn't crash on errors

**Commit message:** `fix: 4.2 - Error handling and polish`

---

## 📝 Git Workflow

After completing each task:

1. **Stage changes:**
   ```bash
   git add -A
   ```

2. **Commit with the specified message:**
   ```bash
   git commit -m "feat: X.X - Description"
   ```

3. **Push to GitHub:**
   ```bash
   git push origin main
   ```

4. **Update PROGRESS.md** with:
   - What was implemented
   - Files changed
   - Any learnings or gotchas
   - Check off the task in this BRD

---

## 🛠️ Running the Application

### Backend
```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/VACAY
source venv/bin/activate
cd backend
uvicorn main:app --reload --port 8000
```

### Frontend
```bash
cd /Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/frontend
npm run dev
```

### Run Tests
```bash
# Backend tests
cd backend
python -m pytest tests/ -v

# Frontend tests  
cd frontend
npm test
```

---

## ✅ Success Criteria

MVP is complete when:
1. All Phase 1-3 tasks checked off
2. All 4 sample TikToks process successfully
3. POIs display on real Mapbox map
4. No hardcoded mock data in production flow
5. Processing completes in under 60 seconds for short videos
