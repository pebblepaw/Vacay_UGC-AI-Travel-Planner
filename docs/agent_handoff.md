# Agent Handoff Protocol

VACAY is an AI travel planner that turns short travel videos into editable trips, then helps with search and booking in chat.

## Current Status
- **Phase 8 work is merged to `main`.**
- **Frontend**: React app with Mapbox, trip views, and chat.
- **Backend**: FastAPI + LangGraph multi-agent graph.
- **Booking**: Live Trip.com flight discovery and checkout handoff through a visible Playwright browser window. The app stops before final payment.
- **Storage**: Trips live in Supabase. Booking follow-up state still lives in backend memory.

## Read This First
Documentation lives in `docs/`. `BRD.md` is only the index.

### Required Reading
1. `docs/brd/overview.md`
2. `docs/brd/architecture.md`
3. `docs/architecture/agent_architecture.md`
4. `docs/progress/phase8.md`

### Useful Follow-Ups
- `docs/progress/phase7.md` — Supabase migration details
- `docs/progress/phase5.md` — original plan-and-execute rebuild
- `docs/brd/env_vars.md` — runtime setup
- `docs/brd/test_data.md` — manual test inputs

## Tech Stack
- **Frontend**: React, Vite, TailwindCSS, Shadcn UI, Framer Motion, Mapbox GL JS
- **Backend**: Python 3.11, FastAPI, Uvicorn, Pydantic v2
- **LLMs**: Gemini or DashScope/Qwen, chosen by `config/config.yaml`
- **Video analysis**: `google.genai`
- **Agent runtime**: LangGraph + LangChain Core
- **Search and geocoding**: Tavily, Nominatim, Mapbox Geocoding, DDGS
- **Browser automation**: Playwright, with `browser-use` as an optional compatibility path
- **Storage**: Supabase Postgres with JSONB trip blobs
- **Python venv**: `/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/venv`

## What Is Stable
- Video import from TikTok and similar short-form links
- Scope-aware location filtering during import
- Supabase-backed trip load/save
- Chat-based trip editing
- Config-driven assistant language and role-to-model mapping
- Live Trip.com flight search and checkout handoff to a visible Playwright window

## What Is Still Fragile
1. **Search follow-up selection is not durable.** The agent can search and list places, but the clean structured “show options, then add only after selection” flow was rolled back. Today the follow-up still depends on prompt context and free-text interpretation.
2. **Critic state is still too simple.** The current critic uses the first human message in the conversation, not a durable current-request field. The cap is a simple loop cap, now set to `2`, not a real request-level cap.
3. **Booking is flight-first and Trip.com-first.** The schema mentions trains, hotels, and attractions, but the live automation path is strongest for Trip.com flights.
4. **Checkout deep links are uneven.** Some fares still depend on a live results-page browser session instead of a clean reusable booking URL.
5. **Booking state is process-local.** `_BOOKING_SESSION` in `backend/routers/chat.py` is not shared across machines or backend instances.
6. **Verbose node logging is still on by default.** Many nodes log `>>> NODE entered`.

## Rolled-Back Work You Should Know About
One sub-phase was implemented, then reverted because it broke other behavior.

- **Implemented in** `520e878` — `Fix search result handoff and critic request cap`
- **Reverted in** `1e249d4` — `Revert search result handoff and critic request cap`

That experiment tried to:
- pause after search and show structured POI options first
- cache search results between turns
- create the add step only after the user picked a result
- make the critic judge the current request instead of the first human message
- add a request-level critic cap

The direction was right. The implementation was not. Rebuild it later with durable state and better end-to-end tests.

## Tests
- **Backend**: pytest suites cover video import, booking, search, response formatting, Supabase, and live booking handoff.
- **Frontend**: vitest for UI helpers and components.
- **Manual live tests**: `start.sh` plus Playwright-backed Trip.com search and checkout handoff.

## Next Recommended Work
1. Re-implement the rolled-back search-result selection flow with durable state, not prompt scraping.
2. Move booking follow-up state from in-memory cache to shared persistence.
3. Add user auth and scoped RLS policies.
4. Tighten the Trip.com handoff so every selected fare reaches a stable traveler page.
