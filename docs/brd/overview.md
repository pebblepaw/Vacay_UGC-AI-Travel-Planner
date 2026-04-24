# VACAY - Project Overview

**VACAY** turns short-form travel videos into structured travel itineraries, then lets the user edit and book parts of the trip in chat.

## User Flow
1. **User** pastes TikTok URL
2. **Backend** downloads video (yt-dlp)
3. **Gemini via `google.genai`** extracts locations, place scope, vibe, and visit metadata
4. **Tavily/Nominatim/Mapbox** resolve places and reject out-of-scope matches
5. **Itinerary Builder** organizes POIs into days (<=4 per day, balanced)
6. **Frontend** displays interactive Mapbox map + timeline/cards views
7. **Chat Agent** (LangGraph) edits the trip, searches for new places, or starts booking
8. **Booking Agent** can search Trip.com flights, ask for missing details, and hand the user to a live Playwright browser window before payment

## Features
- Video-to-itinerary pipeline (TikTok URL -> structured trip)
- Interactive map with colored category markers + bounce animation on selection
- Timeline view with drag-and-drop reordering
- Cards view for quick browsing
- AI chat: add, delete, swap, move POIs; replan days; optimize routes; search for new places
- Meal-aware place search that can anchor lunch or dinner near the right part of the day
- Real images fetched via DuckDuckGo
- Haversine-based travel time estimates between POIs
- Thinking indicator during agent processing
- Auto-refresh map/timeline after chat modifications
- Config-driven assistant language and role-to-model mapping through `config/config.yaml`
- Live Trip.com flight search and checkout handoff through Playwright

## Booking Scope
- The strongest live path today is **Trip.com flights**.
- The schema mentions trains, hotels, and attractions, but those paths do not have the same live Playwright coverage yet.
- VACAY stops before final payment. The user finishes payment in the booking site.

## Current State
- Phase 8 work is on `main`
- Supabase is the live trip store
- Video analysis uses `google.genai`
- Chat models are selected by role and provider through YAML config
- Search-result interrupt state and request-level critic state were prototyped, then rolled back. They need a cleaner second pass.
