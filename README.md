# VacayClaw

VacayClaw turns short-form travel videos into a shared trip workspace. A Telegram group and the web app control the same Supabase-backed trip, so users can import videos, edit the itinerary, open media folders, and hand off flight booking before payment.

## What It Does

- Imports TikTok, YouTube, Instagram, Douyin, and Rednote links into one shared workspace.
- Uses Gemini to extract places from media.
- Uses Tavily, Mapbox, and OpenStreetMap to resolve places and images.
- Builds a day-by-day itinerary with map markers, timeline cards, and per-location media folders.
- Syncs Telegram group messages and web chat through the same workspace event log.
- Searches real Trip.com flight options, waits for user selection, and returns a browser handoff before payment.
- Stores trips, workspace state, chat events, and memory in Supabase.

## Requirements

- Python 3.11+
- Node.js 18+
- Supabase project with the tables used by this repo
- API keys for Gemini, Tavily, and Mapbox
- Optional: Telegram bot token and `cloudflared` for group-chat demos

## Install

```bash
git clone https://github.com/pebblepaw/Vacay_UGC-AI-Travel-Planner.git
cd Vacay_UGC-AI-Travel-Planner

python3 -m venv venv
source venv/bin/activate
python -m pip install -r backend/requirements.txt

cd frontend
npm install
cd ..
```

Create `.env` in the repo root. See [docs/brd/env_vars.md](docs/brd/env_vars.md) for the full list.

Minimum local demo keys:

```bash
GEMINI_API_KEY=...
TAVLY_API=...
MAPBOX_PUBLIC=...
MAPBOX_SECRET=...
SUPABASE_PROJECT_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=...
```

Telegram demo keys:

```bash
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
```

## Run Locally

```bash
./start.sh
```

Default URLs:

- Frontend: [http://127.0.0.1:8080](http://127.0.0.1:8080)
- Backend: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

Change ports if needed:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=3000 ./start.sh
```

## Run A Telegram Demo

Telegram needs a public HTTPS webhook. For local demos, use the built-in Cloudflare quick tunnel:

```bash
TELEGRAM_TUNNEL=1 ./start.sh
```

Then:

1. Create a Telegram group.
2. Add `@VacayClawBot`.
3. Send a tagged message, for example `@VacayClawBot plan this trip ...`.
4. The first tagged message creates a Supabase workspace with ID `telegram:{chat_id}:main`.
5. Open the workspace link returned by the bot to control the same trip in the browser.

Use [Sample_Inputs/VacayClaw_test.md](Sample_Inputs/VacayClaw_test.md) for copy-paste demo messages.

## Current Demo Limits

- AWS hosting is paused. The supported demo path is local frontend + local backend + Supabase.
- Cloudflare quick tunnels are good for demos, not stable production URLs.
- Douyin and Rednote can require fresh cookies. Treat that as an external platform blocker.
- Long video imports can exceed Telegram or tunnel request timeouts. The backend may still finish and save the workspace after the visible webhook request times out.
- Trip.com can show CAPTCHA. The accepted behavior is to return the current Trip.com or remote-browser URL and stop before payment.

## Tests

Run the project verification script:

```bash
scripts/codex/verify.sh
```

Useful focused checks:

```bash
source venv/bin/activate
python -m pytest backend/tests/test_telegram_media_ingest.py backend/tests/test_trip_live_handoff.py -q

cd frontend
npm test -- CardsView ChatSidebar TripContext
```

## Project Structure

```text
backend/                 FastAPI backend, agent graph, services, routers
frontend/                React + Vite frontend
config/config.yaml       Model routing and user-facing booking copy
docs/                    Architecture, environment, and handoff docs
Sample_Inputs/           Manual Telegram and web E2E prompts
deploy/                  Docker, Nginx, and worker deployment files
scripts/codex/verify.sh  Local verification script
```

## Main Docs

- [AGENTS.md](AGENTS.md): operating rules for agents working in this repo
- [23_Apr_Report.md](23_Apr_Report.md): implementation plan and current checklist
- [docs/agent_handoff.md](docs/agent_handoff.md): tested paths and known gaps
- [PROGRESS.md](PROGRESS.md): progress log
