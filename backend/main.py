"""
VACAY FastAPI Application
Main entry point for the backend API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging

from backend.routers import videos, trips, chat
from backend.storage.supabase_storage import supabase_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="VACAY API",
    description="AI-powered travel itinerary planner from UGC videos",
    version="1.0.0"
)

# CORS middleware - allow frontend to connect
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(videos.router)
app.include_router(trips.router)
app.include_router(chat.router)


@app.on_event("startup")
async def startup_event():
    """Seed placeholder trip if the database is empty."""
    logger.info("Checking Supabase for existing trips...")
    await supabase_storage.seed_placeholder_if_empty()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "VACAY API is running",
        "version": "1.0.0",
        "status": "healthy"
    }


@app.get("/api/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok",
            "storage": "ok"
        }
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
