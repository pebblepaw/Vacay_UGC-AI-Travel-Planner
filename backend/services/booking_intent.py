"""LLM-based normalization for booking requests."""

from __future__ import annotations

import json
from datetime import date
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from backend.app_config import get_assistant_language_instruction, render_copy
from backend.llm import get_agent_llm


class BookingIntent(BaseModel):
    is_booking_request: bool = True
    booking_type: str = "flight"
    provider_hint: str = "trip.com"
    origin: str = ""
    origin_code: str = ""
    origin_city_code: str = ""
    destination: str = ""
    destination_code: str = ""
    destination_city_code: str = ""
    departure_date: str = ""
    return_date: str = ""
    trip_type: str = ""
    adults: int | None = None
    cabin: str = ""
    budget_limit: float = 0.0
    origin_source: str = ""
    destination_source: str = ""
    departure_date_source: str = ""
    trip_type_source: str = ""
    adults_source: str = ""
    missing_fields: list[str] = Field(default_factory=list)
    can_search: bool = False
    follow_up_question: str = ""


def _format_trip_context(trip: Any) -> str:
    if not trip:
        return "No trip context."

    lines = [f"Trip title: {trip.title}"]
    for day in trip.days:
        lines.append(f"Day {day.day_number} ({day.date})")
        for poi in day.pois:
            lines.append(f"- {poi.name} | {poi.category} | {poi.time_slot}")
    return "\n".join(lines)


def _extract_json_block(text: str) -> dict[str, Any]:
    stripped = (text or "").strip()
    if stripped.startswith("```"):
        parts = [part for part in stripped.split("```") if part.strip()]
        stripped = parts[0]
        if stripped.lower().startswith("json"):
            stripped = stripped[4:].strip()
    return json.loads(stripped)


def normalize_booking_intent(
    *,
    message: str,
    trip: Any = None,
    history: list[Any] | None = None,
    llm: Any | None = None,
) -> BookingIntent:
    llm = llm or get_agent_llm(role="booking_intent", temperature=0)
    trip_context = _format_trip_context(trip)
    recent_history = []
    for item in history or []:
        content = getattr(item, "content", "")
        if content:
            recent_history.append(str(content))
    history_text = "\n".join(recent_history[-6:]) or "No recent chat history."
    today = date.today().isoformat()

    system = SystemMessage(
        content=(
            "You normalize travel booking requests into a strict JSON object.\n"
            f"{get_assistant_language_instruction()}\n"
            f"Today is {today}.\n"
            "Infer dates in YYYY-MM-DD.\n"
            "Prefer gateway cities and city codes for regional destinations when that is more reliable than one airport.\n"
            "Only return airport or city codes if you are confident.\n"
            "If a required field is missing or ambiguous, set can_search=false, list the missing_fields, and write one short follow_up_question.\n"
            "Required fields for a flight search: origin, destination, departure_date, trip_type, adults.\n"
            "Return JSON only with this schema:\n"
            "{"
            "\"is_booking_request\":true,"
            "\"booking_type\":\"flight\","
            "\"provider_hint\":\"trip.com\","
            "\"origin\":\"\","
            "\"origin_code\":\"\","
            "\"origin_city_code\":\"\","
            "\"destination\":\"\","
            "\"destination_code\":\"\","
            "\"destination_city_code\":\"\","
            "\"departure_date\":\"\","
            "\"return_date\":\"\","
            "\"trip_type\":\"one_way|round_trip\","
            "\"adults\":1,"
            "\"cabin\":\"economy|premium_economy|business|first|\","
            "\"budget_limit\":0,"
            "\"origin_source\":\"user|trip_context|inference|missing\","
            "\"destination_source\":\"user|trip_context|inference|missing\","
            "\"departure_date_source\":\"user|trip_context|inference|missing\","
            "\"trip_type_source\":\"user|trip_context|inference|missing\","
            "\"adults_source\":\"user|trip_context|inference|missing\","
            "\"missing_fields\":[],"
            "\"can_search\":false,"
            "\"follow_up_question\":\"\""
            "}"
        )
    )
    human = HumanMessage(
        content=(
            f"Trip context:\n{trip_context}\n\n"
            f"Recent chat history:\n{history_text}\n\n"
            f"User booking request:\n{message}"
        )
    )

    response = llm.invoke([system, human])
    payload = _extract_json_block(getattr(response, "content", ""))
    intent = BookingIntent.model_validate(payload)

    if not intent.is_booking_request:
        intent.booking_type = ""
        intent.provider_hint = ""
        intent.missing_fields = []
        intent.can_search = False
        intent.follow_up_question = ""
        return intent

    missing_fields = list(intent.missing_fields)

    def require(field_name: str, value: Any, source: str, allowed_sources: set[str]) -> None:
        if value and source in allowed_sources:
            return
        if field_name not in missing_fields:
            missing_fields.append(field_name)

    require("origin airport", intent.origin, intent.origin_source, {"user", "trip_context"})
    require("destination", intent.destination, intent.destination_source, {"user", "trip_context"})
    require("departure date", intent.departure_date, intent.departure_date_source, {"user"})
    require("trip type", intent.trip_type, intent.trip_type_source, {"user"})
    require("adult count", intent.adults, intent.adults_source, {"user"})

    intent.missing_fields = missing_fields
    intent.can_search = not missing_fields

    if not intent.follow_up_question and not intent.can_search:
        fields = ", ".join(intent.missing_fields) if intent.missing_fields else "the missing details"
        intent.follow_up_question = render_copy(
            "booking.missing_details",
            fields=fields,
            provider=intent.provider_hint or "trip.com",
        )

    return intent
