"""Booking Agent Node.

Responsible for booking intent execution:
1) discover offers (browser-use)
2) select one offer
3) proceed to provider checkout (Playwright)
"""

from langchain_core.messages import SystemMessage, AIMessage
import re
import uuid
import logging

from backend.agent.state import AgentState
from backend.agent.tools.booking_tools import (
    find_booking_options,
    select_booking_option,
    proceed_checkout,
)
from backend.llm import get_agent_llm


def _extract_date_iso(text: str) -> str:
    match = re.search(r"(20\d{2})[\-/年]\s*(\d{1,2})[\-/月]\s*(\d{1,2})", text)
    if match:
        y, m, d = match.groups()
        return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
    return ""


def _extract_route(text: str) -> tuple[str, str]:
    lowered = text.lower()
    origin = ""
    destination = ""

    # Generic patterns first: 出发机场/到达机场, or 出发/到达
    cn_origin_match = re.search(r"出发机场[:：\s]*([^\s，,;]+)", text)
    cn_dest_match = re.search(r"到达机场[:：\s]*([^\s，,;]+)", text)
    if cn_origin_match:
        origin = cn_origin_match.group(1).strip()
    if cn_dest_match:
        destination = cn_dest_match.group(1).strip()

    if not origin:
        cn_origin_match = re.search(r"出发[:：\s]*([^\s，,;]+)", text)
        if cn_origin_match:
            origin = cn_origin_match.group(1).strip()
    if not destination:
        cn_dest_match = re.search(r"到达[:：\s]*([^\s，,;]+)", text)
        if cn_dest_match:
            destination = cn_dest_match.group(1).strip()

    # English patterns: from X to Y
    if not origin or not destination:
        en_match = re.search(
            r"from\s+([a-z0-9()\-/\s]+?)\s+to\s+([a-z0-9()\-/\s]+?)"
            r"(?=\s+(?:on|for|depart(?:ing|ure)|return|with|budget)\b|[,.]|$)",
            text,
            re.IGNORECASE,
        )
        if en_match:
            if not origin:
                origin = en_match.group(1).strip(" ,.;")
            if not destination:
                destination = en_match.group(2).strip(" ,.;")

    # Fallback: keep legacy explicit mapping for known routes
    if not origin and ("东京" in text or "tokyo" in lowered):
        origin = "Tokyo"
    if not destination and ("上海" in text or "shanghai" in lowered):
        destination = "Shanghai"
    if "上海飞东京" in text or "shanghai to tokyo" in lowered:
        origin, destination = "Shanghai", "Tokyo"

    return origin, destination


def _is_booking_query(text: str) -> bool:
    lowered = text.lower()
    keywords = ["机票", "订票", "航班", "flight", "book", "trip.com", "tripcom"]
    return any(k in text or k in lowered for k in keywords)


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
    info.setdefault("headless", True)
    return info


def booking_agent_node(state: AgentState) -> dict:
    _log = logging.getLogger(__name__)
    llm = get_agent_llm(role="booking_agent", temperature=0)

    llm_with_tools = llm.bind_tools([
        find_booking_options,
        select_booking_option,
        proceed_checkout,
    ])

    plan = state.get("plan", [])
    current_step = state.get("current_step", 0)
    messages = state["messages"]
    critique = state.get("critique", "")

    latest_user_input = messages[-1].content
    if plan and current_step < len(plan):
        instruction = plan[current_step]
    else:
        instruction = latest_user_input

    # Deterministic kickoff: ensure tool call happens for booking requests.
    booking_offers = list(state.get("booking_offers") or [])
    selected_offer = dict(state.get("selected_offer") or {})
    booking_result = dict(state.get("booking_result") or {})
    booking_context = state.get("booking_context") or {}
    if booking_offers and not selected_offer:
        match = re.search(r"\boffer_\d+\b", instruction)
        if match:
            auto_select = {
                "name": "select_booking_option",
                "args": {
                    "option_id": match.group(0),
                    "notes": "User selected offer id.",
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_select])],
                "last_agent": "booking_agent",
            }
    if (
        selected_offer
        and booking_context.get("explicit_selection")
        and not booking_result
        and booking_context.get("checkout_status") not in {
        "in_progress",
        "needs_user_payment",
        "needs_user_input",
        "failed",
        }
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
                "headless": True,
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
                "args": {**traveler_payload, "headless": True},
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_checkout])],
                "last_agent": "booking_agent",
            }
        selected_id = booking_context.get("selected_offer_id")
        if selected_id and booking_offers:
            auto_select = {
                "name": "select_booking_option",
                "args": {
                    "option_id": selected_id,
                    "notes": "Use cached selection for checkout.",
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            auto_checkout = {
                "name": "proceed_checkout",
                "args": {**traveler_payload, "headless": True},
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_select, auto_checkout])],
                "last_agent": "booking_agent",
            }
        if booking_offers and len(booking_offers) == 1:
            auto_select = {
                "name": "select_booking_option",
                "args": {
                    "option_id": booking_offers[0].get("id"),
                    "notes": "Auto-selected only available offer.",
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            auto_checkout = {
                "name": "proceed_checkout",
                "args": {**traveler_payload, "headless": True},
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_select, auto_checkout])],
                "last_agent": "booking_agent",
            }
    if not booking_offers and not selected_offer and not booking_result and _is_booking_query(instruction):
        last_msg = messages[-1] if messages else None
        if booking_context.get("attempted") and getattr(last_msg, "type", "") == "tool":
            failure_reason = str(booking_context.get("last_error") or "").strip()
            message = (
                "已经尝试过 trip.com 实时抓取，但没有拿到可用结果。"
                "请补充：出发/到达机场、日期、单程或往返、舱位、预算，"
                "或直接提供 trip.com 搜索链接。"
            )
            if failure_reason:
                message = f"{message}\nDebug reason: {failure_reason}"
            return {
                "messages": [AIMessage(content=message)],
                "last_agent": "booking_agent",
            }
        if booking_context.get("attempted") or booking_context.get("last_error"):
            failure_reason = str(booking_context.get("last_error") or "").strip()
            message = (
                "已经尝试过 trip.com 实时抓取，但没有拿到可用结果。"
                "请补充：出发/到达机场、日期、单程或往返、舱位、预算，"
                "或直接提供 trip.com 搜索链接。"
            )
            if failure_reason:
                message = f"{message}\nDebug reason: {failure_reason}"
            return {
                "messages": [AIMessage(content=message)],
                "last_agent": "booking_agent",
            }
        origin, destination = _extract_route(instruction)
        departure_date = _extract_date_iso(instruction)
        if not origin or not destination or not departure_date:
            missing = []
            if not origin or not destination:
                missing.append("出发/到达机场")
            if not departure_date:
                missing.append("日期")
            hint = "、".join(missing) if missing else "必要信息"
            return {
                "messages": [
                    AIMessage(
                        content=(
                            f"我需要补充 {hint} 才能在 trip.com 实时查询机票。"
                            "请提供：出发机场、到达机场、日期（YYYY-MM-DD）、单程或往返、舱位、预算。"
                        )
                    )
                ],
                "last_agent": "booking_agent",
            }
        if origin and destination and departure_date:
            auto_call = {
                "name": "find_booking_options",
                "args": {
                    "booking_type": "flight",
                    "origin": origin,
                    "destination": destination,
                    "departure_date": departure_date,
                    "return_date": "",
                    "adults": 1,
                    "budget_limit": 0.0,
                    "provider_hint": "trip.com",
                    "max_results": 10,
                },
                "id": f"auto_{uuid.uuid4().hex[:10]}",
                "type": "tool_call",
            }
            return {
                "messages": [AIMessage(content="", tool_calls=[auto_call])],
                "last_agent": "booking_agent",
            }

    booking_hint = state.get("booking_context") or {}

    system_content = f"""You are the Booking Agent for VACAY.

Current booking context: {booking_hint}
Task: {instruction}
{f"Critic feedback: {critique}" if critique else ""}

Rules:
- Use find_booking_options to discover options first.
- Use select_booking_option before checkout.
- Use proceed_checkout only after an option is selected.
- Trip.com search must use real fetched results. Do not fabricate offers.
- If tool says no actionable offers, ask the user to refine inputs:
    exact origin/destination airport, date, one-way or round-trip, cabin, budget,
    or provide a direct trip.com search URL.
- If traveler info is missing, ask the user for:
    traveler_name, traveler_email, traveler_gender, traveler_birth_date,
    traveler_nationality, traveler_doc_type, traveler_doc_number, traveler_doc_expiry.
- Never claim payment completed.
- If checkout reaches pre-payment, share the returned confirmation URL and ask
    user to complete payment in the trip.com page.
- End with a concise summary when done.
"""

    response = llm_with_tools.invoke([SystemMessage(content=system_content)] + list(messages))
    _log.info(">>> BOOKING_AGENT tool_calls=%s", getattr(response, "tool_calls", None)
    )

    # Guardrail: do not allow free-form "booking completed" style responses
    # before any real booking tool state exists.
    has_tool_calls = bool(getattr(response, "tool_calls", None))
    has_booking_state = bool(state.get("booking_offers") or state.get("booking_result"))
    if not has_tool_calls and not has_booking_state:
        response = AIMessage(
            content=(
                "我还没有拿到真实的 trip.com 抓取结果，所以不能确认已完成订票。"
                "我将先执行查询；如果失败，我会请你补充：出发/到达机场、日期、单程或往返、舱位、预算，"
                "或直接提供 trip.com 搜索链接。"
            )
        )

    return {
        "messages": [response],
        "last_agent": "booking_agent",
    }
