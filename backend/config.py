"""
Configuration module for backend services.
Loads environment variables and provides typed settings.
"""
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

# Get project root (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Keys
    GEMINI_API_KEY: str
    TAVLY_API: str
    MAPBOX_PUBLIC: str
    MAPBOX_SECRET: str
    GEMINI_MODEL: str = "gemini-2.0-flash"
    
    # Optional settings with defaults
    DEBUG: bool = True
    MAX_VIDEO_SIZE_MB: int = 500
    DOWNLOAD_TIMEOUT_SECONDS: int = 300
    
    # Paths
    DOWNLOADS_DIR: Path = PROJECT_ROOT / "downloads"
    DATA_DIR: Path = PROJECT_ROOT / "backend" / "data"
    TRIPS_DIR: Path = PROJECT_ROOT / "backend" / "data" / "trips"
    
    class Config:
        # Load from .env in project root (parent directory)
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields in .env (like SUPABASE keys for Phase 2)


# Singleton instance
settings = Settings()

# Create required directories on import
settings.DOWNLOADS_DIR.mkdir(exist_ok=True)
settings.DATA_DIR.mkdir(exist_ok=True)
settings.TRIPS_DIR.mkdir(exist_ok=True)
