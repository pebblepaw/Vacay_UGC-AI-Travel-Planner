from backend.agent.nodes.booking_agent import _extract_route


def test_extract_route_stops_before_date_clause() -> None:
    origin, destination = _extract_route(
        "Find flights on trip.com from Tokyo Haneda to Shanghai Pudong on 2026-05-10 for 1 adult"
    )

    assert origin == "Tokyo Haneda"
    assert destination == "Shanghai Pudong"


def test_extract_route_preserves_airport_codes() -> None:
    origin, destination = _extract_route(
        "Book a flight from HND to PVG on 2026-05-10"
    )

    assert origin == "HND"
    assert destination == "PVG"
