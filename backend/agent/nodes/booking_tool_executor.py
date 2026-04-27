"""Custom executor for booking tools.

Why custom:
- We need shared mutable state (offers, selected offer, checkout status)
- Standard ToolNode does not easily persist this state shape for our flow
"""

from __future__ import annotations

from langchain_core.messages import ToolMessage
import logging
import re

from backend.agent.state import AgentState
from backend.services.automation.browser_use_worker import (
    BookingQuery,
    browser_use_worker,
)
from backend.services.automation.playwright_checkout import playwright_checkout_runner


def _latest_human_turn_key(messages: list) -> str:
    for message in reversed(messages):
        if getattr(message, "type", "") == "human":
            return re.sub(r"\s+", " ", str(getattr(message, "content", "") or "").strip().lower())[:256]
    return ""


async def booking_tool_executor(state: AgentState) -> dict:
    _log = logging.getLogger(__name__)
    last_message = state["messages"][-1]
    _log.info(">>> BOOKING_TOOL_EXECUTOR entered, tool_calls=%s", getattr(last_message, "tool_calls", None))

    booking_context = dict(state.get("booking_context") or {})
    booking_offers = list(state.get("booking_offers") or [])
    selected_offer = dict(state.get("selected_offer") or {})
    booking_result = dict(state.get("booking_result") or {})

    tool_messages = []

    for tc in last_message.tool_calls:
        name = tc["name"]
        args = tc["args"]
        call_id = tc["id"]

        try:
            if name == "find_booking_options":
                requested_origin = args.get("origin")
                requested_destination = args.get("destination")
                requested_departure = args.get("departure_date")
                requested_return = args.get("return_date", "")
                requested_trip_type = args.get("trip_type", "")
                requested_provider = args.get("provider_hint", "trip.com")
                force_refresh = bool(args.get("force_refresh", False))
                if (
                    not force_refresh
                    and booking_offers
                    and booking_context.get("origin") == requested_origin
                    and booking_context.get("destination") == requested_destination
                    and booking_context.get("departure_date") == requested_departure
                    and booking_context.get("return_date", "") == requested_return
                    and booking_context.get("trip_type", "") == requested_trip_type
                    and booking_context.get("provider_hint") == requested_provider
                ):
                    message = "Using cached booking offers."
                    tool_messages.append(ToolMessage(content=message, tool_call_id=call_id))
                    continue

                selected_offer = {}
                booking_result = {}

                query = BookingQuery(
                    booking_type=args["booking_type"],
                    origin=requested_origin,
                    destination=requested_destination,
                    departure_date=requested_departure,
                    origin_code=str(args.get("origin_code", "")),
                    origin_city_code=str(args.get("origin_city_code", "")),
                    destination_code=str(args.get("destination_code", "")),
                    destination_city_code=str(args.get("destination_city_code", "")),
                    return_date=requested_return,
                    adults=int(args["adults"]),
                    trip_type=str(args.get("trip_type", "")),
                    cabin=str(args.get("cabin", "")),
                    budget_limit=float(args.get("budget_limit", 0.0)),
                    provider_hint=requested_provider,
                    max_results=int(args.get("max_results", 5)),
                )
                attempted_context = {
                    "booking_type": query.booking_type,
                    "origin": query.origin,
                    "destination": query.destination,
                    "departure_date": query.departure_date,
                    "return_date": query.return_date,
                    "trip_type": query.trip_type,
                    "adults": query.adults,
                    "provider_hint": query.provider_hint,
                    "attempted": True,
                    "explicit_selection": False,
                }
                offers = await browser_use_worker.search_offers(query)
                booking_context = attempted_context
                booking_offers = offers
                if not offers:
                    failure_reason = (browser_use_worker.last_error or "unknown reason").strip()
                    booking_context["last_error"] = failure_reason
                    message = (
                        "Trip.com real-time fetch returned no actionable offers. "
                        "Please ask the user to refine inputs (airport codes, exact date, one-way/round-trip, cabin, budget), "
                        "or provide a direct trip.com search URL. "
                        f"Debug reason: {failure_reason}"
                    )
                else:
                    summary = [f"Found {len(offers)} options:"]
                    for item in offers:
                        summary.append(
                            f"- {item['id']}: {item['title']} ({item['currency']} {item['price']})"
                        )
                    message = "\n".join(summary)
                _log.info(">>> BOOKING_TOOL_EXECUTOR offers=%s", len(booking_offers))

            elif name == "select_booking_option":
                option_id = args["option_id"]
                selected = next((o for o in booking_offers if o.get("id") == option_id), None)
                if not selected:
                    message = f"Option '{option_id}' not found. Run find_booking_options first."
                else:
                    selected_offer = selected
                    booking_context["selected_offer_id"] = selected.get("id")
                    booking_context["explicit_selection"] = True
                    message = (
                        f"Selected {selected['id']}: {selected['title']} "
                        f"({selected['currency']} {selected['price']})"
                    )

            elif name == "proceed_checkout":
                if not selected_offer:
                    message = "No selected offer. Call select_booking_option first."
                else:
                    checkout_status = booking_context.get("checkout_status")
                    handoff_channel = booking_result.get("handoff_channel")
                    if checkout_status in {"in_progress", "needs_user_payment"} or (
                        checkout_status == "needs_user_input"
                        and handoff_channel != "provider_verification"
                    ):
                        message = "Checkout already attempted; skipping duplicate checkout call."
                        tool_messages.append(ToolMessage(content=message, tool_call_id=call_id))
                        continue

                    traveler_name = str(args.get("traveler_name", "")).strip()
                    traveler_email = str(args.get("traveler_email", "")).strip()
                    traveler_phone = str(args.get("traveler_phone", "")).strip()
                    traveler_gender = str(args.get("traveler_gender", "")).strip()
                    traveler_birth_date = str(args.get("traveler_birth_date", "")).strip()
                    traveler_nationality = str(args.get("traveler_nationality", "")).strip()
                    traveler_doc_type = str(args.get("traveler_doc_type", "")).strip()
                    traveler_doc_number = str(args.get("traveler_doc_number", "")).strip()
                    traveler_doc_expiry = str(args.get("traveler_doc_expiry", "")).strip()

                    allow_empty_traveler = bool(args.get("allow_empty_traveler", False))
                    if not allow_empty_traveler:
                        missing_fields = []
                        if not traveler_name:
                            missing_fields.append("traveler_name")
                        if not traveler_email:
                            missing_fields.append("traveler_email")
                        if not traveler_gender:
                            missing_fields.append("traveler_gender")
                        if not traveler_birth_date:
                            missing_fields.append("traveler_birth_date")
                        if not traveler_nationality:
                            missing_fields.append("traveler_nationality")
                        if not traveler_doc_type:
                            missing_fields.append("traveler_doc_type")
                        if not traveler_doc_number:
                            missing_fields.append("traveler_doc_number")
                        if not traveler_doc_expiry:
                            missing_fields.append("traveler_doc_expiry")

                        if missing_fields:
                            message = (
                                "Missing traveler info. Please ask the user to provide: "
                                + ", ".join(missing_fields)
                                + "."
                            )
                            tool_messages.append(ToolMessage(content=message, tool_call_id=call_id))
                            continue

                    traveler = {
                        "name": traveler_name,
                        "email": traveler_email,
                        "phone": traveler_phone,
                        "gender": traveler_gender,
                        "birth_date": traveler_birth_date,
                        "nationality": traveler_nationality,
                        "doc_type": traveler_doc_type,
                        "doc_number": traveler_doc_number,
                        "doc_expiry": traveler_doc_expiry,
                    }
                    headless = bool(args.get("headless", True))
                    booking_context["checkout_status"] = "in_progress"
                    checkout_offer = dict(selected_offer)
                    workspace_id = str(state.get("workspace_id") or "").strip()
                    if workspace_id:
                        checkout_offer.setdefault("workspace_id", workspace_id)
                    try:
                        result = await playwright_checkout_runner.checkout_to_confirmation(
                            checkout_offer,
                            traveler,
                            headless=headless,
                            skip_fill=allow_empty_traveler,
                        )
                    except Exception as exc:
                        result = {
                            "status": "failed",
                            "reason": f"checkout exception: {exc}",
                            "confirmation_url": "",
                            "screenshot": "",
                        }

                    booking_result = result
                    booking_context["checkout_status"] = result.get("status") or "unknown"
                    checkout_turn_key = _latest_human_turn_key(list(state.get("messages") or []))
                    if checkout_turn_key:
                        booking_context["checkout_retry_turn_key"] = checkout_turn_key
                    if result.get("status") == "failed":
                        booking_context["last_error"] = result.get("reason")
                    _log.info(">>> BOOKING_TOOL_EXECUTOR checkout_result=%s", result
                    )

                    message = (
                        f"Checkout status: {result.get('status')}\n"
                        f"Reason: {result.get('reason')}\n"
                        f"URL: {result.get('confirmation_url')}\n"
                        f"Screenshot: {result.get('screenshot')}"
                    )

            else:
                message = f"Unknown booking tool: {name}"

        except Exception as exc:
            if name == "find_booking_options":
                booking_offers = []
                selected_offer = {}
                booking_result = {}
                booking_context = {
                    "booking_type": str(args.get("booking_type", "")),
                    "origin": str(args.get("origin", "")),
                    "destination": str(args.get("destination", "")),
                    "departure_date": str(args.get("departure_date", "")),
                    "return_date": str(args.get("return_date", "")),
                    "trip_type": str(args.get("trip_type", "")),
                    "adults": int(args.get("adults", 1)),
                    "provider_hint": str(args.get("provider_hint", "trip.com")),
                    "attempted": True,
                    "explicit_selection": False,
                    "last_error": str(exc),
                }
            message = f"Error executing {name}: {exc}"

        tool_messages.append(ToolMessage(content=message, tool_call_id=call_id))

    return {
        "messages": tool_messages,
        "booking_context": booking_context,
        "booking_offers": booking_offers,
        "selected_offer": selected_offer,
        "booking_result": booking_result,
    }
