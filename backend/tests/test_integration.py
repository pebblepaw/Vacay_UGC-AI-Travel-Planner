"""
Simple test to verify backend services work.
Run with: python backend/tests/test_integration.py
"""
import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.models.schemas import GeminiAnalysisResult, POI
from backend.services.itinerary_builder import itinerary_builder


async def test_itinerary_builder():
    """Test that we can build an itinerary from mock data."""
    print("Testing itinerary builder...")
    
    # Mock video data
    video_data = [
        {
            'url': 'https://tiktok.com/@test/video1',
            'title': 'Amazing Tokyo Ramen',
            'platform': 'tiktok'
        }
    ]
    
    # Mock Gemini analysis result
    analysis_results = [
        GeminiAnalysisResult(
            locations=[
                {
                    'name': 'TeamLab Borderless',
                    'type': 'Art',
                    'description': 'Amazing digital art museum',
                    'mentioned_time': '0:15'
                },
                {
                    'name': 'Ichiran Ramen',
                    'type': 'Food',
                    'description': 'Best tonkotsu ramen in Tokyo',
                    'mentioned_time': '1:30'
                }
            ],
            activities=['eating', 'sightseeing', 'photography'],
            vibes=['authentic', 'trendy', 'instagram-worthy'],
            metadata={'city': 'Tokyo', 'confidence': 'high'}
        )
    ]
    
    # Build itinerary
    trip = await itinerary_builder.build_itinerary(
        video_data,
        analysis_results,
        "Test Tokyo Trip"
    )
    
    # Verify
    assert trip.title == "Test Tokyo Trip"
    assert len(trip.source_videos) == 1
    assert len(trip.days) > 0
    assert trip.accommodation is not None
    
    print(f"✅ Created trip: {trip.trip_id}")
    print(f"   Title: {trip.title}")
    print(f"   Days: {len(trip.days)}")
    print(f"   Total POIs: {sum(len(day.pois) for day in trip.days)}")
    print(f"   Accommodation: {trip.accommodation.name}")
    
    return trip


async def main():
    print("\n=== VACAY Backend Integration Test ===\n")
    
    try:
        trip = await test_itinerary_builder()
        print("\n✅ All tests passed!")
        return True
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(main())
    sys.exit(0 if success else 1)
