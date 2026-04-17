from backend.agent.nodes.travel_tool_executor import _execute_replan_day
from backend.models.schemas import Accommodation, Day, POI, SourceVideo, Trip


def _make_trip_with_lunch() -> Trip:
    return Trip(
        trip_id="trip_replan",
        title="Queenstown Day",
        source_videos=[
            SourceVideo(
                platform="tiktok",
                url="https://www.tiktok.com/@demo/video/1",
                title="Queenstown guide",
            )
        ],
        days=[
            Day(
                day_number=1,
                date="2026-04-20",
                pois=[
                    POI(
                        id="poi_1",
                        name="Lakefront Walk",
                        category="Nature",
                        coords=(168.6626, -45.0312),
                        img="https://example.com/1.jpg",
                        time_slot="09:00 - 10:30",
                        vibe="Scenic lake walk",
                        visit_duration=90,
                    ),
                    POI(
                        id="poi_2",
                        name="Akin",
                        category="Food",
                        coords=(168.6631, -45.0304),
                        img="https://example.com/2.jpg",
                        time_slot="12:00 - 13:30",
                        vibe="Lunch stop",
                        visit_duration=90,
                    ),
                    POI(
                        id="poi_3",
                        name="Skyline Gondola",
                        category="Culture",
                        coords=(168.6480, -45.0240),
                        img="https://example.com/3.jpg",
                        time_slot="14:00 - 15:30",
                        vibe="Afternoon lookout",
                        visit_duration=90,
                    ),
                ],
            )
        ],
        accommodation=Accommodation(
            name="Hotel",
            price_per_night=200,
            status="confirmed",
            img="https://example.com/hotel.jpg",
            coords=(168.6626, -45.0312),
        ),
    )


def test_replan_day_preserves_lunch_window_and_real_clock_times() -> None:
    trip = _make_trip_with_lunch()

    updated_trip, message = _execute_replan_day(trip, 1)

    assert "Replanned Day 1" in message
    lunch_poi = next(poi for poi in updated_trip.days[0].pois if poi.name == "Akin")
    assert lunch_poi.time_slot.startswith("12:")
    assert "26:" not in " ".join(poi.time_slot for poi in updated_trip.days[0].pois)


def test_replan_day_refuses_impossible_schedule_instead_of_emitting_26_hours() -> None:
    trip = _make_trip_with_lunch()
    trip.days[0].pois.extend(
        [
            POI(
                id="poi_4",
                name="Far Stop 1",
                category="Nature",
                coords=(174.7633, -36.8485),
                img="https://example.com/4.jpg",
                time_slot="16:00 - 18:00",
                vibe="Long transfer",
                visit_duration=240,
            ),
            POI(
                id="poi_5",
                name="Far Stop 2",
                category="Nightlife",
                coords=(115.8605, -31.9505),
                img="https://example.com/5.jpg",
                time_slot="19:00 - 21:00",
                vibe="Another city entirely",
                visit_duration=240,
            ),
        ]
    )

    updated_trip, message = _execute_replan_day(trip, 1)

    assert "too packed" in message.lower()
    assert all("26:" not in poi.time_slot for poi in updated_trip.days[0].pois)

