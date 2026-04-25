# Agent Handoff Protocol

VacayClaw is now a **workspace-first collaborative travel runtime**. Use this file plus `AGENTS.md` and `23_Apr_Report.md` as operating context.

## Current Status (2026-04-26)

- Backend supports workspace-scoped routing at `/api/workspaces/*` with shared event logs, runtime state, and signed web handoff.
- Telegram webhook ingestion works at `/api/telegram/webhook`, keyed by `chat_id + message_thread_id`, and sends outbound replies back into the Telegram group.
- Frontend supports workspace mode via `/?workspace=<id>&token=<signed-token>`.
- Workspace snapshots drive the shared web chat, the map, and media folders by place.
- The branch has a live EC2 deployment with Docker Compose, Nginx, Telegram webhooks, and a public browser worker behind a Cloudflare quick tunnel.
- The branch is still not cleanly done. Later E2E steps can drift between the bot reply and the saved workspace snapshot.

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
- Live Telegram webhook roundtrip for:
  - initial Sydney itinerary build
  - trip resize to 2 days
- Live public workspace render with map markers after the Mapbox env fix.

### Not Fully Tested

1. The full five-step Telegram E2E script in `Sample_Inputs/VacayClaw_test.md`.
2. Clean persistence for the later Telegram steps. Step 3 returned a success reply once, but the saved snapshot did not retain the food stop.
3. Real media analysis after the Gemini project hit its spend cap.
4. Real cloud browser handoff on Trip.com through to a polished signed remote takeover flow.
5. Cross-user concurrent edits from multiple real Telegram users and multiple browser clients.
6. A stable public domain and TLS path that does not rely on a Cloudflare quick tunnel.

## Next Operator Actions

1. Restore Gemini credits or configure another supported provider. Without that, fresh media analysis and any LLM-only path will stall.
2. Fix the state drift bug between Telegram success replies and the saved workspace snapshot during later steps.
3. Re-run the full five-step script in `Sample_Inputs/VacayClaw_test.md` from a fresh workspace.
4. Finish the remote browser handoff so the user lands in a signed takeover session, not just a browser worker that exists on the server.
5. Replace the quick tunnel with a stable public hostname.
6. Run `scripts/codex/verify.sh` again once the branch is stable, then refresh the report checklist.
