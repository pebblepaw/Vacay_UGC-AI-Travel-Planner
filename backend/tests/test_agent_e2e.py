"""
End-to-end tests for the LangGraph agent.

These tests use REAL LLM calls (DashScope/Qwen by default) and verify the full pipeline:
orchestrator → agent → tools → critic → response

Run with: pytest backend/tests/test_agent_e2e.py -v -s
The -s flag shows print output (useful for seeing agent responses).

NOTE: These require DASHSCOPE_API_KEY in .env when AGENT_LLM_PROVIDER=aliyun,
and cost real API credits.
"""

import pytest
import copy
from langchain_core.messages import HumanMessage
from backend.agent.graph import app
from backend.models.schemas import Trip, Day, POI, SourceVideo, Accommodation


# ── Test fixture: a simple 2-day trip ──

@pytest.fixture
def sample_trip() -> Trip:
    """A minimal trip for testing."""
    return Trip(
        trip_id="test_trip_001",
        title="Test Trip to Tokyo",
        source_videos=[
            SourceVideo(platform="tiktok", url="https://example.com", title="Test")
        ],
        days=[
            Day(
                day_number=1,
                date="2024-04-15",
                pois=[
                    POI(
                        id="poi_1",
                        name="TeamLab Borderless",
                        category="Art",
                        coords=(139.7834, 35.6267),
                        img="https://example.com/img1.jpg",
                        time_slot="10:00 - 13:00",
                        vibe="Digital art museum",
                        priority="high",
                        intensity="normal",
                        visit_duration=180,
                    ),
                    POI(
                        id="poi_2",
                        name="Shinjuku Ramen Shop",
                        category="Food",
                        coords=(139.71, 35.685),
                        img="https://example.com/img2.jpg",
                        time_slot="13:30 - 14:30",
                        vibe="Famous tonkotsu ramen",
                        priority="normal",
                        intensity="normal",
                        visit_duration=60,
                    ),
                    POI(
                        id="poi_3",
                        name="Shinjuku Gyoen Garden",
                        category="Nature",
                        coords=(139.71, 35.6852),
                        img="https://example.com/img3.jpg",
                        time_slot="15:00 - 17:00",
                        vibe="Beautiful Japanese garden",
                        priority="low",
                        intensity="low",
                        visit_duration=120,
                    ),
                ],
            ),
            Day(
                day_number=2,
                date="2024-04-16",
                pois=[
                    POI(
                        id="poi_4",
                        name="Harajuku Takeshita Street",
                        category="Shopping",
                        coords=(139.7028, 35.6716),
                        img="https://example.com/img4.jpg",
                        time_slot="10:00 - 12:00",
                        vibe="Kawaii culture central",
                        priority="normal",
                        intensity="normal",
                        visit_duration=120,
                    ),
                    POI(
                        id="poi_5",
                        name="Meiji Shrine",
                        category="Culture",
                        coords=(139.6993, 35.6764),
                        img="https://example.com/img5.jpg",
                        time_slot="13:00 - 15:00",
                        vibe="Peaceful Shinto shrine",
                        priority="high",
                        intensity="low",
                        visit_duration=120,
                    ),
                ],
            ),
        ],
        accommodation=Accommodation(
            name="Test Hotel",
            price_per_night=150.0,
            status="Test",
            img="https://example.com/hotel.jpg",
            coords=(139.7, 35.68),
        ),
    )


# ── Helper ──

async def run_agent(message: str, trip: Trip) -> dict:
    """Run the agent with a message and trip, return final state."""
    initial_state = {
        "messages": [HumanMessage(content=message)],
        "trip": trip,
        "next_node": None,
        "plan": None,
        "current_step": 0,
        "critique": "",
        "iteration_count": 0,
        "last_agent": None,
        "pending_changes": None,
    }
    return await app.ainvoke(initial_state)


# ============================================================================
# TESTS
# ============================================================================

class TestChitChat:
    """Test that chitchat routes correctly."""

    @pytest.mark.asyncio
    async def test_greeting(self, sample_trip):
        result = await run_agent("Hello!", sample_trip)
        final_msg = result["messages"][-1].content
        assert final_msg  # Should have some response
        print(f"Chitchat response: {final_msg}")


class TestDeletePOI:
    """Test deleting POIs."""

    @pytest.mark.asyncio
    async def test_delete_by_name(self, sample_trip):
        result = await run_agent("Remove the ramen shop", sample_trip)
        trip = result["trip"]

        # poi_2 should be gone
        all_poi_ids = [p.id for d in trip.days for p in d.pois]
        assert "poi_2" not in all_poi_ids, f"poi_2 should be deleted. Remaining: {all_poi_ids}"
        print(f"Delete response: {result['messages'][-1].content}")


class TestMovePOI:
    """Test moving POIs between days."""

    @pytest.mark.asyncio
    async def test_move_to_different_day(self, sample_trip):
        result = await run_agent("Move the garden to Day 2", sample_trip)
        trip = result["trip"]

        # poi_3 should be on Day 2 now
        day2_ids = [p.id for p in trip.days[1].pois]
        assert "poi_3" in day2_ids, f"poi_3 should be on Day 2. Day 2 POIs: {day2_ids}"
        print(f"Move response: {result['messages'][-1].content}")


class TestOptimize:
    """Test trip optimization."""

    @pytest.mark.asyncio
    async def test_optimize_trip(self, sample_trip):
        result = await run_agent("Optimize my trip route", sample_trip)
        trip = result["trip"]

        # Trip should still have all POIs (just reordered)
        all_pois = [p.id for d in trip.days for p in d.pois]
        assert len(all_pois) == 5, f"Should still have 5 POIs after optimization. Got: {len(all_pois)}"
        print(f"Optimize response: {result['messages'][-1].content}")


class TestReplanDay:
    """Test replanning a single day."""

    @pytest.mark.asyncio
    async def test_replan_day(self, sample_trip):
        result = await run_agent("Replan Day 1 for a better schedule", sample_trip)
        trip = result["trip"]

        # Day 1 should still have 3 POIs
        assert len(trip.days[0].pois) == 3
        print(f"Replan response: {result['messages'][-1].content}")
        print(f"New order: {[p.name for p in trip.days[0].pois]}")