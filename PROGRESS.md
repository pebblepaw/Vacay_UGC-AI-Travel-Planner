# VACAY Development Progress Log

> **READ THIS FILE FIRST** before starting any work.  
> This file tracks all progress, learnings, and patterns discovered during development.

---

## 📚 Codebase Patterns

> **IMPORTANT**: Read these patterns before making any changes. Add new patterns here as you discover them.

### Project Structure
- Frontend is in `/frontend` (React + Vite + Shadcn)
- Backend is in `/backend` (Python FastAPI)
- API keys are in `/.env` at project root (NEVER commit)
- Downloaded videos go to `/downloads` (gitignored)
- Trip data saved to `/backend/data/trips/*.json`

### Frontend Patterns
- Uses Shadcn UI components in `frontend/src/components/ui/`
- Custom trip components in `frontend/src/components/trip/`
- Global state via React Context in `frontend/src/contexts/TripContext.tsx`
- Mock data structure defined in `frontend/src/data/mockData.ts` - **match this structure in backend**
- Uses Framer Motion for animations
- Uses TanStack Query for data fetching

### Backend Patterns
- Config loaded from parent `.env` file via `backend/config.py`
- Services are in `backend/services/` - one file per external API
- API routes in `backend/routers/`
- Pydantic models in `backend/models/schemas.py`
- Tests use pytest with markers: `@pytest.mark.slow` for network tests, `@pytest.mark.api` for API-calling tests

### Styling
- Tailwind CSS with custom colors defined in `tailwind.config.ts`
- Category colors: Food=orange, Art=purple, Nature=green, Culture=amber, Shopping=pink, Nightlife=indigo
- Use `gradient-bg` class for primary gradient buttons
- Use `glass` class for glassmorphism effects

### API Conventions
- All endpoints prefixed with `/api/`
- Video processing: `POST /api/videos/process`
- Trip CRUD: `GET/POST/DELETE /api/trips/{trip_id}`
- Chat: `POST /api/trips/{trip_id}/chat`
- Always return proper error details in HTTPException

### Testing
- Backend: `cd backend && python -m pytest tests/ -v`
- Skip slow tests: `python -m pytest -m "not slow"`
- Frontend: `cd frontend && npm test`

### Git Workflow
- Commit after each task with message format: `feat: X.X - Description`
- Always push to `main` branch
- Update this PROGRESS.md after each commit

---

## 🔄 Current Status

**Last Updated**: January 31, 2025

**Current Phase**: Phase 3 - Frontend Integration (Task 3.1 completed)

**Next Task**: Task 3.2 - Update TripContext to fetch real data

**Blockers**: None

**Completed Tasks**: ✅ 1.1-1.8, 2.1-2.4, 3.1 (11/14 tasks complete)

---

## 📝 Progress Entries

> Append new entries below. Never delete old entries.

---

## [2025-01-31] - Phase 1: Backend Foundation Complete (Tasks 1.1-1.8)

**Status**: ✅ Completed

**What was implemented:**
- Task 1.1: Python environment with venv and all dependencies
- Task 1.2: Configuration module loading from .env with pydantic-settings
- Task 1.3: Pydantic models matching frontend TypeScript interfaces exactly
- Task 1.4: Video downloader service using yt-dlp for TikTok/YouTube/Douyin/RedNote
- Task 1.5: Gemini analyzer service for video content analysis with Gemini 1.5 Pro
- Task 1.6: Tavily location service for geocoding with Nominatim fallback
- Task 1.7: Itinerary builder service to create Trip objects from analysis
- Task 1.8: Local JSON storage service for Phase 1

**Files created:**
- backend/config.py
- backend/models/schemas.py
- backend/services/video_downloader.py
- backend/services/gemini_analyzer.py
- backend/services/tavily_location.py
- backend/services/itinerary_builder.py
- backend/storage/local_storage.py
- backend/requirements.txt

**Tests:**
- [x] All services import correctly
- [x] Config loads from .env successfully
- [x] Required directories created automatically

**Learnings:**
- pydantic-settings requires `extra = "ignore"` to handle extra .env keys (like SUPABASE for Phase 2)
- google.generativeai shows deprecation warning - consider migrating to google.genai in future
- Coordinates MUST be tuple[float, float] to match frontend [lng, lat] format
- Use Unsplash Source API for placeholder images (no key needed)

**Commits**: feat: 1.1 through feat: 1.8

---

## [2025-01-31] - Phase 2: API Endpoints Complete (Tasks 2.1-2.4)

**Status**: ✅ Completed

**What was implemented:**
- Task 2.1: Video processing endpoint with full pipeline (download → analyze → build → save)
- Task 2.2: Trip CRUD endpoints (GET list, GET by ID, DELETE)
- Task 2.3: FastAPI main app with CORS middleware for frontend
- Task 2.4: Chat endpoint with mock responses (Phase 1)

**Files created:**
- backend/main.py
- backend/routers/videos.py
- backend/routers/trips.py
- backend/routers/chat.py

**Tests:**
- [x] FastAPI app starts successfully
- [x] All routes registered correctly
- [x] CORS allows localhost:5173 and localhost:3000

**Learnings:**
- Use BackgroundTasks for video cleanup to avoid blocking response
- HTTPException needs to be re-raised in try/except blocks
- CORS must include both Vite ports (5173 default, 3000 alternative)
- Chat uses simple keyword matching for Phase 1, will need LangChain for Phase 2

**Commits**: feat: 2.1-2.3, feat: 2.4

---

## [2025-01-31] - Phase 3: Frontend Integration Started (Task 3.1)

**Status**: ✅ Completed

**What was implemented:**
- Task 3.1: API client in frontend/src/lib/api.ts with all endpoints
- Updated AddUrlModal to call real backend API
- Added error handling and toast notifications
- Created frontend/.env for VITE_API_URL configuration

**Files created/modified:**
- frontend/src/lib/api.ts (new)
- frontend/.env (new)
- frontend/src/components/trip/AddUrlModal.tsx (updated)

**Tests:**
- [x] API client functions defined
- [x] AddUrlModal imports processVideos correctly

**Learnings:**
- Vite uses VITE_ prefix for environment variables (not REACT_APP_)
- Use useToast hook from shadcn for user feedback
- Redirect to /trip/{trip_id} after successful video processing
- Frontend .env already in .gitignore (safe)

**Commit**: feat: 3.1

---

### Template for New Entries

```
## [Date] - Task X.X: [Task Name]

**Status**: ✅ Completed / 🚧 In Progress / ❌ Blocked

**What was implemented:**
- List of changes made

**Files changed:**
- path/to/file1.py
- path/to/file2.tsx

**Tests:**
- [ ] Test 1 passed
- [ ] Test 2 passed

**Learnings for future iterations:**
- Pattern discovered: "..."
- Gotcha: "..."
- Useful context: "..."

**Commit**: `feat: X.X - Description`

---
```

---

## 📋 Quick Reference

### Test URLs (from Sample_Inputs/TikTok-Links.md)
```
25 sec video:    https://www.tiktok.com/@roadynz/video/7440193649578659090
Restaurant:      https://www.tiktok.com/@miaandtheworld/video/7506102845653962002
Photo slides:    https://www.tiktok.com/@christinaelle_/photo/7544978045929622792
2.5 min video:   https://www.tiktok.com/@ashlinpria/video/7595259514400673055
```

### Common Commands
```bash
# Activate Python venv
source venv/bin/activate

# Start backend
cd backend && uvicorn main:app --reload --port 8000

# Start frontend
cd frontend && npm run dev

# Run backend tests
cd backend && python -m pytest tests/ -v

# Git commit and push
git add -A && git commit -m "feat: X.X - Description" && git push origin main
```

### API Endpoints (when backend is running)
```
Health:     GET  http://localhost:8000/health
Process:    POST http://localhost:8000/api/videos/process
Trips:      GET  http://localhost:8000/api/trips/
Trip:       GET  http://localhost:8000/api/trips/{id}
Chat:       POST http://localhost:8000/api/trips/{id}/chat
```

---

## ⚠️ Known Issues

> Document any known issues, workarounds, or technical debt here.

*(None yet)*

---

## 💡 Ideas for Future

> Capture ideas that are out of scope for MVP but worth remembering.

- YouTube Shorts support
- Rednote/Xiaohongshu support  
- Batch URL processing
- Supabase integration for persistence
- User authentication
- Duffel booking integration
- LangGraph for complex AI workflows
