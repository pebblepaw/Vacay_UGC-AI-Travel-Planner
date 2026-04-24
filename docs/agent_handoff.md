# Agent Handoff Protocol

VacayClaw is now a **workspace-first collaborative travel runtime**. Use this file plus `AGENTS.md` and `23_Apr_Report.md` as operating context.

## Current Status (2026-04-23)

- Backend now supports **workspace-scoped routing** (`/api/workspaces/*`) with shared event logs and runtime state persistence.
- Telegram webhook ingestion exists at `/api/telegram/webhook`, keyed by `chat_id + message_thread_id` workspace IDs, and now sends outbound replies with topic routing.
- Frontend supports workspace mode via `/?workspace=<id>&token=<signed-token>`.
- Workspace snapshots now drive live polling updates, shared chat hydration from `recent_events`, and media-per-location folders in Cards view.
- Signed share links are available via `/api/workspaces/{workspace_id}/share-link` and are included in Telegram replies.
- Legacy `/api/trips/{trip_id}/chat` still works as compatibility shim into workspace runtime.

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

## What Was Tested in VM

### Ran

- Python syntax compile over backend package.
- Frontend production build.
- Existing codex verify script.

### Not Fully Tested (Environment / Integration Constraints)

1. **Real Telegram webhook roundtrip against a public bot endpoint** was not run end-to-end in this VM despite outbound API calls being implemented and covered with mocked tests.
2. **Supabase workspace tables** (`workspaces`, `conversation_events`, `memory_entries`, `workspace_runtime_state`, `workspace_snapshots`) against production schema. Runtime includes in-memory fallback when tables are absent.
3. **Real cloud browser handoff on Trip.com** end-to-end from Telegram event through interactive browser takeover remains unverified here.
4. **Cross-user concurrent edits** from multiple real Telegram users plus multiple browser clients simultaneously.
5. **EC2 Docker Compose deployment** on an actual host with domain + TLS.

## Next Operator Actions

1. Apply SQL migrations for the new workspace tables in Supabase.
2. Configure Telegram webhook URL + secret token.
3. Run `scripts/demo/run_workspace_demo.sh` against deployed backend.
4. Run full `scripts/codex/verify.sh` in cloud env with live secrets.
5. Validate real Trip.com handoff and stop-before-payment behavior with human verification.
