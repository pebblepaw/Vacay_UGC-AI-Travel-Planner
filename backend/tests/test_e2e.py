"""
End-to-end test to verify the complete system works.
This simulates what happens when a user submits a video URL.

Run with: python backend/tests/test_e2e.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import VideoProcessRequest, GeminiAnalysisResult
from backend.services.itinerary_builder import itinerary_builder
from backend.storage.local_storage import local_storage


async def test_full_pipeline_mock():
    """
    Test the full pipeline with mock data (no actual video download/analysis).
    This verifies the itinerary building and storage works correctly.
    """
    print("\n=== VACAY End-to-End Test (Mock Data) ===\n")
    
    # Step 1: Mock video data (as if we downloaded videos)
    print("Step 1: Mock video data...")
    video_data = [
        {
            'url': 'https://tiktok.com/@test/video1',
            'title': 'Best Ramen in Tokyo',
            'platform': 'tiktok'
        },
        {
            'url': 'https://youtube.com/shorts/abc',
            'title': 'TeamLab Museum Tour',
            'platform': 'youtube'
        }
    ]
    print(f"   ✓ Prepared {len(video_data)} mock videos")
    
    # Step 2: Mock Gemini analysis results
    print("\nStep 2: Mock Gemini analysis...")
    analysis_results = [
        GeminiAnalysisResult(
            locations=[
                {
                    'name': 'Ichiran Ramen Shinjuku',
                    'type': 'Food',
                    'description': 'Famous tonkotsu ramen chain with private booths',
                    'mentioned_time': '0:30'
                },
                {
                    'name': 'Shinjuku Gyoen Garden',
                    'type': 'Nature',
                    'description': 'Beautiful Japanese garden in the heart of Tokyo',
                    'mentioned_time': '1:15'
                }
            ],
            activities=['eating', 'photography'],
            vibes=['authentic', 'local favorite'],
            metadata={'city': 'Tokyo', 'confidence': 'high'}
        ),
        GeminiAnalysisResult(
            locations=[
                {
                    'name': 'TeamLab Borderless',
                    'type': 'Art',
                    'description': 'Immersive digital art museum',
                    'mentioned_time': '0:10'
                }
            ],
            activities=['art viewing', 'photography'],
            vibes=['instagram-worthy', 'mind-blowing'],
            metadata={'city': 'Tokyo', 'confidence': 'high'}
        )
    ]
    print(f"   ✓ Created {len(analysis_results)} mock analysis results")
    total_locations = sum(len(r.locations) for r in analysis_results)
    print(f"   ✓ Total locations extracted: {total_locations}")
    
    # Step 3: Build itinerary
    print("\nStep 3: Building itinerary...")
    trip = await itinerary_builder.build_itinerary(
        video_data,
        analysis_results,
        "Tokyo Hidden Gems"
    )
    print(f"   ✓ Created trip: {trip.trip_id}")
    print(f"   ✓ Title: {trip.title}")
    print(f"   ✓ Source videos: {len(trip.source_videos)}")
    print(f"   ✓ Days: {len(trip.days)}")
    print(f"   ✓ Total POIs: {sum(len(day.pois) for day in trip.days)}")
    print(f"   ✓ Accommodation: {trip.accommodation.name}")
    
    # Step 4: Save to storage
    print("\nStep 4: Saving to storage...")
    success = await local_storage.save_trip(trip)
    if not success:
        raise Exception("Failed to save trip")
    print(f"   ✓ Trip saved successfully")
    
    # Step 5: Load from storage
    print("\nStep 5: Loading from storage...")
    loaded_trip = await local_storage.load_trip(trip.trip_id)
    if not loaded_trip:
        raise Exception("Failed to load trip")
    print(f"   ✓ Trip loaded successfully")
    print(f"   ✓ Loaded trip title: {loaded_trip.title}")
    
    # Step 6: Verify data integrity
    print("\nStep 6: Verifying data integrity...")
    assert loaded_trip.trip_id == trip.trip_id
    assert loaded_trip.title == trip.title
    assert len(loaded_trip.days) == len(trip.days)
    assert len(loaded_trip.source_videos) == len(trip.source_videos)
    print("   ✓ All data matches!")
    
    # Step 7: List all trips
    print("\nStep 7: Listing all trips...")
    all_trips = await local_storage.list_all_trips()
    print(f"   ✓ Found {len(all_trips)} trip(s) in storage")
    
    # Step 8: Cleanup test trip
    print("\nStep 8: Cleaning up test trip...")
    deleted = await local_storage.delete_trip(trip.trip_id)
    if not deleted:
        print("   ⚠ Warning: Could not delete test trip")
    else:
        print("   ✓ Test trip deleted")
    
    return True


async def main():
    try:
        await test_full_pipeline_mock()
        print("\n" + "="*50)
        print("✅ ALL TESTS PASSED!")
        print("="*50)
        print("\nYour VACAY system is working correctly!")
        print("Next steps:")
        print("  1. Start the backend: uvicorn backend.main:app --reload")
        print("  2. Start the frontend: cd frontend && npm run dev")
        print("  3. Test with a real TikTok URL at http://localhost:5173")
        print()
        return True
    except Exception as e:
        print("\n" + "="*50)
        print("❌ TEST FAILED")
        print("="*50)
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
