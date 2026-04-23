```markdown
# Phase 7: Supabase Migration (Completed)

**Status**: ✅ Completed (Feb 2025)

## Context
Migrated from local JSON file storage to Supabase Postgres. All trip data now lives in a `trips` table with JSONB storage. Added a placeholder trip that auto-seeds when the database is empty.

## What Changed

### Database Schema
- **Table**: `trips` (id TEXT PK, title TEXT, data JSONB, created_at, updated_at)
- **Index**: `idx_trips_updated_at` for fast "most recent" queries
- **Trigger**: `trips_updated_at` auto-updates the `updated_at` column on every write
- **RLS**: Enabled with "allow all" policy (Phase 8: add user auth + scoped policies)

### Backend Changes
- **New**: `backend/storage/supabase_storage.py` — `SupabaseStorageService` with same interface as `LocalStorageService`
- **Modified**: `backend/config.py` — Added `SUPABASE_PROJECT_URL` and `SUPABASE_SECRET_KEY` to settings
- **Modified**: `backend/routers/trips.py`, `chat.py`, `videos.py` — Switched imports from `local_storage` to `supabase_storage`
- **Modified**: `backend/main.py` — Added `@app.on_event("startup")` to seed placeholder trip
- **Added**: `supabase>=2.0.0` to `requirements.txt`

### Frontend Changes
- **Modified**: `frontend/src/contexts/TripContext.tsx` — When no `?trip=` param, auto-loads most recent trip from Supabase via `listTrips()`. Falls back to `sampleTrip` if backend is unavailable.

### Placeholder Trip
- On server startup, if the `trips` table is empty, a "Welcome to VACAY!" placeholder trip is seeded with 3 Paris POIs (Eiffel Tower, Louvre Museum, Café de Flore).
- This ensures the map always has something to display on first launch.
- The placeholder is a real trip in Supabase and can be chatted with.

## Files Modified
- `backend/requirements.txt`
- `backend/config.py`
- `backend/storage/supabase_storage.py` (new)
- `backend/routers/trips.py`
- `backend/routers/chat.py`
- `backend/routers/videos.py`
- `backend/main.py`
- `backend/tests/test_supabase.py` (new)
- `frontend/src/contexts/TripContext.tsx`

## Tests
- 8 Supabase storage tests: save, load, load_nonexistent, upsert, list, delete, exists, placeholder seeding — ALL PASSING
- 5 agent e2e tests: greeting, delete, move, optimize, replan — ALL PASSING (verified Supabase integration doesn't break agent)

## Environment Variables Added
```
SUPABASE_PROJECT_URL = "https://xmubadcfzpnjssppbofm.supabase.co"
SUPABASE_SECRET_KEY = "..."
```

```
