
"""
Response Formatter Node — Produces the final user-facing message.

This is the last node before END. It:
1. Summarizes what changes were made
2. Shows the updated trip overview
3. Formats everything nicely for the chat UI

This node also handles advancing the plan to the next step.
If there are more steps in the plan, it routes back to the orchestrator.
"""

from langchain_core.messages import AIMessage
from backend.agent.state import AgentState


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
    chat_interrupt = None

    # ── Find the last substantive AI response ──
    last_ai_content = ""
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and not getattr(msg, "tool_calls", None):
            last_ai_content = msg.content
            break

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
            formatted = (
                "预订未能进入确认页。"
                f"原因：{reason}\n"
                f"链接：{confirmation_url}\n"
                f"截图：{screenshot}"
            )
            return {
                "messages": [AIMessage(content=formatted)],
                "next_node": "done",
            }
        if status in {"needs_user_payment", "needs_user_input"} and confirmation_url:
            if status == "needs_user_input":
                formatted = (
                    "已在新窗口打开 Trip.com 继续页面。Trip.com 可能会先要求登录，"
                    "登录后通常会回到旅客信息页。\n"
                    f"状态：{booking_result.get('status')}"
                )
            else:
                formatted = (
                    "已打开 trip.com 信息填充页，请在新窗口完成填写与支付。\n"
                    f"状态：{booking_result.get('status')}"
                )
            chat_interrupt = {
                "interrupt_type": "open_url",
                "content": confirmation_url,
                "status": "pending",
            }
        elif status != "needs_user_payment":
            if booking_offers:
                if selected_offer:
                    formatted = f"当前已选：{selected_offer.get('id')}。"
                else:
                    formatted = "已找到可选航班，请选择一个。"
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
                        "content": "请选择一个航班以继续订票。",
                        "status": "pending",
                        "options": options,
                    }
            else:
                failure_reason = str(booking_context.get("last_error") or "").strip()
                formatted = (
                    "还没有完成真实订票，也没有拿到可用的 trip.com 实时结果。"
                    "请补充：出发/到达机场、日期、单程或往返、舱位、预算，"
                    "或直接提供 trip.com 搜索链接。"
                )
                if failure_reason:
                    formatted = f"{formatted}\nDebug reason: {failure_reason}"
        elif booking_result.get("confirmation_url"):
            if booking_result.get("status") == "needs_user_input":
                formatted = (
                    "已在新窗口打开 Trip.com 继续页面。Trip.com 可能会先要求登录，"
                    "登录后通常会回到旅客信息页。\n"
                    f"状态：{booking_result.get('status')}"
                )
            else:
                formatted = (
                    "已打开 trip.com 信息填充页，请在新窗口完成填写与支付。\n"
                    f"状态：{booking_result.get('status')}"
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
