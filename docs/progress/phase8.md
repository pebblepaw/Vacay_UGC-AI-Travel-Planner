# Phase 8: Booking Automation, Runtime Config, and Stabilization

**Status**: ✅ Core work merged to `main` (April 2026)  
**Caveat**: One search/critic sub-phase was implemented, then rolled back.

## What Landed

### 1. Config-Driven Runtime
- Added `config/config.yaml`
- Moved assistant language, provider preference, and role-to-model mapping out of hard-coded Python
- `backend/app_config.py` now loads user-editable runtime config
- `backend/llm.py` now resolves Gemini vs DashScope/Qwen by role

### 2. Video Import Hardening
- Migrated video analysis from the deprecated Gemini SDK to `google.genai`
- Stopped silently saving empty trips when video analysis fails
- Tightened geocoding:
  - 20-second budget per location
  - capped Tavily candidate count
  - junk candidate filtering
  - broader China and Shanghai scope matching
  - unresolved places are dropped instead of saved with `(0, 0)`

### 3. Playwright Booking Flow
- Added a booking agent and booking tool executor to the LangGraph graph
- Added LLM-based booking intent normalization in `backend/services/booking_intent.py`
- Added live Trip.com flight search through Playwright in `backend/services/automation/browser_use_worker.py`
- Added checkout handoff through `backend/services/automation/playwright_checkout.py`
- Added live browser session reuse through `live_booking_sessions.py`
- The user can now pick an offer, then continue in a visible Playwright browser window
- The flow stops before final payment

### 4. Frontend and Runtime Support
- `start.sh` now defaults to backend `8010` and frontend `3000`
- `start.sh` writes backend and frontend logs to `logs/`
- `start.sh` exports the Mapbox frontend token so the map renders in local runs

## What Did Not Stick

One sub-phase was the right idea, but the wrong implementation.

- **Implemented in** `520e878` — `Fix search result handoff and critic request cap`
- **Reverted in** `1e249d4` — `Revert search result handoff and critic request cap`

That experiment tried to:
- pause after search and show structured POI options first
- cache search results between turns
- create the add step only after the user picked one result
- make the critic judge the current user request
- add a request-level critic cap

It broke other flows. The code was rolled back.

## Current Mainline Behavior After The Rollback
- Search results are still returned as agent text, not as a durable selection state
- Follow-up selection still depends on prompt context
- The critic still reads the first human message in the conversation
- The critic cap is still a simple loop cap, now `2`

## What To Rebuild Later
1. Rebuild search-result selection with structured state, not prompt scraping
2. Add durable current-request state for the critic
3. Add a real request-level critic cap
4. Back the selection and booking caches with shared persistence, not in-process memory

## Files You Will Open For This Phase
- `config/config.yaml`
- `backend/app_config.py`
- `backend/llm.py`
- `backend/services/gemini_analyzer.py`
- `backend/services/tavily_location.py`
- `backend/services/itinerary_builder.py`
- `backend/services/booking_intent.py`
- `backend/services/automation/browser_use_worker.py`
- `backend/services/automation/playwright_checkout.py`
- `backend/agent/nodes/booking_agent.py`
- `backend/agent/nodes/booking_tool_executor.py`
- `backend/routers/chat.py`
