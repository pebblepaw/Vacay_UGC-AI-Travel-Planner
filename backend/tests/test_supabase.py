"""
Integration tests for Supabase storage layer.
Tests CRUD operations against the real Supabase instance.
"""
import pytest
import uuid
from backend.storage.supabase_storage import supabase_storage, PLACEHOLDER_TRIP
from backend.models.schemas import Trip


# ── Helpers ──────────────────────────────────────────────────

def _make_test_trip(trip_id: str = None) -> Trip:
    """Create a minimal valid Trip for testing."""
    tid = trip_id or f"test_{uuid.uuid4().hex[:12]}"
    return Trip(**{
        "trip_id": tid,
        "title": f"Test Trip {tid}",
        "source_videos": [
            {"platform": "tiktok", "url": "https://example.com/v", "title": "Test"}
        ],
        "days": [
            {
                "day_number": 1,
                "date": "2025-01-01",
                "pois": [
                    {
                        "id": "poi_test_1",
                        "name": "Test Place",
                        "category": "Food",
                        "coords": [2.3522, 48.8566],
                        "img": "https://example.com/img.jpg",
                        "time_slot": "10:00 - 12:00",
                        "vibe": "Test vibe",
                        "priority": "normal",
                        "intensity": "normal",
                        "visit_duration": 60,
                    }
                ],
            }
        ],
        "accommodation": {
            "name": "Test Hotel",
            "price_per_night": 100.0,
            "status": "Test",
            "img": "https://example.com/hotel.jpg",
            "coords": [2.35, 48.85],
        },
    })


# ── Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_save_and_load_trip():
    """Save a trip, then load it back and verify fields match."""
    trip = _make_test_trip()
    saved = await supabase_storage.save_trip(trip)
    assert saved is True

    loaded = await supabase_storage.load_trip(trip.trip_id)
    assert loaded is not None
    assert loaded.trip_id == trip.trip_id
    assert loaded.title == trip.title
    assert len(loaded.days) == 1
    assert loaded.days[0].pois[0].name == "Test Place"

    # Cleanup
    await supabase_storage.delete_trip(trip.trip_id)


@pytest.mark.asyncio
async def test_load_nonexistent_trip():
    """Loading a trip that doesn't exist returns None."""
    result = await supabase_storage.load_trip("nonexistent_trip_xyz")
    assert result is None


@pytest.mark.asyncio
async def test_upsert_overwrites():
    """Saving a trip with the same ID overwrites the previous data."""
    trip = _make_test_trip()
    await supabase_storage.save_trip(trip)

    # Modify and re-save
    trip.title = "Updated Title"
    await supabase_storage.save_trip(trip)

    loaded = await supabase_storage.load_trip(trip.trip_id)
    assert loaded is not None
    assert loaded.title == "Updated Title"

    # Cleanup
    await supabase_storage.delete_trip(trip.trip_id)


@pytest.mark.asyncio
async def test_list_trips():
    """List returns all trips, most recent first."""
    trips = await supabase_storage.list_all_trips()
    assert isinstance(trips, list)
    # Should work even if empty — just returns []


@pytest.mark.asyncio
async def test_delete_trip():
    """Deleting a trip removes it from the database."""
    trip = _make_test_trip()
    await supabase_storage.save_trip(trip)

    deleted = await supabase_storage.delete_trip(trip.trip_id)
    assert deleted is True

    exists = await supabase_storage.trip_exists(trip.trip_id)
    assert exists is False


@pytest.mark.asyncio
async def test_trip_exists():
    """trip_exists returns True for saved trips, False otherwise."""
    trip = _make_test_trip()
    await supabase_storage.save_trip(trip)
    assert await supabase_storage.trip_exists(trip.trip_id) is True

    await supabase_storage.delete_trip(trip.trip_id)
    assert await supabase_storage.trip_exists(trip.trip_id) is False


@pytest.mark.asyncio
async def test_placeholder_is_valid_trip():
    """The PLACEHOLDER_TRIP dict can be parsed into a valid Trip object."""
    trip = Trip(**PLACEHOLDER_TRIP)
    assert trip.trip_id == "placeholder-welcome"
    assert len(trip.days) == 1
    assert len(trip.days[0].pois) == 3
    assert trip.days[0].pois[0].name == "The Eiffel Tower"


@pytest.mark.asyncio
async def test_seed_placeholder_if_empty():
    """seed_placeholder_if_empty inserts the placeholder when DB is empty."""
    # This test just verifies the method doesn't crash.
    # The actual seeding logic is: if 0 rows → insert placeholder.
    # Since we can't easily empty the DB in a test, just call it
    # and verify no exception is raised.
    await supabase_storage.seed_placeholder_if_empty()
    # After seeding, at least 1 trip should exist
    trips = await supabase_storage.list_all_trips()
    assert len(trips) >= 1
