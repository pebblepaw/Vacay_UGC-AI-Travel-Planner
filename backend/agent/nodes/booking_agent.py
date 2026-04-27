"""Booking Agent Node."""

from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
import logging
import re
import uuid

from backend.agent.state import AgentState
from backend.agent.tools.booking_tools import (
    find_booking_options,
    proceed_checkout,
    select_booking_option,
)
from backend.app_config import get_assistant_language_instruction, render_copy
from backend.llm import get_agent_llm
from backend.services.booking_intent import normalize_booking_intent


def _latest_human_content(messages: list) -> str:
    for message in reversed(messages):
        if isinstance(message, HumanMessage):
            content = getattr(message, "content", "")
            if content:
                return str(content)
    return ""


def _user_requested_immediate_booking(text: str) -> bool:
    lowered = (text or "").lower()
    return any(token in lowered for token in ("book ", "book a", "book the", "reserve", "checkout"))


def _user_requested_checkout_retry(text: str) -> bool:
    lowered = (text or "").lower()
    return any(
        token in lowered
        for token in (
            "continue",
            "try again",
            "retry",
            "solved",
            "go with",
            "let's go with",
            "lets go with",
            "option",
            "book it",
            "checkout",
        )
    )


def _checkout_retry_turn_key(text: str) -> str:
    normalized = re.sub(r"\s+", " ", (text or "").strip().lower())
    return normalized[:256]


def _extract_offer_selection_id(text: str, offers: list[dict]) -> str:
    normalized = (text or "").strip()
    if not normalized or not offers:
        return ""

    lowered = normalized.lower()
    offer_ids = {str(offer.get("id") or "").lower(): str(offer.get("id") or "") for offer in offers}
    direct = re.search(r"\boffer_\d+\b", lowered)
    if direct and direct.group(0) in offer_ids:
        return offer_ids[direct.group(0)]

    selection_match = re.search(
        r"(?:^|\b)(?:option|choice|number|no\.?|#|go with|pick|choose|select|take|use|let'?s go with)\s*[_#-]?\s*(\d+)\b",
        lowered,
    )
    exact_number_match = re.fullmatch(r"(?:option\s*)?(\d+)\.?", lowered)
    number = int((selection_match or exact_number_match).group(1)) if (selection_match or exact_number_match) else 0
    if 1 <= number <= len(offers):
        return str(offers[number - 1].get("id") or "")
    return ""


def _extract_traveler_info(text: str) -> dict[str, str]:
    info: dict[str, str] = {}
    boundary = r"(?=\s*(性别|出生日期|国籍|证件类型|证件号|证件有效期|邮箱|手机号|$))"
    patterns = {
        "traveler_name": rf"姓名[:：\s]*([\u4e00-\u9fffA-Za-z\s]+?){boundary}",
        "traveler_gender": r"性别[:：\s]*([男女]|male|female)",
        "traveler_birth_date": r"出生日期[:：\s]*(\d{4}-\d{2}-\d{2})",
        "traveler_nationality": rf"国籍[:：\s]*([\u4e00-\u9fffA-Za-z\s]+?){boundary}",
        "traveler_doc_type": r"证件类型[:：\s]*(护照|身份证|passport|id)",
        "traveler_doc_number": r"证件号[:：\s]*([A-Za-z0-9\-]{5,})",
        "traveler_doc_expiry": r"证件有效期[:：\s]*(\d{4}-\d{2}-\d{2})",
        "traveler_email": r"邮箱[:：\s]*([\w\.-]+@[\w\.-]+\.[A-Za-z]{2,})",
        "traveler_phone": r"手机号[:：\s]*([\+\d\-\s]{7,})",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            info[key] = match.group(1).strip()
    if not info:
        return {}
    info.setdefault("traveler_phone", "")
    info.setdefault("headless", False)
    return info


def booking_agent_node(state: AgentState) -> dict:
    _log = logging.getLogger(__name__)

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    messages = state["messages"]
    critique = state.get("critique", "")

    latest_user_input = messages[-1].content
    if plan and current_step < len(plan):
        instruction = plan[current_step]
    else:
        instruction = latest_user_input

    booking_offers = list(state.get("booking_offers") or [])
    selected_offer = dict(state.get("selected_offer") or {})
    booking_result = dict(state.get("booking_result") or {})
    booking_context = state.get("booking_context") or {}
    latest_human_input = _latest_human_content(messages)

    checkout_status = str(booking_context.get("checkout_status") or booking_result.get("status") or "")
    provider_verification_pending = (
        checkout_status == "needs_user_input"
        and booking_result.get("handoff_channel") == "provider_verification"
    )
    failure_text = " ".join(
        [
            str(booking_result.get("reason") or ""),
            str(booking_context.get("last_error") or ""),
        ]
    ).lower()
    live_session_lost = "live session" in failure_text and "no longer available" in failure_text
    if (
        selected_offer
        and booking_result
        and checkout_status == "failed"
        and live_session_lost
        and _user_requested_immediate_booking(latest_human_input)
    ):
        intent = normalize_booking_intent(
            message=instruction,
            trip=state.get("trip"),
            history=messages,
        )
        if intent.is_booking_request and intent.can_search:
            refresh_call = {
                "name": "find_booking_options",
                "args": {
                    "booking_type": intent.booking_type,
                    "origin": intent.origin,
                    "origin_code": intent.origin_code,
                    "origin_city_code": intent.origin_city_code,
                    "destination": intent.destination,
                    "destination_code": intent.destination_code,
                    "destination_city_code": intent.destination_city_code,
                    "departure_date": intent.departure_date,
                    "return_date": intent.return_date,
                    "trip_type": intent.trip_type,
                    "adults": intent.adults,
                    "budget_limit": intent.budget_limit,
                    "cabin": intent.cabin,
                    "provider_hint": intent.provider_hint,
                    "max_results": 10,
                    "force_refresh": True,
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[refresh_call])],
                "last_agent": "booking_agent",
            }

    if (
        selected_offer
        and booking_result
        and checkout_status in {"failed", "needs_user_input"}
        and (checkout_status == "failed" or provider_verification_pending)
        and _user_requested_checkout_retry(latest_human_input)
    ):
        retry_turn_key = _checkout_retry_turn_key(latest_human_input)
        if booking_context.get("checkout_retry_turn_key") == retry_turn_key:
            return {
                "messages": [AIMessage(content="")],
                "last_agent": "booking_agent",
            }
        retry_checkout = {
            "name": "proceed_checkout",
            "args": {
                "traveler_name": "",
                "traveler_email": "",
                "traveler_phone": "",
                "traveler_gender": "",
                "traveler_birth_date": "",
                "traveler_nationality": "",
                "traveler_doc_type": "",
                "traveler_doc_number": "",
                "traveler_doc_expiry": "",
                "headless": False,
                "allow_empty_traveler": True,
            },
            "id": f"auto_{uuid.uuid4().hex[:10]}",
            "type": "tool_call",
        }
        return {
            "messages": [AIMessage(content="", tool_calls=[retry_checkout])],
            "last_agent": "booking_agent",
            "booking_context": {
                **booking_context,
                "checkout_retry_turn_key": retry_turn_key,
            },
        }

    if booking_offers and not selected_offer:
        selected_offer_id = (
            _extract_offer_selection_id(instruction, booking_offers)
            or _extract_offer_selection_id(latest_human_input, booking_offers)
        )
        if selected_offer_id:
            auto_select = {
                "name": "select_booking_option",
                "args": {
                    "option_id": selected_offer_id,
                    "notes": "User selected offer id.",
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_select])],
                "last_agent": "booking_agent",
            }
        if _user_requested_immediate_booking(latest_human_input):
            return {
                "messages": [AIMessage(content="Choose one flight option by number before I open checkout.")],
                "last_agent": "booking_agent",
            }

    if (
        selected_offer
        and booking_context.get("explicit_selection")
        and not booking_result
        and booking_context.get("checkout_status")
        not in {"in_progress", "needs_user_payment", "needs_user_input", "failed"}
    ):
        auto_checkout = {
            "name": "proceed_checkout",
            "args": {
                "traveler_name": "",
                "traveler_email": "",
                "traveler_phone": "",
                "traveler_gender": "",
                "traveler_birth_date": "",
                "traveler_nationality": "",
                "traveler_doc_type": "",
                "traveler_doc_number": "",
                "traveler_doc_expiry": "",
                "headless": False,
                "allow_empty_traveler": True,
            },
            "id": f"auto_{uuid.uuid4().hex[:10]}",
            "type": "tool_call",
        }
        return {
            "messages": [AIMessage(content="", tool_calls=[auto_checkout])],
            "last_agent": "booking_agent",
        }

    traveler_payload = _extract_traveler_info(latest_user_input)
    if traveler_payload and not booking_result and booking_context.get("checkout_status") not in {
        "in_progress",
        "needs_user_payment",
        "failed",
    }:
        if selected_offer:
            auto_checkout = {
                "name": "proceed_checkout",
                "args": {**traveler_payload, "headless": False},
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_checkout])],
                "last_agent": "booking_agent",
            }

    if not booking_offers and not selected_offer and not booking_result:
        provider = str(booking_context.get("provider_hint") or "trip.com")
        last_graph_message = messages[-1] if messages else None

        intent = normalize_booking_intent(
            message=instruction,
            trip=state.get("trip"),
            history=messages,
        )
        if intent.is_booking_request:
            if (
                booking_context.get("attempted")
                and booking_context.get("last_error")
                and getattr(last_graph_message, "type", "") == "tool"
            ):
                failure = render_copy(
                    "booking.attempted_no_results",
                    provider=provider,
                )
                refine = render_copy("booking.refine_request", provider=provider)
                return {
                    "messages": [AIMessage(content=f"{failure}\n{refine}")],
                    "last_agent": "booking_agent",
                }

            if intent.can_search:
                auto_call = {
                    "name": "find_booking_options",
                    "args": {
                        "booking_type": intent.booking_type,
                        "origin": intent.origin,
                        "origin_code": intent.origin_code,
                        "origin_city_code": intent.origin_city_code,
                        "destination": intent.destination,
                        "destination_code": intent.destination_code,
                        "destination_city_code": intent.destination_city_code,
                        "departure_date": intent.departure_date,
                        "return_date": intent.return_date,
                        "trip_type": intent.trip_type,
                        "adults": intent.adults,
                        "budget_limit": intent.budget_limit,
                        "cabin": intent.cabin,
                        "provider_hint": intent.provider_hint,
                        "max_results": 10,
                    },
                    "id": f"auto_{uuid.uuid4().hex[:10]}",
                    "type": "tool_call",
                }
                return {
                    "messages": [AIMessage(content="", tool_calls=[auto_call])],
                    "last_agent": "booking_agent",
                }

            return {
                "messages": [AIMessage(content=intent.follow_up_question)],
                "last_agent": "booking_agent",
            }

    llm = get_agent_llm(role="booking_agent", temperature=0)
    llm_with_tools = llm.bind_tools([
        find_booking_options,
        select_booking_option,
        proceed_checkout,
    ])

    system_content = f"""You are the Booking Agent for VACAY.

Current booking context: {booking_context}
Task: {instruction}
{f"Critic feedback: {critique}" if critique else ""}
{get_assistant_language_instruction()}

Rules:
- Use find_booking_options to discover options first.
- Use select_booking_option before checkout.
- Use proceed_checkout only after an option is selected.
- Trip.com search must use real fetched results. Do not fabricate offers.
- If tool says no actionable offers, ask the user to refine inputs:
  exact origin/destination airport or gateway city, date, one-way or round-trip,
  cabin, adult count, budget, or provide a direct trip.com search URL.
- If traveler info is missing, ask the user for:
  traveler_name, traveler_email, traveler_gender, traveler_birth_date,
  traveler_nationality, traveler_doc_type, traveler_doc_number, traveler_doc_expiry.
- Never claim payment completed.
- If checkout reaches pre-payment, share the returned confirmation URL and ask
  the user to complete payment in the trip.com page.
- End with a concise summary when done.
"""

    response = llm_with_tools.invoke([SystemMessage(content=system_content)] + list(messages))
    _log.info(">>> BOOKING_AGENT tool_calls=%s", getattr(response, "tool_calls", None))

    has_tool_calls = bool(getattr(response, "tool_calls", None))
    has_booking_state = bool(state.get("booking_offers") or state.get("booking_result"))
    if not has_tool_calls and not has_booking_state:
        response = AIMessage(
            content=render_copy(
                "booking.guard_no_completion",
                provider=booking_context.get("provider_hint") or "trip.com",
            )
        )

    return {
        "messages": [response],
        "last_agent": "booking_agent",
    }
