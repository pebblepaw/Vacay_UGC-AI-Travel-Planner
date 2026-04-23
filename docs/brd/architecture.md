# Architecture & Tech Stack

## Project Structure
```
VACAY/
  .env                          # API keys (NEVER COMMIT)
  config/
    config.yaml                 # Assistant language + role/model mapping
  docs/                         # Documentation (YOU ARE HERE)
    brd/                        # Business requirements
    progress/                   # Phase logs
    architecture/               # Agent architecture detail
  backend/                      # Python FastAPI
    agent/                      # LangGraph agent graph
      graph.py                  # StateGraph + edges
      state.py                  # AgentState TypedDict
      nodes/                    # orchestrator, search, booking, critic, formatter, etc.
      tools/                    # Trip-editing and booking tool schemas
    routers/                    # API Endpoints (chat, trips, videos)
    services/                   # Gemini analyzer, itinerary builder, booking intent, geocoding
      automation/               # Playwright search, checkout, live session registry
    models/                     # Pydantic v2 schemas
    storage/                    # Supabase persistence
    data/booking_artifacts/     # Checkout screenshots and debug artifacts
    tests/                      # pytest-asyncio e2e tests
  frontend/                     # React + Vite
    src/
      components/trip/          # MapView, TimelineView, CardsView, ViewTabs, ChatSidebar
      contexts/                 # TripContext (state management)
      pages/                    # Index (main layout)
      lib/                      # API client
    e2e/                        # Playwright tests
  Sample_Inputs/                # Manual test URLs and prompts
  logs/                         # start.sh runtime logs
```

## Tech Stack
- **Frontend**: React 18, Vite, TailwindCSS, Shadcn UI, Framer Motion, Mapbox GL JS
- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic v2
- **AI/ML**: Gemini or DashScope/Qwen for agent nodes, selected by role in `config/config.yaml`
- **Video Analysis**: `google.genai`
- **Agent**: LangGraph, LangChain Core, provider adapters in `backend/llm.py`
- **Search/Geocoding**: Tavily, Nominatim, Mapbox Geocoding, DDGS
- **Video**: yt-dlp (TikTok/YouTube download)
- **Browser Automation**: Playwright, plus `browser-use` compatibility path
- **Storage**: Supabase Postgres (JSONB in `trips` table)
- **Testing**: pytest-asyncio (backend), Vitest (frontend unit), Playwright (frontend e2e)

## API Endpoints
| Method | Path | Description |
|---|---|---|
| POST | /api/videos/process | Full pipeline: download -> analyze -> build -> save |
| GET | /api/trips/{id} | Retrieve a trip by ID |
| POST | /api/trips/{id}/chat | Chat with the LangGraph agent |

## Runtime Notes
- `start.sh` defaults to backend `8010` and frontend `3000`
- `start.sh` also exports `VITE_MAPBOX_PUBLIC` from `.env`, so the frontend map works without a separate Vite env file
- The booking flow has no separate API route. It runs through `/api/trips/{id}/chat`
- Booking follow-up state is still stored in memory in the chat router

## Key Configuration
- Secrets live in `.env`
- Assistant language, provider preference, and role-to-model mapping live in `config/config.yaml`
- See `docs/brd/env_vars.md` for the full list
