"""
Configuration module for backend services.
Loads environment variables and provides typed settings.
"""
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings
from pathlib import Path
from typing import Optional

# Get project root (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # API Keys
    GEMINI_API_KEY: str
    DASHSCOPE_API_KEY: Optional[str] = None
    TAVLY_API: str
    MAPBOX_PUBLIC: str
    MAPBOX_SECRET: str
    DASHSCOPE_BASE_URL: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    APP_CONFIG_PATH: Path = PROJECT_ROOT / "config" / "config.yaml"
    BOOKING_STRICT_REAL_TRIP: bool = True
    SECRET_KEY: str = "vacayclaw-dev-secret"

    # Supabase
    SUPABASE_PROJECT_URL: str
    SUPABASE_SECRET_KEY: str
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SERVICE_ROLE"),
    )
    LANGGRAPH_CHECKPOINT_URL: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices(
            "LANGGRAPH_CHECKPOINT_URL",
            "SUPABASE_SESSION_POOLER",
            "SUPBASE_CONNECTION_STRING",
        ),
    )

    # Optional settings with defaults
    DEBUG: str = "true"
    MAX_VIDEO_SIZE_MB: int = 500
    DOWNLOAD_TIMEOUT_SECONDS: int = 300
    TELEGRAM_WEBHOOK_SECRET: Optional[str] = None
    TELEGRAM_BOT_TOKEN: Optional[str] = None
    PUBLIC_WEB_BASE_URL: str = "http://localhost:5173"
    PUBLIC_API_BASE_URL: str = "http://127.0.0.1:8000"

    # Paths
    DOWNLOADS_DIR: Path = PROJECT_ROOT / "downloads"
    DATA_DIR: Path = PROJECT_ROOT / "backend" / "data"
    TRIPS_DIR: Path = PROJECT_ROOT / "backend" / "data" / "trips"

    class Config:
        # Load from .env in project root (parent directory)
        env_file = str(PROJECT_ROOT / ".env")
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"


# Singleton instance
settings = Settings()

# Create required directories on import
settings.DOWNLOADS_DIR.mkdir(exist_ok=True)
settings.DATA_DIR.mkdir(exist_ok=True)
settings.TRIPS_DIR.mkdir(exist_ok=True)
