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

**Last Updated**: Not started yet

**Current Phase**: Phase 1 - Backend Foundation

**Next Task**: Task 1.1 - Python Environment Setup

**Blockers**: None

---

## 📝 Progress Entries

> Append new entries below. Never delete old entries.

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
