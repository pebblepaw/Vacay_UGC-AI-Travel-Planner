"""
VACAY FastAPI Application
Main entry point for the backend API.
"""
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import logging

from backend.config import settings
from backend.routers import videos, trips, chat
from backend.routers import workspaces, telegram
from backend.routers import browser
from backend.agent.graph import close_graph_checkpointer, configure_graph_checkpointer
from backend.storage.supabase_storage import supabase_storage

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)
WORKSPACE_PATH = str(Path.cwd().resolve())
CONFIG_PATH = str(Path(settings.APP_CONFIG_PATH).resolve())

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
        "http://localhost:3001",
        "http://localhost:8080",
        "http://localhost:8081",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Vacay-Workspace", "X-Vacay-Config"],
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1):\d+",
)


@app.middleware("http")
async def add_debug_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Vacay-Workspace"] = WORKSPACE_PATH
    response.headers["X-Vacay-Config"] = CONFIG_PATH
    return response

# Include routers
app.include_router(videos.router)
app.include_router(trips.router)
app.include_router(chat.router)
app.include_router(workspaces.router)
app.include_router(telegram.router)
app.include_router(browser.router)
app.mount("/media", StaticFiles(directory=str(settings.DOWNLOADS_DIR)), name="media")


@app.on_event("startup")
async def startup_event():
    """Seed placeholder trip if the database is empty."""
    logger.info("VACAY workspace: %s", WORKSPACE_PATH)
    logger.info("VACAY config: %s", CONFIG_PATH)
    logger.info("Configuring LangGraph checkpoint storage...")
    configure_graph_checkpointer()
    logger.info("Checking Supabase for existing trips...")
    await supabase_storage.seed_placeholder_if_empty()


@app.on_event("shutdown")
async def shutdown_event():
    close_graph_checkpointer()


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "message": "VACAY API is running",
        "version": "1.0.0",
        "status": "healthy",
        "workspace": WORKSPACE_PATH,
        "config_path": CONFIG_PATH,
    }


@app.get("/api/health")
async def health():
    """Detailed health check."""
    return {
        "status": "healthy",
        "services": {
            "api": "ok",
            "storage": "ok"
        },
        "workspace": WORKSPACE_PATH,
        "config_path": CONFIG_PATH,
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
