# Agent Handoff Protocol

VacayClaw is now a **workspace-first collaborative travel runtime**. Use this file plus `AGENTS.md` and `23_Apr_Report.md` as operating context.

## Current Status (2026-04-26)

- Backend supports workspace-scoped routing at `/api/workspaces/*` with shared event logs, runtime state, and signed web handoff.
- Telegram webhook ingestion works at `/api/telegram/webhook`, keyed by `chat_id + message_thread_id`, sends outbound replies back into the Telegram group, ignores duplicate `update_id` deliveries, and ignores edited messages.
- Frontend supports workspace mode via `/?workspace=<id>&token=<signed-token>`.
- Workspace snapshots drive the shared web chat, the map, and media folders by place.
- The branch has a live EC2 deployment with Docker Compose, Nginx, Telegram webhooks, and a public browser worker behind a Cloudflare quick tunnel.
- Meal insertion now checks the saved itinerary after replanning, so the bot stops claiming success when the new food stop gets dropped.
- Browser takeover now keeps the last known Trip.com URL even after the live session registry entry is gone.
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
- Live public workspace render with map markers after the Mapbox env fix.
- `scripts/codex/verify.sh`

### Not Fully Tested

1. The full five-step Telegram E2E script in `Sample_Inputs/VacayClaw_test.md`.
2. A fresh live rerun of Douyin and Rednote imports through Telegram after the short-link fix.
3. Real cloud browser handoff on Trip.com through to the pre-payment page on this exact commit.
4. Cross-user concurrent edits from multiple real Telegram users and multiple browser clients.
5. A stable public domain and TLS path that does not rely on a Cloudflare quick tunnel.

## Next Operator Actions

1. Run the full five-step script in `Sample_Inputs/VacayClaw_test.md` from a fresh Telegram group or fresh topic. Do not reuse the noisy old demo thread.
2. Verify the cinema-insertion step and the booking step against one fresh saved workspace snapshot.
3. Re-run real Douyin and Rednote imports through Telegram now that `xhslink.com` is recognized.
4. Replace the quick tunnel with a stable public hostname when demo-day setup is ready.
5. If multi-process durability becomes a requirement, move active live browser session ownership out of `live_booking_sessions` and into a real shared coordinator.
