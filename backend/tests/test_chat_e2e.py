import pytest
import json
import time
from pathlib import Path
from playwright.sync_api import Page, expect

# Constants
MOCK_TRIP_ID = "test_chat_123"
TRIPS_DIR = Path("backend/data/trips")

@pytest.fixture(scope="function", autouse=True)
def setup_mock_trip():
    """Injects a mock trip into the backend storage."""
    TRIPS_DIR.mkdir(parents=True, exist_ok=True)
    
    trip_data = {
        "trip_id": MOCK_TRIP_ID,
        "title": "Test Chat Trip",
        "source_videos": [
            {"platform": "youtube", "url": "http://test.com", "title": "Test Video"}
        ],
        "days": [
            {
                "day_number": 1,
                "date": "2024-01-01",
                "pois": [
                    {
                        "id": "p1", 
                        "name": "The Bund", 
                        "category": "Culture", 
                        "coords": [121.48, 31.23], 
                        "img": "https://placehold.co/600x400", 
                        "time_slot": "09:00 - 10:00", 
                        "vibe": "Historic",
                        "priority": "high",
                        "intensity": "normal",
                        "visit_duration": 60
                    }
                ]
            }
        ],
        "accommodation": {
            "name": "Peace Hotel",
            "price_per_night": 300,
            "status": "Found",
            "img": "https://placehold.co/600x400",
            "coords": [121.48, 31.24]
        }
    }
    
    file_path = TRIPS_DIR / f"{MOCK_TRIP_ID}.json"
    with open(file_path, "w") as f:
        json.dump(trip_data, f)
        
    yield

def test_chat_interaction(page: Page):
    # 1. Open App directly to trip
    page.goto(f"http://localhost:8080/?trip={MOCK_TRIP_ID}")
    print(f"Page Title: {page.title()}")
    
    # 2. Verify Trip Loaded
    # Expect trip content to be visible (e.g. Header)
    # page.get_by_text("Test Chat Trip") might be in the header title
    expect(page.get_by_text("Test Chat Trip").first).to_be_visible(timeout=15000)
    
    # 3. Open Chat (Floating Button)
    # The button is fixed bottom-6 right-6
    # It might take a moment to appear
    chat_btn = page.locator("button.fixed.bottom-6.right-6")
    expect(chat_btn).to_be_visible(timeout=5000)
    chat_btn.click()
    
    # 4. Check Input
    chat_input = page.get_by_placeholder("Ask anything about your trip...")
    expect(chat_input).to_be_visible()
    
    # 5. Send Message
    chat_input.fill("Hello, finding any errors?")
    # Send button is next to input with Send icon
    page.locator("button:has(svg.lucide-send)").click()
    
    # 6. Verify Response
    # Wait for a bot message (Bot icon)
    # The user message appears immediately (User icon)
    # The bot message appears after API call
    
    # We can check for the Bot icon appearing in the message list
    # Initially there might be 0 or 1 (welcome message?) 
    # Let's count them or wait for new text.
    
    # Wait for *any* text response that is not our own
    expect(page.locator("svg.lucide-bot").last).to_be_visible(timeout=30000)
    
    # Optional: Print the text for debugging
    # The text is in a sibling div to the icon container
    # .flex.items-end.gap-2 > div.bg-secondary > p
    last_bot_msg = page.locator("div.bg-secondary p").last
    print(f"Bot says: {last_bot_msg.text_content()}")
    
    # Ensure it's not empty
    expect(last_bot_msg).not_to_be_empty()
