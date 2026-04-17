from backend.agent.nodes.search_agent import build_search_instruction
from backend.models.schemas import Accommodation, Day, POI, SourceVideo, Trip


def make_trip() -> Trip:
    return Trip(
        trip_id="trip_search",
        title="Lake Como Escape",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/123",
                title="Lake Como highlights",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-04-19",
                pois=[
                    POI(
                        id="poi_1",
                        name="Villa del Balbianello",
                        category="Culture",
                        coords=(9.2026, 45.9719),
                        img="https://example.com/1.jpg",
                        time_slot="10:00 - 11:30",
                        vibe="Historic villa on the lake.",
                    ),
                    POI(
                        id="poi_2",
                        name="Bellagio Waterfront",
                        category="Culture",
                        coords=(9.2592, 45.9872),
                        img="https://example.com/2.jpg",
                        time_slot="14:00 - 16:00",
                        vibe="Classic lake promenade.",
                    ),
                ],
            )
        ],
        accommodation=Accommodation(
            name="Grand Hotel",
            price_per_night=320,
            status="confirmed",
            img="https://example.com/hotel.jpg",
            coords=(9.25, 45.98),
        ),
    )


def test_build_search_instruction_anchors_lunch_to_noon_neighbors() -> None:
    instruction = build_search_instruction(
        "Find me a lunch place",
        trip=make_trip(),
    )

    assert "Day 1" in instruction
    assert "Villa del Balbianello" in instruction
    assert "Bellagio Waterfront" in instruction
    assert "lunch" in instruction.lower()


def test_build_search_instruction_anchors_generic_restaurant_request() -> None:
    instruction = build_search_instruction(
        "Find me a restaurant for this day",
        trip=make_trip(),
    )

    assert "Day 1" in instruction
    assert "Villa del Balbianello" in instruction
    assert "Bellagio Waterfront" in instruction
