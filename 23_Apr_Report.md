# 23 Apr Implementation Plan: VacayClaw

**VACAY cannot become a collaborative Telegram-first travel agent by adding a few skills on top of Hermes or OpenClaw.** Build `VacayClaw` as its own runtime in this repo: add a Telegram gateway, durable shared workspace state, cloud-first browser execution, and a web surface that mirrors the same live trip. Keep the travel-specific agent logic, but replace the in-memory state and single-user assumptions.

## Summary

- Build `VacayClaw` in this repo. Do not re-platform onto Hermes, OpenClaw, or Memoh.
- Keep the travel planner logic. Replace the session, memory, media, and booking runtime around it.
- Treat each Telegram group or topic as one shared trip workspace. DMs do not edit that workspace.
- Move from one trip JSON blob to a `hybrid workspace + snapshot` model: real shared records underneath, one derived snapshot for the web client.
- Run the product cloud-first on `single EC2 + Docker Compose`, with a remote browser worker that the user can take over before payment.

## Progress Checklist

- [x] Create the `VacayClaw` runtime shell and replace the current trip-scoped chat entrypoint with workspace-scoped routing.
- [x] Add Telegram webhook ingestion keyed by `chat_id + message_thread_id`.
- [x] Replace the current trip JSON storage model with the hybrid workspace data model.
- [x] Add durable LangGraph persistence and remove all in-memory booking and chat session state.
- [x] Add workspace memory and user memory.
- [x] Extend media ingestion to TikTok, YouTube, Instagram, Douyin, and Rednote in one shared workspace flow.
- [x] Add media-to-place linking so the bot can resolve requests like “add the cafe in this TikTok”.
- [x] Rebuild the frontend around workspace snapshots, live updates, and shared web chat.
- [x] Add per-location media folders with autoplay clips on the desktop web view.
- [x] Replace URL-only booking handoff with a cloud browser session handoff that survives remote use.
- [x] Deploy the full stack on one EC2 host with Docker Compose, Nginx, and Telegram webhooks.
- [x] Write end-to-end tests and a fixed demo script for the final presentation.

## Decision: Build VacayClaw Here

The base architecture is `VacayClaw runtime in this repo`.

Do not:

- turn Hermes into the product shell
- turn OpenClaw into the product shell
- keep the current `Trip` blob as the only shared state model
- rely on skills, markdown files, or prompt glue as the main contribution

Do:

- borrow only the pieces we need from Hermes, OpenClaw, or other repos if that shortens delivery
- log every borrowed module in `docs/research/donor_code_log.md` with repo, commit, license, files copied, and what changed after copying
- keep the travel-specific planner and booking logic as core product code, not as a plugin inside a generic assistant

This makes the contribution clear: **VacayClaw is a travel-first collaborative agent runtime, not a generic agent with travel prompts.**

## What Is Broken Now

The current product is strong as a single-web-app planner. It is weak as a shared Telegram-driven runtime.

Current limits:

- The backend treats the trip as the unit of conversation, not the shared workspace.
- The graph has no durable checkpointer. `backend/agent/graph.py` compiles without persistence.
- Booking follow-up still uses module memory in `backend/routers/chat.py`.
- The frontend loads one trip and one chat session. It does not mirror a shared group workspace in real time.
- The data model stores one trip document. That is fine for one user. It is weak for group edits, media folders, booking state, and attribution.
- Booking handoff still assumes the machine running Playwright is visible to the user. That breaks once the app runs in the cloud.

## Architecture

### 1. Workspace Runtime

Make `workspace` the core unit, not `trip_id`.

Rules:

- One Telegram group or topic maps to one workspace.
- New links always merge into that workspace.
- Web chat and Telegram chat both write to the same workspace event stream.
- DMs can exist, but they do not edit a group workspace unless you add that policy later.

Workspace key:

```text
telegram:{chat_id}:{thread_id|main}
```

Core runtime flow:

```text
Telegram message or web chat
→ workspace router
→ conversation event log
→ agent run
→ state mutations
→ snapshot rebuild
→ websocket push to web clients
```

Keep the travel-specific orchestrator idea, but refactor it into a workspace-aware runtime:

- keep specialist travel, search, and booking behavior
- keep LangGraph as the internal task engine unless the implementation proves a simpler router is better
- remove request state that depends on free-text history scanning
- replace trip-scoped chat calls with workspace-scoped runs and durable thread IDs

### 2. Shared State Model

Use the `hybrid workspace + snapshot` design.

Store shared records in Postgres. Serve one derived snapshot JSON to the frontend.

Core tables:

- `workspaces`
- `workspace_members`
- `workspace_snapshots`
- `media_items`
- `place_candidates`
- `places`
- `place_media_links`
- `itinerary_items`
- `conversation_events`
- `memory_entries`
- `booking_runs`
- `share_links`

What each part does:

- `workspaces`: one row per Telegram trip workspace
- `workspace_members`: Telegram users who participated in that workspace
- `workspace_snapshots`: the current web-ready JSON snapshot
- `media_items`: every imported TikTok, YouTube, Instagram, Douyin, or Rednote video
- `place_candidates`: extracted places from each media item before the agent commits them
- `places`: canonical places already accepted into the workspace
- `place_media_links`: many-to-many link between places and source videos
- `itinerary_items`: ordered day slots inside the trip
- `conversation_events`: Telegram and web chat messages, tool actions, system notices
- `memory_entries`: `workspace` scope and `user` scope memory
- `booking_runs`: search results, selected fare, traveler progress, remote browser session metadata
- `share_links`: signed tokens for website access

Snapshot policy:

- Rebuild the workspace snapshot after every state mutation.
- Store the latest snapshot as JSONB for fast web reads.
- Keep the frontend read path simple: `load snapshot`, `subscribe to updates`, `send messages`.

Do not keep one giant trip document as the only mutable record.

### 3. Media Ingestion

Keep the current yt-dlp and video-analysis pipeline shape, but make it part of the workspace model.

Required changes:

- Add Instagram URL detection and download support.
- Accept multiple links from one Telegram message and from repeated messages over time.
- Persist every imported media item, not just the final trip.
- Store extracted place candidates per media item.
- Let the agent resolve commands like “add the cafe in this TikTok” by using:
  - the replied-to Telegram message
  - the referenced media item
  - the extracted place candidates from that clip

Media storage:

- Save derived thumbnails and short autoplay-safe preview clips to S3.
- Keep raw downloaded files temporary. Delete them after processing unless needed for retry.
- Save only the metadata and object URLs in Postgres.

### 4. Memory

Keep two memory scopes only:

- `workspace memory`
- `user memory`

Workspace memory stores:

- trip destination and theme
- accepted places
- rejected places
- unresolved search and booking tasks
- current booking run status
- shared decisions made in Telegram or web chat

User memory stores:

- preferences like budget, airline bias, food restrictions, pace
- traveler identity fields that matter for booking
- past corrections that should stay attached to one person, not the whole group

Do not add a third global bot memory layer.

### 5. Web Surface

The website is not a passive dashboard. It is a second control surface for the same workspace.

Required changes:

- Replace trip-based loading with workspace snapshot loading.
- Add a workspace websocket channel for real-time updates.
- Keep the chat panel on the website and route it to the same workspace event stream as Telegram.
- Redesign for desktop only. Stop spending time on mobile-first behavior.
- Add a location detail panel that shows:
  - the accepted place
  - the linked media folder
  - autoplay preview clips
  - source platform badges

Signed access:

- The Telegram bot sends a signed workspace link.
- The link itself is the access key.
- No login screen for the demo.
- The signed token maps to one workspace and one scope.

Public interface changes:

- `POST /api/telegram/webhook`
- `GET /api/workspaces/{workspace_id}/snapshot`
- `POST /api/workspaces/{workspace_id}/messages`
- `GET /api/workspaces/{workspace_id}/events/ws`
- `POST /api/workspaces/{workspace_id}/share-links`

Retire the old assumption that the frontend opens a trip by `?trip=...` and talks only to `/api/trips/{id}/chat`.

### 6. Booking and Browser Handoff

Flights stay in scope. Hotels and attractions do not.

The product stops before payment.

Do not keep the current “open a Trip.com URL in the user’s browser” handoff. That is local-machine logic. It fails in the cloud because the server browser session and the user browser session do not share cookies or session state.

Build a remote browser worker instead:

- run a headed Playwright container on EC2
- keep one persistent browser context per booking run
- expose that browser session through a signed takeover link, backed by a streamed browser page
- hand the user to that remote browser session before payment

Booking flow:

```text
Telegram or web asks for flights
→ booking run created in Postgres
→ browser worker searches Trip.com
→ normalized offers saved to booking_runs
→ user selects one offer
→ same persistent browser session reaches traveler page
→ web app shows "continue booking" button
→ signed remote-browser page opens
→ human finishes pre-payment steps and payment
```

The browser worker must persist:

- browser session ID
- profile path or remote context ID
- selected offer identity
- current booking step
- last known page URL

Remove all in-memory booking caches from the backend.

### 7. Deployment

Target one EC2 host with Docker Compose.

Compose services:

- `nginx`
- `frontend`
- `backend-api`
- `backend-worker`
- `redis`
- `browser-worker`

External services:

- Supabase Postgres
- S3 bucket for preview media
- Telegram Bot API

Nginx handles:

- HTTPS
- frontend static assets
- API reverse proxy
- websocket proxy
- Telegram webhook endpoint routing

The backend worker handles:

- media ingestion jobs
- video analysis jobs
- snapshot rebuild jobs
- booking automation jobs

Redis handles:

- job queue
- short-lived coordination between API and worker processes

## Implementation Changes

### A. Replace Trip-Scoped APIs With Workspace APIs

Keep the old trip endpoints only long enough to migrate the frontend. The real runtime must move to workspace IDs.

Work items:

- add workspace router and signed-link service
- add Telegram webhook ingestion
- add workspace event append and replay service
- map the web chat and Telegram chat into one message contract

### B. Add Durable LangGraph Persistence

Use LangGraph persistence with Postgres-backed checkpointing and store.

Work items:

- compile the graph with a real checkpointer
- pass a durable `thread_id` per workspace run
- move all request, booking, and follow-up state into durable graph state or Postgres records
- remove `_BOOKING_SESSION` completely
- stop deriving current request from the first human message in history

### C. Rebuild the Frontend Around Workspace Snapshots

The current frontend already has the right visual pieces. It needs a new data contract.

Work items:

- replace `TripContext` with `WorkspaceContext`
- load snapshots, not trip blobs
- subscribe to websocket events
- merge Telegram and web chat into one visible timeline
- add media folders to the map and cards flows
- add desktop-first layout for map, media, and shared chat

### D. Add Media-Aware Commands

Users will keep sending clips into the same Telegram chat. The agent must understand those clips as reusable evidence, not as one-off trip seeds.

Work items:

- attach each imported media item to the Telegram message that created it
- keep extracted place candidates per media item
- resolve “this TikTok”, “that Instagram reel”, and reply-based references
- support commands that add one place from one clip without rebuilding the whole trip

### E. Replace the Booking Handoff Model

The current booking logic proves Trip.com automation. It does not yet solve cloud use.

Work items:

- make booking runs first-class records
- normalize offer identities and persist them
- keep one remote browser context per booking run
- stream the remote browser into a signed takeover page
- stop before payment

## Test Plan

### Shared Runtime

- One Telegram group creates one workspace and reuses it across many messages.
- Two users in the same group add links and both changes appear in the same workspace.
- A Telegram topic creates a different workspace from the group main thread.
- A backend restart does not lose booking state, memory, or pending tasks.

### Media

- One message with multiple TikTok and YouTube links imports all media items into the current workspace.
- A later Instagram link merges into the same workspace without replacing the existing trip.
- The command “add the cafe in this TikTok” resolves against the replied-to media item and adds only that place.
- A place page on the website shows all linked clips for that location and autoplay previews work on desktop.

### Web

- The bot sends a signed workspace link and the website opens the correct shared trip.
- Two web clients connected to the same workspace see live updates from Telegram.
- A web chat message appears in Telegram-visible history and vice versa.
- Invalid or expired signed links fail cleanly.

### Booking

- A user requests flights from Telegram and receives real Trip.com options.
- Offer selection persists across backend restarts.
- The browser worker reaches the traveler page in the same persistent session.
- The website opens the signed browser takeover page and the human can continue before payment.
- Payment is never auto-submitted.

### Deployment

- Docker Compose starts the full stack on one EC2 host.
- Telegram webhook delivery works through Nginx over HTTPS.
- S3-hosted preview media loads in the website.
- The full demo works from a laptop that is not the machine running the server.

## Codex Cloud Workflow

Use Codex cloud for development when laptop access is poor.

What I need from you before that handoff:

- the repo pushed to GitHub
- one setup script that installs backend and frontend dependencies
- the list of environment variable names the cloud task will need
- the AWS values stored in the cloud environment or a secret manager, not pasted into chat

How to run it:

1. Connect the GitHub repo to Codex cloud.
2. Point Codex cloud at the target branch.
3. Add the setup script and environment variables.
4. Let cloud tasks run tests, builds, and implementation work in the remote container.
5. Review diffs and PRs from the browser when local connectivity is weak.

This fits your situation because the coding and test execution happen in the cloud container, not on your laptop.

## Sources

External research used for this plan:

- OpenClaw docs and repo: <https://docs.openclaw.ai/> , <https://github.com/openclaw/openclaw>
- Hermes Agent docs and repo: <https://hermes-agent.nousresearch.com/docs/> , <https://github.com/NousResearch/hermes-agent>
- Memoh docs and repo: <https://docs.memoh.ai/> , <https://github.com/memohai/Memoh>
- LangGraph persistence and memory docs: <https://docs.langchain.com/oss/python/langgraph/persistence> , <https://docs.langchain.com/oss/python/langgraph/add-memory>
- OpenAI Codex cloud docs: <https://developers.openai.com/codex/cloud> , <https://developers.openai.com/codex/cloud/environments> , <https://developers.openai.com/codex/cloud/internet-access>

Local evidence used for this plan:

- [backend/agent/graph.py](/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/backend/agent/graph.py)
- [backend/routers/chat.py](/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/backend/routers/chat.py)
- [backend/storage/supabase_storage.py](/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/backend/storage/supabase_storage.py)
- [frontend/src/contexts/TripContext.tsx](/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/frontend/src/contexts/TripContext.tsx)
- [frontend/src/pages/Index.tsx](/Users/pebblepaw/Documents/CODING_PROJECTS/VACAY/frontend/src/pages/Index.tsx)


## Implementation Notes (Overnight Run)

- Completed the checklist with workspace-scoped runtime endpoints, Telegram webhook routing, workspace snapshots, memory tables with fallback storage, and signed share links.
- Added workspace media ingestion merge flow and media-to-place derived folders for desktop autoplay previews.
- Added Docker Compose + Nginx deployment scaffolding for single-host EC2 rollout.
- Added demo script for repeatable end-to-end walkthrough.
- Validation constraints remain for real Telegram and Trip.com live flows, recorded in `docs/agent_handoff.md`.
