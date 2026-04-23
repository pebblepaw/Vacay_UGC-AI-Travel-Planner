```markdown
# Phase 6: UX Polish & Bug Fixes (Completed)

**Status**: ✅ Completed (Feb 2025)

## Context
With the agent stable (Phase 5), this phase addressed 9 UX issues found during live testing.

## Fixes Applied

### 1. Balance POIs Across Days (travel_tool_executor.py)
- **Problem**: `replan_day` dumped all POIs onto a single day.
- **Fix**: Added `_balance_clusters()` to distribute POIs evenly (≤4 per day), creating new days as needed.

### 2. Remove Empty Days After Edits
- **Problem**: Deleting all POIs from a day left an empty day in the itinerary.
- **Fix**: Added cleanup logic in `delete_poi` and `move_poi` to remove days with zero POIs.

### 3. Real Images via DuckDuckGo (travel_tool_executor.py)
- **Problem**: POIs had placeholder/missing images.
- **Fix**: Added `_fetch_image()` using `DDGS().images()` to fetch real photos by POI name + city.

### 4. Thinking Indicator in Frontend (TripContext.tsx)
- **Problem**: No feedback while the agent was processing.
- **Fix**: Inject a "thinking" message (with `isThinking: true`) into the chat while awaiting the API response. Remove it when the response arrives.

### 5. Auto-Refresh After Changes (ChatResponse schema)
- **Problem**: Trip modifications via chat didn't update the map/timeline until page refresh.
- **Fix**: Added `updated_trip: Optional[Trip]` to `ChatResponse`. Frontend's `sendUserMessage` now calls `setTrip(updated_trip)` immediately.

### 6. Travel Time Haversine Fix (travel_tool_executor.py)
- **Problem**: Travel times were all "0 mins" (placeholder).
- **Fix**: Implemented haversine-based distance calculation between consecutive POIs, converted to estimated drive time.

### 7. Map Pin Bounce Animation (MapView.tsx, index.css)
- **Problem**: No visual indication of which POI is selected on the map.
- **Fix**: Added CSS `@keyframes marker-bounce` animation. When a POI is selected (clicked in timeline/cards), its map marker bounces and the map `flyTo`s to center on it.

### 8. Travel Time (0,0) Coord Guard (travel_tool_executor.py)
- **Problem**: "17472 mins drive" between POIs when one had placeholder (0,0) coords. `haversine_km((0,0), (105.8, 21.0))` ≈ 11,648 km.
- **Fix**: Skip travel_time calculation if either POI has (0,0) coords. Cap at "~X hrs drive" for distances > 50 km.

### 9. Removed Duplicate 'map' Tab (ViewTabs.tsx, TripContext.tsx, Index.tsx)
- **Problem**: 'map' and 'timeline' views were functionally identical.
- **Fix**: Removed 'map' from views array. UI now shows only 'timeline' and 'cards' tabs.

## Files Modified
- `backend/agent/nodes/travel_tool_executor.py`
- `backend/models/schemas.py`
- `backend/routers/chat.py`
- `frontend/src/index.css`
- `frontend/src/components/trip/MapView.tsx`
- `frontend/src/components/trip/ViewTabs.tsx`
- `frontend/src/contexts/TripContext.tsx`
- `frontend/src/pages/Index.tsx`

## Tests
- All 5 backend e2e tests passing
- 0 TypeScript errors in all modified frontend files

```
