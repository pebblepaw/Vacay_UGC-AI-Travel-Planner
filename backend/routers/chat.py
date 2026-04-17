"""
FastAPI routers for chat/AI agent interactions.
Handles chat messages and agent responses (Phase 1: Mock responses).
"""
import abc
import re
from fastapi import APIRouter, HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from datetime import datetime
import logging
import uuid

from backend.models.schemas import ChatRequest, ChatResponse, ChatMessage, Trip
from backend.storage.supabase_storage import supabase_storage as storage
from backend.agent.graph import app


# In-memory booking context cache (per trip) for follow-up selections.
_BOOKING_SESSION: dict[str, dict] = {}
_SEARCH_SESSION: dict[str, list[dict]] = {}

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["chat"])

@router.post("/{trip_id}/chat", response_model=ChatResponse)
async def send_chat_message(trip_id: str, request: ChatRequest):
  
    try:
        # Verify trip exists
        trip = await storage.load_trip(trip_id)
        if not trip:
            raise HTTPException(
                status_code=404,
                detail=f"Trip '{trip_id}' not found"
            )
        
        # Build message history for context
        history_messages = []
        if request.history:
            for h in request.history[-10:]:  # Last 10 exchanges max
                if h.get("role") == "user":
                    history_messages.append(HumanMessage(content=h["content"]))
                elif h.get("role") == "agent":
                    history_messages.append(AIMessage(content=h["content"]))

        if _should_reset_booking(request.message):
            _BOOKING_SESSION.pop(trip_id, None)

        cached = _BOOKING_SESSION.get(trip_id) or {}
        cached_search_results = _SEARCH_SESSION.get(trip_id) or []

        # Prepare input for LangGraph
        initial_state = {
            "messages": history_messages + [HumanMessage(content=request.message)],
            "trip": trip,
            "next_node": None,
            "plan": None,
            "current_step": 0,
            "critique": "",
            "iteration_count": 0,
            "request_iteration_count": 0,
            "current_user_request": request.message,
            "last_agent": None,
            "pending_changes": None,
            "booking_context": cached.get("booking_context"),
            "booking_offers": cached.get("booking_offers"),
            "selected_offer": cached.get("selected_offer"),
            "booking_result": cached.get("booking_result"),
            "search_results": cached_search_results,
        }

        # .ainvoke = asynchronously invoke, i.e. runs until 
        # it hits END or an interrupt
        result = await app.ainvoke(
            initial_state,
            config={"recursion_limit": 50},
        )

        # ── Extract results ──
        final_messages = result.get("messages", [])
        updated_trip = result.get("trip")
        chat_interrupt = result.get("chat_interrupt")

        _BOOKING_SESSION[trip_id] = {
            "booking_context": result.get("booking_context"),
            "booking_offers": result.get("booking_offers"),
            "selected_offer": result.get("selected_offer"),
            "booking_result": result.get("booking_result"),
        }

        if result.get("search_results") is not None:
            search_results = result.get("search_results") or []
            if search_results:
                _SEARCH_SESSION[trip_id] = search_results
            else:
                _SEARCH_SESSION.pop(trip_id, None)
        elif cached_search_results and _looks_like_search_selection(request.message, cached_search_results):
            _SEARCH_SESSION.pop(trip_id, None)

        # Find the last AI message (the response to show the user)
        final_content = "I'm not sure how to help with that."

        for msg in reversed(final_messages):
            if isinstance(msg, AIMessage) and msg.content:
                final_content = msg.content
                break

        # Save updated trip
        if updated_trip:
              # The trip in state might be a Trip object or a dict
            if isinstance(updated_trip, dict):
                updated_trip = Trip(**updated_trip)
            await storage.save_trip(updated_trip)

        # Format response
        user_message = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="user",
            content=request.message,
            timestamp=datetime.now()
        )
        
        agent_message = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="agent",
            content=final_content,
            timestamp=datetime.now()
        )

        interrupt_message = None
        if isinstance(chat_interrupt, dict):
            interrupt_message = ChatMessage(
                id=f"msg_{uuid.uuid4().hex[:8]}",
                type="interrupt",
                content=str(chat_interrupt.get("content") or ""),
                timestamp=datetime.now(),
                interrupt_type=chat_interrupt.get("interrupt_type"),
                options=chat_interrupt.get("options"),
                status=chat_interrupt.get("status"),
            )
        
        # Return both messages + updated trip
        response_messages = [user_message, agent_message]
        if interrupt_message:
            response_messages.append(interrupt_message)

        return ChatResponse(
            messages=response_messages,
            updated_trip=updated_trip,
        )
        
    except HTTPException:
            raise  # Re-raise HTTP errors as-is
    except Exception as e:
        logger.error(f"Error in chat for trip {trip_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)}")


def _should_reset_booking(message: str) -> bool:
    lowered = (message or "").lower()
    keywords = [
        "reset booking",
        "clear booking",
        "reset order",
        "clear order",
        "重置订票",
        "清空订票",
        "重置订单",
        "清空订单",
    ]
    return any(k in lowered for k in keywords)


def _looks_like_search_selection(message: str, search_results: list[dict]) -> bool:
    lowered = (message or "").strip().lower()
    if not lowered or not search_results:
        return False
    if re.fullmatch(r"(?:add\s+)?(?:option\s*)?(?:no\.?\s*)?(\d+)", lowered):
        return True
    match = re.search(r"\b(?:option|no\.?|number)\s*(\d+)\b", lowered)
    if match:
        return True
    return any(str(item.get("name") or "").strip().lower() in lowered for item in search_results if item.get("name"))


# def _generate_mock_response(user_message: str, trip) -> str:
#     """
#     Generate a mock agent response (Phase 1).
#     Phase 2: Replace with LangChain agent.
#     """
#     msg_lower = user_message.lower()
    
#     # Simple keyword-based responses
#     if "hotel" in msg_lower or "accommodation" in msg_lower:
#         return f"Great question! The suggested accommodation is {trip.accommodation.name} at ${trip.accommodation.price_per_night}/night. Would you like me to find alternatives?"
    
#     elif "food" in msg_lower or "restaurant" in msg_lower:
#         food_pois = [poi for day in trip.days for poi in day.pois if poi.category == "Food"]
#         if food_pois:
#             names = ", ".join([poi.name for poi in food_pois[:3]])
#             return f"For food, I've included these spots: {names}. Want more recommendations?"
#         return "Let me find some food spots for you!"
    
#     elif "change" in msg_lower or "replace" in msg_lower:
#         return "Sure! Which location would you like to change? Just tell me the name and what you'd prefer instead."
    
#     elif "budget" in msg_lower or "cost" in msg_lower:
#         total = trip.accommodation.price_per_night * len(trip.days)
#         return f"Based on {len(trip.days)} days at ${trip.accommodation.price_per_night}/night, accommodation will be ~${total}. Food and activities vary, but budget ~$100-150/day for a comfortable trip."
    
#     elif "how many" in msg_lower or "length" in msg_lower:
#         return f"Your trip is {len(trip.days)} days long with {sum(len(day.pois) for day in trip.days)} locations to visit!"
    
#     else:
#         return f"I'm here to help with your {trip.title} trip! Ask me about accommodations, activities, budget, or if you'd like to make changes."
