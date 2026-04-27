# Agent Handoff Protocol

VacayClaw is now a **workspace-first collaborative travel runtime**. Use this file plus `AGENTS.md` and `23_Apr_Report.md` as operating context.

## Current Status (2026-04-27)

- Backend supports workspace-scoped routing at `/api/workspaces/*` with shared event logs, runtime state, and signed web handoff.
- Telegram webhook ingestion works at `/api/telegram/webhook`, keyed by `chat_id + message_thread_id`, sends outbound replies back into the Telegram group, ignores duplicate `update_id` deliveries, and ignores edited messages.
- Frontend supports workspace mode via `/?workspace=<id>&token=<signed-token>`.
- Workspace snapshots drive the shared web chat, the map, and media folders by place.
- The active demo path is local frontend + local backend + Supabase. AWS work is paused.
- Meal insertion now checks the saved itinerary after replanning, so the bot stops claiming success when the new food stop gets dropped.
- Trip.com booking now returns real options, waits for user selection, and treats CAPTCHA as a valid handoff by returning the current Trip.com URL.
- Rednote short links from `xhslink.com` now flow through the same shared ingest path as full Rednote URLs.
- The branch is still not cleanly done. It still needs one fresh full Telegram E2E run on this exact commit.

## Source of Truth

1. `AGENTS.md`
2. `23_Apr_Report.md`

Other docs may lag and should be treated as historical unless updated in the same commit series.

## New Runtime Components

- `backend/services/workspace_runtime.py`
  - workspace ID generation (`telegram:{chat_id}:{thread_id|main}`)
  - event log persistence with in-memory fallback
  - workspace/user memory persistence with in-memory fallback
  - runtime booking state persistence (replaces `_BOOKING_SESSION` cache)
  - signed share token generation and validation
  - workspace snapshot derivation
- `backend/routers/workspaces.py`
  - workspace chat endpoint
  - workspace snapshot endpoint
  - workspace share-link endpoint
  - workspace media merge ingestion endpoint
- `backend/routers/telegram.py`
  - webhook ingestion and workspace dispatch

## Deployment Artifacts

- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `frontend/nginx.conf`
- `deploy/nginx/default.conf`
- demo script: `scripts/demo/run_workspace_demo.sh`

## What Was Tested

### Ran

- Frontend production build.
- Focused backend tests for:
  - async LangGraph Postgres checkpointer setup
  - empty-shell workspace import replacement
  - booking-intent non-booking short-circuit
  - booking-intent fallback parsing when the LLM is unavailable
  - Telegram duplicate-delivery handling
  - Telegram edited-message ignore path
  - meal insertion truthfulness after replanning
  - signed browser handoff and takeover recovery
  - live booking handoff regression coverage
  - Rednote `xhslink.com` detection in backend and frontend
- Live Telegram webhook roundtrip for:
  - initial Sydney itinerary build
  - trip resize to 2 days
- Live local Telegram Step 5:
  - returned real Trip.com flight options
  - accepted `let's go with 1`
  - hit Trip.com CAPTCHA
  - returned the current Trip.com URL instead of looping or claiming payment
- Partial live local Step 1:
  - TikTok downloads started
  - TikTok photo handling started
  - Douyin short link resolved
  - Douyin then required fresh cookies
- Live public workspace render with map markers after the Mapbox env fix.
- `scripts/codex/verify.sh`

### Not Fully Tested

1. The full five-step Telegram E2E script in `Sample_Inputs/VacayClaw_test.md`.
2. A fresh live rerun of Douyin and Rednote imports through Telegram after the short-link fix.
3. Real Trip.com handoff past CAPTCHA. CAPTCHA URL handoff is now accepted for the demo.
4. Cross-user concurrent edits from multiple real Telegram users and multiple browser clients.
5. A stable public domain and TLS path. AWS is paused for this pass.
6. Step 1 idempotency during long media downloads. Telegram can retry a webhook before the current receipt is fully persisted.

## Next Operator Actions

1. Start the local backend and frontend.
2. Create a fresh Telegram group, add `@VacayClawBot`, and send the copy-paste messages in `Sample_Inputs/VacayClaw_test.md`.
3. Confirm the bot creates a new Supabase workspace automatically for the group.
4. If Douyin asks for cookies, count that as an external blocker and continue with the TikTok-backed itinerary.
5. Verify Step 3 meal options, Step 4 cinema insertion, and Step 5 CAPTCHA URL handoff.
6. Before a full live rerun, harden the Telegram receipt claim so long Step 1 downloads cannot be retried mid-run.
