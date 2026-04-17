
"""
Response Formatter Node — Produces the final user-facing message.

This is the last node before END. It:
1. Summarizes what changes were made
2. Shows the updated trip overview
3. Formats everything nicely for the chat UI

This node also handles advancing the plan to the next step.
If there are more steps in the plan, it routes back to the orchestrator.
"""

import json
import re

from langchain_core.messages import AIMessage
from backend.agent.state import AgentState
from backend.app_config import render_copy


def _is_results_url(url: str) -> bool:
    lowered = (url or "").lower()
    if "/flights/passenger" in lowered:
        return False
    if "showfarefirst" in lowered:
        return True
    if "/flights/?" in lowered and "triptype" in lowered:
        return True
    return False


def _format_trip_summary(trip) -> str:
    """Compact trip summary for the chat response."""
    if not trip:
        return ""

    lines = []
    for day in trip.days:
        poi_names = [f"{p.name} ({p.time_slot})" for p in day.pois]
        lines.append(f"📅 Day {day.day_number}: {', '.join(poi_names)}")
    return "\n".join(lines)


def _infer_search_result_context(instruction: str) -> tuple[int, str, str]:
    lowered = (instruction or "").lower()
    day_match = re.search(r"\bday\s+(\d+)\b", instruction or "", re.IGNORECASE)
    day_number = int(day_match.group(1)) if day_match else 1

    if any(token in lowered for token in ["lunch", "restaurant", "meal", "food", "eat"]):
        return day_number, "Food", "12:00 - 13:30"
    if "dinner" in lowered:
        return day_number, "Food", "19:00 - 20:30"
    if "nightlife" in lowered or "bar" in lowered or "club" in lowered:
        return day_number, "Nightlife", "20:00 - 22:00"
    return day_number, "Culture", "10:00 - 12:00"


def _extract_search_results(messages, instruction: str) -> list[dict]:
    day_number, category, time_slot = _infer_search_result_context(instruction)

    for msg in reversed(messages):
        if getattr(msg, "type", "") != "tool":
            continue
        try:
            payload = json.loads(msg.content or "")
        except Exception:
            continue
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            continue

        results = []
        for item in raw_results:
            if not isinstance(item, dict):
                continue
            coords = item.get("coords")
            if not isinstance(coords, list) or len(coords) != 2:
                coords = [0.0, 0.0]
            results.append(
                {
                    "name": item.get("name") or "",
                    "description": item.get("description") or "",
                    "coords": coords,
                    "category": category,
                    "time_slot": time_slot,
                    "day_number": day_number,
                }
            )
        if results:
            return results
    return []


def response_formatter_node(state: AgentState) -> dict:
    """Format the final response and check if there are more plan steps."""
    import logging as _logging
    _log = _logging.getLogger(__name__)
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    _log.info(f">>> FORMATTER NODE entered, plan={plan}, current_step={current_step}")

    messages = state["messages"]
    trip = state.get("trip")
    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    last_agent = state.get("last_agent")
    booking_result = state.get("booking_result") or {}
    booking_offers = state.get("booking_offers") or []
    selected_offer = state.get("selected_offer") or {}
    booking_context = state.get("booking_context") or {}
    provider = str(booking_context.get("provider_hint") or "trip.com")
    handoff_channel = str(booking_result.get("handoff_channel") or "")
    chat_interrupt = None

    # ── Find the last substantive AI response ──
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            last_ai_content = msg.content
            break

    current_instruction = ""
    if plan and current_step < len(plan):
        current_instruction = plan[current_step]
    elif messages:
        current_instruction = messages[-1].content or ""

    if last_agent == "search_agent":
        search_results = _extract_search_results(messages, current_instruction)
        if search_results:
            options = []
            for index, item in enumerate(search_results, start=1):
                coords = item.get("coords") or [0.0, 0.0]
                coord_text = f"coords: {coords[0]}, {coords[1]}"
                description = str(item.get("description") or "").strip()
                if description:
                    description = f"{description[:120]} | {coord_text}"
                else:
                    description = coord_text
                options.append(
                    {
                        "id": f"option_{index}",
                        "name": item.get("name") or f"Option {index}",
                        "price": 0.0,
                        "description": description,
                    }
                )
            return {
                "messages": [AIMessage(content=last_ai_content)],
                "next_node": "done",
                "chat_interrupt": {
                    "interrupt_type": "poi_selection",
                    "content": "Which one would you like to add?",
                    "status": "pending",
                    "options": options,
                },
                "search_results": search_results,
            }

    # ── Check if there are more plan steps ──
    next_step = current_step + 1
    has_more_steps = plan and next_step < len(plan)

    if has_more_steps:
        # More steps to execute — route back to orchestrator
        _log.info(f">>> FORMATTER: more steps, advancing to step {next_step}")
        return {
            "current_step": next_step,
            "next_node": "continue_plan",  # Signal to graph router
            "iteration_count": 0,  # Reset critic counter for new step
            "critique": "",  # Clear stale critique
        }

    # ── Final response: use the AI content directly ──
    # The trip summary is redundant since the user sees the timeline/cards view
    formatted = last_ai_content

    # Booking safety gate: prevent false completion if we never reached
    # the real checkout pre-payment stage.
    if last_agent == "booking_agent":
        status = booking_result.get("status")
        confirmation_url = booking_result.get("confirmation_url") or ""
        if status == "needs_user_payment" and _is_results_url(confirmation_url):
            status = None
        if status == "failed":
            reason = booking_result.get("reason") or "unknown reason"
            screenshot = booking_result.get("screenshot") or ""
            formatted = render_copy(
                "booking.checkout_failed",
                reason=reason,
                url=confirmation_url,
                screenshot=screenshot,
            )
            return {
                "messages": [AIMessage(content=formatted)],
                "next_node": "done",
            }
        if status in {"needs_user_payment", "needs_user_input"} and confirmation_url:
            if handoff_channel == "live_browser":
                if status == "needs_user_input":
                    formatted = render_copy(
                        "booking.checkout_live_browser_user_input",
                        status=booking_result.get("status"),
                    )
                else:
                    formatted = render_copy(
                        "booking.checkout_live_browser_payment",
                        status=booking_result.get("status"),
                    )
            else:
                if status == "needs_user_input":
                    formatted = render_copy(
                        "booking.checkout_user_input",
                        status=booking_result.get("status"),
                    )
                else:
                    formatted = render_copy(
                        "booking.checkout_payment",
                        status=booking_result.get("status"),
                    )
                chat_interrupt = {
                    "interrupt_type": "open_url",
                    "content": confirmation_url,
                    "status": "pending",
                }
        elif status != "needs_user_payment":
            if booking_offers:
                if selected_offer:
                    formatted = render_copy(
                        "booking.selected_offer",
                        offer_id=selected_offer.get("id"),
                    )
                else:
                    formatted = render_copy("booking.found_options")
                    options = []
                    for item in booking_offers:
                        try:
                            price_value = float(item.get("price"))
                        except Exception:
                            price_value = 0.0
                        currency = item.get("currency") or "USD"
                        title = item.get("title") or item.get("id")
                        options.append(
                            {
                                "id": item.get("id"),
                                "name": title,
                                "price": price_value,
                                "description": f"{currency} {price_value}",
                            }
                        )
                    chat_interrupt = {
                        "interrupt_type": "confirmation",
                        "content": render_copy("booking.selection_prompt"),
                        "status": "pending",
                        "options": options,
                    }
            else:
                failure_reason = str(booking_context.get("last_error") or "").strip()
                if booking_context.get("attempted") or failure_reason:
                    formatted = (
                        f"{render_copy('booking.attempted_no_results', provider=provider)}\n"
                        f"{render_copy('booking.refine_request', provider=provider)}"
                    )
                    if failure_reason:
                        formatted = f"{formatted}\nDebug reason: {failure_reason}"
                elif last_ai_content:
                    formatted = last_ai_content
        elif booking_result.get("confirmation_url"):
            if handoff_channel == "live_browser":
                if booking_result.get("status") == "needs_user_input":
                    formatted = render_copy(
                        "booking.checkout_live_browser_user_input",
                        status=booking_result.get("status"),
                    )
                else:
                    formatted = render_copy(
                        "booking.checkout_live_browser_payment",
                        status=booking_result.get("status"),
                    )
            else:
                if booking_result.get("status") == "needs_user_input":
                    formatted = render_copy(
                        "booking.checkout_user_input",
                        status=booking_result.get("status"),
                    )
                else:
                    formatted = render_copy(
                        "booking.checkout_payment",
                        status=booking_result.get("status"),
                    )
                chat_interrupt = {
                    "interrupt_type": "open_url",
                    "content": booking_result.get("confirmation_url"),
                    "status": "pending",
                }

    return {
        "messages": [AIMessage(content=formatted)],
        "next_node": "done",
        "chat_interrupt": chat_interrupt,
    }
