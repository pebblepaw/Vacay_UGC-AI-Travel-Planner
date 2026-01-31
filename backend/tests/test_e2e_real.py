"""
End-to-end test using REAL external APIs (Gemini, Tavily).
WARNING: This costs money/credits!

Run with: python backend/tests/test_e2e_real.py
"""
import asyncio
import sys
import logging
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import VideoProcessRequest
from backend.storage.local_storage import local_storage

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def test_real_pipeline():
    """
    Test the full video processing pipeline with a real TikTok video.
    """
    print("\n=== VACAY Real E2E Test (USING CREDITS) ===\n")
    
    # Use the 25-second TikTok video from sample inputs
    # "New Zealand Road Trip"
    test_url = "https://www.tiktok.com/@roadynz/video/7440193649578659090"
    
    print(f"Testing with URL: {test_url}")
    print("This will:")
    print("  1. Download video (yt-dlp)")
    print("  2. Analyze with Gemini 1.5 Pro")
    print("  3. Geocode with Tavily")
    print("  4. Build Itinerary")
    print("  5. Save to Local Storage")
    
    # NOTE: The actual API expects a list of URLs
    # request = VideoProcessRequest(urls=[test_url], trip_title="E2E Test Trip")
    
    try:
        # We can't call the API endpoint directly easily because of async context and dependencies
        # So we'll simulate the client call or import the logic if possible.
        # Ideally we'd use TestClient but process_video does background tasks which might be tricky in script.
        # Let's use httpx against the running server if it's up, OR use the service functions directly.
        # Using service functions directly gives us better error visibility here without needing server running.
        
        # NOTE: reusing the logic from routers/videos.py manually to avoid FastAPI dependency injection complexity in script
        
        from backend.services.video_downloader import download_video, cleanup_video
        from backend.services.gemini_analyzer import analyze_video
        from backend.services.location_service import batch_geocode
        from backend.services.itinerary_builder import build_trip
        from backend.models.schemas import SourceVideo
        from backend.storage.local_storage import local_storage
        
        # Step 1: Download
        print("\nStep 1: Downloading video...")
        download_result = download_video(test_url)
        if not download_result.success:
            print(f"❌ Download failed: {download_result.error}")
            return False
        print(f"✅ Video downloaded to: {download_result.video_path}")
        print(f"   Title: {download_result.title}")
        
        try:
            # Step 2: Analyze
            print("\nStep 2: Analyzing with Gemini...")
            analysis = analyze_video(download_result.video_path)
            if not analysis:
                print("❌ Gemini analysis failed")
                return False
            
            print(f"✅ Gemini analysis complete")
            print(f"   City: {analysis.city}, Country: {analysis.country}")
            print(f"   Locations found: {len(analysis.locations)}")
            for loc in analysis.locations:
                print(f"     - {loc.name} ({loc.category})")
                
            if not analysis.locations:
                print("❌ No locations found in video")
                return False
                
            # Step 3: Geocode
            print("\nStep 3: Geocoding locations...")
            location_names = [loc.name for loc in analysis.locations]
            geo_results = await batch_geocode(
                location_names, 
                city=analysis.city, 
                country=analysis.country
            )
            print(f"✅ Geocoding complete. Results: {len(geo_results)}")
            for res in geo_results:
                coords = res.coords if res.coords else "Not found"
                print(f"     - {res.name}: {coords}")
                
            # Step 4: Build Trip
            print("\nStep 4: Building itinerary...")
            source_video = SourceVideo(
                platform="tiktok",
                url=test_url,
                title=download_result.title or "Test Video",
                thumbnail=download_result.thumbnail_url
            )
            
            trip = build_trip(analysis, geo_results, source_video)
            print(f"✅ Trip built: {trip.title} (ID: {trip.trip_id})")
            print(f"   Days: {len(trip.days)}")
            
            # Step 5: Save
            print("\nStep 5: Saving to storage...")
            success = await local_storage.save_trip(trip)
            if success:
                print(f"✅ Trip saved successfully")
            else:
                print(f"❌ Failed to save trip")
                return False
                
            # Cleanup
            print("\nStep 6: Cleaning up...")
            from backend.services.video_downloader import cleanup_video
            cleanup_video(download_result.video_path)
            print("✅ Video file deleted")
            
            return True
            
        finally:
            if download_result.video_path and download_result.video_path.exists():
                cleanup_video(download_result.video_path)

    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_real_pipeline())
    sys.exit(0 if success else 1)
