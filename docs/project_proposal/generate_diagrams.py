"""
generate_diagrams.py  —  VACAY Project Proposal Diagrams
Uses gemini-2.5-flash-image to generate clean, white-background, 
cartoon-style architecture diagrams.

Run from project root:
    python docs/project_proposal/generate_diagrams.py
"""

import os
import sys
import base64
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).parent.parent.parent
load_dotenv(ROOT / ".env")

API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not found in .env")
    sys.exit(1)

try:
    from google import genai
    from google.genai import types
except ImportError:
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "google-genai"])
    from google import genai
    from google.genai import types

client = genai.Client(api_key=API_KEY)
OUT_DIR = Path(__file__).parent / "diagrams"
OUT_DIR.mkdir(exist_ok=True)

MODEL = "gemini-2.5-flash-image"

STYLE_PREFIX = (
    "White background. Simple, clean cartoon-style technical diagram. "
    "Thick black outlines on all boxes and arrows. Flat, bold sans-serif labels. "
    "No drop shadows. No gradients. No dark backgrounds. "
    "Nodes are simple rounded rectangles with a single solid pastel fill colour. "
    "Arrows are clean single-headed lines with no overlapping. "
    "Labels on arrows are short (2-4 words max) placed cleanly beside the arrow, never overlapping boxes. "
    "Generous whitespace between nodes so nothing feels crowded. "
    "The overall look should resemble a textbook or hand-drawn diagram, NOT a dark-mode SaaS design. "
)

DIAGRAMS = [
    {
        "filename": "00_user_flow.png",
        "prompt": (
            "White background. Clean cartoon-style flowchart. Thick black outlines on all shapes. "
            "Bold sans-serif labels. No gradients, no shadows. Generous whitespace between elements. "
            "Draw a vertical top-to-bottom flowchart with the following structure: "
            ""
            "At the top: a light blue rounded rectangle labelled 'User pastes TikTok / YouTube URL'. "
            "Arrow pointing down into a large light gray rounded rectangle. "
            "This gray box is labelled 'Itinerary Generator' in bold at the top-left corner of the box. "
            "Inside the gray box, stacked vertically with small downward arrows between them, are 5 steps: "
            "  1. Light blue box: 'yt-dlp downloads video' "
            "  2. Light purple box: 'Gemini 2.0 Flash extracts locations, vibe, priority' "
            "  3. Light teal box: 'Tavily + Nominatim geocodes each place' "
            "  4. Light yellow box: 'Itinerary Builder assembles Trip (days + POIs)' "
            "  5. Light blue box: 'Frontend renders map, timeline and chat' "
            "Arrow pointing down out of the gray box to: "
            "A light orange rounded rectangle labelled 'LangGraph Agent handles edits via natural language'. "
            "Arrow pointing down to: "
            "A light orange rounded rectangle labelled 'Booking Agent searches, ranks and books accommodation'. "
            ""
            "ALL text must fit fully inside its box — make boxes wide enough. "
            "The 5 inner boxes inside the gray group must all be the same width and neatly aligned. "
            "Keep the overall diagram narrow and tall, not wide."
        ),
    },
    {
        "filename": "01_system_architecture.png",
        "prompt": STYLE_PREFIX + (
            "Draw a top-to-bottom system architecture diagram for a travel app called VACAY. "
            "Show these components as labelled boxes connected by arrows: "
            "At the top: a box labelled 'User'. "
            "Arrow down to 'React Frontend' (light blue fill). "
            "Arrow right to 'FastAPI Backend' (light blue fill). "
            "Below FastAPI: a dashed-border group box labelled 'Video Ingestion Pipeline' containing four boxes in a row: "
            "'yt-dlp Downloader' → 'Gemini 2.0 Flash (Video AI)' (light purple fill) → 'Itinerary Builder' → 'Tavily Geocoding' (light teal fill). "
            "Arrow from Geocoding down to 'Supabase Postgres' database (light green fill, cylinder shape). "
            "Arrow from Supabase back up to React Frontend. "
            "Arrow from React Frontend down to 'LangGraph Orchestrator' (light yellow fill). "
            "Arrow from React Frontend down to 'Booking Agent / Playwright' (light orange fill). "
            "Arrow from Booking Agent to 'OTA Sites (Booking.com, Airbnb)' box. "
            "Keep boxes well-spaced. No overlapping arrows."
        ),
    },
    {
        "filename": "02_langgraph_agent_loop.png",
        "reference_image": str(Path(__file__).parent / "sketch_reference.png"),
        "prompt": STYLE_PREFIX + (
            "I have attached a hand-drawn reference sketch. Redraw it as a polished, professional, "
            "cartoon-style technical diagram. "
            "Keep THE EXACT SAME nodes, connections, layout, and arrow directions as in the sketch. "
            "Do NOT add any extra nodes or arrows that are not in the sketch. "
            "Do NOT connect any boxes that are not connected in the sketch. "
            "Spell every label EXACTLY as I write below. "
            ""
            "NODES (top to bottom, use these EXACT labels): "
            "- 'User Message' (light blue fill, at the top) "
            "- 'Orchestrator' (light purple/lavender fill, below User Message) "
            "- 'Travel Agent' (light blue fill, bottom-left of three agents) "
            "- 'ChitChat Agent' (light green/teal fill, centre of three agents) "
            "- 'Search Agent' (light purple fill, bottom-right of three agents) "
            "- 'Tools' (small, light teal fill, to the LEFT of Travel Agent) "
            "- 'Tools' (small, light teal fill, to the RIGHT of Search Agent) "
            "- 'Critic' (light yellow fill, below the three agents) "
            "- 'Output' (light purple fill, below Critic) "
            ""
            "ARROWS (copy these exactly): "
            "1. User Message → Orchestrator (single arrow down) "
            "2. Orchestrator → Travel Agent (arrow down-left) "
            "3. Orchestrator → ChitChat Agent (arrow down) "
            "4. Orchestrator → Search Agent (arrow down-right) "
            "5. Travel Agent ↔ Tools on the left (double-headed horizontal arrow) "
            "6. Search Agent ↔ Tools on the right (double-headed horizontal arrow) "
            "7. Travel Agent ↔ Critic (double-headed arrow, drawn in orange colour) "
            "8. ChitChat Agent → Critic (single arrow down, drawn in orange colour) "
            "9. Search Agent ↔ Critic (double-headed arrow, drawn in orange colour) "
            "10. Critic → Output (single arrow down) "
            "11. Critic → Orchestrator (curved arrow going back up along the right side, drawn in red/pink colour, labelled 'multi-step') "
            ""
            "IMPORTANT RULES: "
            "- The two 'Tools' boxes are SEPARATE — one on the left, one on the right. "
            "- Tools boxes do NOT connect to ChitChat Agent. "
            "- The 'multi-step' label should be beside the curved red arrow from Critic back to Orchestrator. "
            "- All text must fit inside its box. Make boxes large enough. "
            "- No extra nodes, no extra arrows beyond what is listed above. "
        ),
    },
    {
        "filename": "03_booking_agent_workflow.png",
        "prompt": STYLE_PREFIX + (
            "Draw a top-to-bottom flowchart for the VACAY Booking Agent workflow. "
            "Use these nodes in order, connected by downward arrows: "
            "1. Pill box: 'User requests booking'. "
            "2. Rounded rect: 'Receive constraints' with small text 'budget · dates · rating' (light blue fill). "
            "3. Rounded rect: 'Build provider task list' (light blue fill). "
            "4. Rounded rect: 'Playwright browser automation' (light orange fill). "
            "5. Rounded rect: 'Extract candidates: price, policy, rating' (light orange fill). "
            "6. Rounded rect: 'Normalize and rank options' (light purple fill). "
            "7. Three small card boxes side by side: 'Option A', 'Option B', 'Option C' (light grey fill). "
            "8. Diamond decision shape: 'User approves?' (light yellow fill). "
            "YES arrow to the right going to: 'Execute booking (Playwright)' (light green fill). "
            "Then arrow down to: 'Save audit record to Supabase' (light green fill). "
            "NO arrow curved back up to the three option cards. "
            "Keep arrows clean and non-overlapping. Generous whitespace."
        ),
    },
    {
        "filename": "04_data_model.png",
        "prompt": STYLE_PREFIX + (
            "Draw an entity-relationship (ER) diagram for the VACAY travel app database in Supabase Postgres. "
            "Use simple rounded rectangle table cards. Each card has a header row with the table name and rows listing columns. "
            "Place TRIP table in the centre. Arrange other tables around it like spokes of a wheel. "
            "Tables and their columns: "
            "TRIP (light blue header): trip_id PK, title, created_at, user_id FK. "
            "DAY (light blue header): day_number, date, trip_id FK. "
            "POI (light purple header): id PK, name, category, lng, lat, time_slot, vibe, priority, intensity, visit_duration_mins. "
            "SOURCE_VIDEO (light teal header): platform, url, title, trip_id FK. "
            "ACCOMMODATION (light green header): id PK, provider, name, price_per_night, booking_ref, trip_id FK. "
            "BOOKING_AUDIT (light orange header): id PK, agent, action, outcome, timestamp, trip_id FK. "
            "CHAT_MESSAGE (light grey header): id PK, type, content, timestamp, trip_id FK. "
            "Draw simple clean lines with crow's foot notation between TRIP and each related table. "
            "Relationships: TRIP one-to-many DAY, DAY one-to-many POI, TRIP one-to-many SOURCE_VIDEO, "
            "TRIP one-to-one ACCOMMODATION, TRIP one-to-many CHAT_MESSAGE, TRIP one-to-many BOOKING_AUDIT. "
            "Place tables so that connector lines do not cross each other. Generous whitespace."
        ),
    },
]


def generate_diagram(diagram: dict) -> bool:
    print(f"Generating: {diagram['filename']}...")
    try:
        # Build contents: optional reference image + text prompt
        contents = []
        ref_path = diagram.get("reference_image")
        if ref_path and Path(ref_path).exists():
            img_bytes = Path(ref_path).read_bytes()
            contents.append(types.Part.from_bytes(data=img_bytes, mime_type="image/png"))
            print(f"  📎 Attached reference image: {ref_path}")
        contents.append(diagram["prompt"])

        response = client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                response_modalities=["TEXT", "IMAGE"],
            ),
        )

        for part in response.candidates[0].content.parts:
            if hasattr(part, "inline_data") and part.inline_data:
                out_path = OUT_DIR / diagram["filename"]
                with open(out_path, "wb") as f:
                    f.write(part.inline_data.data)
                print(f"  ✅ Saved → {out_path}")
                return True

        # No image found in response
        text = ""
        for part in response.candidates[0].content.parts:
            if hasattr(part, "text") and part.text:
                text += part.text
        print(f"  ❌ No image in response. Text: {text[:300]}")
        return False

    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


if __name__ == "__main__":
    print(f"Model: {MODEL}")
    print(f"Output: {OUT_DIR}\n")
    results = [generate_diagram(d) for d in DIAGRAMS]
    ok = sum(results)
    print(f"\n{'='*40}")
    print(f"Done: {ok}/{len(DIAGRAMS)} diagrams generated.")
