"""
FastAPI routers for chat/AI agent interactions.
Handles chat messages and agent responses (Phase 1: Mock responses).
"""
from fastapi import APIRouter, HTTPException
from datetime import datetime
import logging
import uuid

from backend.models.schemas import ChatRequest, ChatResponse, ChatMessage
from backend.storage.local_storage import local_storage

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/trips", tags=["chat"])


@router.post("/{trip_id}/chat", response_model=ChatResponse)
async def send_chat_message(trip_id: str, request: ChatRequest):
    """
    Send a chat message and get AI agent response.
    
    Phase 1: Returns mock responses
    Phase 2: Will integrate with LangChain agent
    
    Args:
        trip_id: Trip identifier
        request: Chat message from user
        
    Returns:
        List of chat messages (user + agent response)
    """
    try:
        # Verify trip exists
        trip = await local_storage.load_trip(trip_id)
        if not trip:
            raise HTTPException(
                status_code=404,
                detail=f"Trip '{trip_id}' not found"
            )
        
        # Create user message
        user_message = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="user",
            content=request.message,
            timestamp=datetime.now()
        )
        
        # Generate mock agent response
        agent_response = _generate_mock_response(request.message, trip)
        
        agent_message = ChatMessage(
            id=f"msg_{uuid.uuid4().hex[:8]}",
            type="agent",
            content=agent_response,
            timestamp=datetime.now()
        )
        
        # Return both messages
        return ChatResponse(messages=[user_message, agent_message])
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in chat for trip {trip_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Chat error: {str(e)}"
        )


def _generate_mock_response(user_message: str, trip) -> str:
    """
    Generate a mock agent response (Phase 1).
    Phase 2: Replace with LangChain agent.
    """
    msg_lower = user_message.lower()
    
    # Simple keyword-based responses
    if "hotel" in msg_lower or "accommodation" in msg_lower:
        return f"Great question! The suggested accommodation is {trip.accommodation.name} at ${trip.accommodation.price_per_night}/night. Would you like me to find alternatives?"
    
    elif "food" in msg_lower or "restaurant" in msg_lower:
        food_pois = [poi for day in trip.days for poi in day.pois if poi.category == "Food"]
        if food_pois:
            names = ", ".join([poi.name for poi in food_pois[:3]])
            return f"For food, I've included these spots: {names}. Want more recommendations?"
        return "Let me find some food spots for you!"
    
    elif "change" in msg_lower or "replace" in msg_lower:
        return "Sure! Which location would you like to change? Just tell me the name and what you'd prefer instead."
    
    elif "budget" in msg_lower or "cost" in msg_lower:
        total = trip.accommodation.price_per_night * len(trip.days)
        return f"Based on {len(trip.days)} days at ${trip.accommodation.price_per_night}/night, accommodation will be ~${total}. Food and activities vary, but budget ~$100-150/day for a comfortable trip."
    
    elif "how many" in msg_lower or "length" in msg_lower:
        return f"Your trip is {len(trip.days)} days long with {sum(len(day.pois) for day in trip.days)} locations to visit!"
    
    else:
        return f"I'm here to help with your {trip.title} trip! Ask me about accommodations, activities, budget, or if you'd like to make changes."
