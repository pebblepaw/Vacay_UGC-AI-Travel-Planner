"""
FastAPI routers for video processing endpoints.
Handles video URL submission and processing pipeline.
"""
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
import logging

from backend.models.schemas import VideoProcessRequest, VideoProcessResponse
from backend.services.video_downloader import video_downloader
from backend.services.gemini_analyzer import gemini_analyzer
from backend.services.itinerary_builder import itinerary_builder
from backend.storage.supabase_storage import supabase_storage as storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])


@router.post("/process", response_model=VideoProcessResponse)
async def process_videos(
    request: VideoProcessRequest,
    background_tasks: BackgroundTasks
):
    """
    Process video URLs to create a trip itinerary.
    
    This endpoint:
    1. Downloads videos using yt-dlp
    2. Analyzes them with Gemini to extract locations
    3. Geocodes locations with Tavily
    4. Builds a complete itinerary
    5. Saves to local storage
    
    Returns immediately with trip_id and processing status.
    """
    try:
        logger.info(f"Processing {len(request.urls)} video(s)")
        
        # Step 1: Download all videos
        download_results = await video_downloader.download_multiple(request.urls)
        
        # Check for failures
        successful_downloads = [r for r in download_results if r.get('success')]
        if not successful_downloads:
            raise HTTPException(
                status_code=400,
                detail="Failed to download any videos. Check URLs and try again."
            )
        
        logger.info(f"Downloaded {len(successful_downloads)}/{len(request.urls)} videos")
        
        # Step 2: Analyze videos with Gemini
        video_data_for_analysis = [
            {
                'file_path': r['file_path'],
                'title': r['title']
            }
            for r in successful_downloads
        ]
        
        analysis_results = await gemini_analyzer.analyze_multiple_videos(video_data_for_analysis)
        
        logger.info(f"Analyzed {len(analysis_results)} videos with Gemini")
        
        # Step 3: Build itinerary
        video_metadata = [
            {
                'url': request.urls[i],
                'title': r['title'],
                'platform': r['platform']
            }
            for i, r in enumerate(successful_downloads)
        ]
        
        trip = await itinerary_builder.build_itinerary(
            video_metadata,
            analysis_results,
            request.trip_title
        )
        
        logger.info(f"Built itinerary: {trip.trip_id} - {trip.title}")
        
        # Step 4: Save trip to storage
        saved = await storage.save_trip(trip)
        
        if not saved:
            raise HTTPException(
                status_code=500,
                detail="Failed to save trip to storage"
            )
        
        # Step 5: Clean up downloaded videos in background
        for result in successful_downloads:
            file_path = result.get('file_path')
            if file_path:
                background_tasks.add_task(video_downloader.cleanup_video, file_path)
        
        # Return success response
        return VideoProcessResponse(
            trip_id=trip.trip_id,
            status="completed",
            message=f"Successfully created trip '{trip.title}' from {len(successful_downloads)} video(s)",
            trip=trip
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing videos: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )
