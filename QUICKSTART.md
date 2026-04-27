# VacayClaw Quick Start

Use this path for the local demo. It runs the frontend and backend on your machine and stores state in Supabase.

## 1. Install Prerequisites

Install:

- Python 3.11+
- Node.js 18+
- `cloudflared` only if you want Telegram to reach your local backend

macOS example:

```bash
brew install python node cloudflared
```

## 2. Install The App

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

## 3. Create `.env`

Create `.env` in the repo root.

```bash
GEMINI_API_KEY=...
TAVLY_API=...
MAPBOX_PUBLIC=...
MAPBOX_SECRET=...
SUPABASE_PROJECT_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SECRET_KEY=...

# Optional Telegram demo
TELEGRAM_BOT_TOKEN=...
TELEGRAM_WEBHOOK_SECRET=...
```

See [docs/brd/env_vars.md](docs/brd/env_vars.md) for all supported settings.

## 4. Start The Local Web Demo

```bash
./start.sh
```

Open:

- Frontend: [http://127.0.0.1:8080](http://127.0.0.1:8080)
- Backend health: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

If ports are busy:

```bash
BACKEND_PORT=8010 FRONTEND_PORT=3000 ./start.sh
```

## 5. Start The Telegram Demo

Telegram cannot call `localhost`. Start a tunnel and register the webhook:

```bash
TELEGRAM_TUNNEL=1 ./start.sh
```

The script starts:

- backend
- frontend
- Cloudflare quick tunnel
- Telegram webhook at `{tunnel_url}/api/telegram/webhook`

Then:

1. Create a Telegram group.
2. Add `@VacayClawBot`.
3. Send a tagged message from [Sample_Inputs/VacayClaw_test.md](Sample_Inputs/VacayClaw_test.md).
4. Wait for the workspace link.
5. Open the link in the browser to see the same workspace.

The first message in a new group creates a Supabase workspace automatically. The workspace ID is `telegram:{chat_id}:main`.

## 6. Manual E2E Script

Use [Sample_Inputs/VacayClaw_test.md](Sample_Inputs/VacayClaw_test.md).

Recommended order:

1. Send Step 1 in Telegram to import media and create the trip.
2. Open the returned workspace link.
3. Send one later step from the web chat to confirm web-to-Telegram sync.
4. Continue Steps 2-5 in Telegram.
5. For booking, ask for flights first, then reply with `Option 1`, `Option 2`, or a similar selection.

Expected booking behavior:

- The bot returns flight options first.
- The bot does not auto-book.
- After selection, the bot opens Trip.com.
- If Trip.com asks for traveler details or CAPTCHA, the bot returns the current handoff URL.
- Stop before payment.

## 7. Troubleshooting

### The bot does not reply

Check that `TELEGRAM_TUNNEL=1 ./start.sh` is still running. Then open the backend log:

```bash
tail -f logs/backend.log
```

If the log shows downloads or Gemini analysis, keep waiting. Long media imports can take several minutes.

### Telegram sends duplicate replies

Telegram retries long webhook calls. If a media import takes too long, the backend may receive the same update more than once. Wait for the first run to finish before resending.

### Douyin or Rednote fails

Some links require fresh platform cookies. Use TikTok or YouTube links for the demo if cookies are blocked.

### Map is blank

Check `MAPBOX_PUBLIC` and restart `./start.sh`.

### Booking returns CAPTCHA

That is acceptable for the demo. Open the returned URL and stop before payment.

## 8. Verification

Run the repo verification script before shipping changes:

```bash
scripts/codex/verify.sh
```

Run focused tests while debugging:

```bash
source venv/bin/activate
python -m pytest backend/tests/test_booking_agent.py backend/tests/test_trip_live_handoff.py -q

cd frontend
npm test -- CardsView ChatSidebar TripContext
```
