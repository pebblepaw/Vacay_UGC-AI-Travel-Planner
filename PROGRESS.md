# VACAY / VacayClaw - Progress Log

**Current Status (April 26, 2026): Workspace-runtime demo hardening complete.**

## Progress Logs (in `docs/progress/`)

- **[Phase 1: Backend Foundation](docs/progress/phase1.md)** (Jan 2025) — Python env, services, models, storage.
- **[Phase 2: API Endpoints](docs/progress/phase2.md)** (Jan 2025) — FastAPI routes, CORS, pipeline.
- **[Phase 3: Frontend Integration](docs/progress/phase3.md)** (Jan 2025) — React connected to backend.
- **[Phase 4: Basic Agent](docs/progress/phase4.md)** (Feb 2025) — Initial LangGraph orchestrator (3 nodes).
- **[Phase 5: Agent Rebuild](docs/progress/phase5.md)** (Feb 2025) — Plan-and-execute, 9 nodes, critic, tools.
- **[Phase 6: UX Polish](docs/progress/phase6.md)** (Feb 2025) — UX stabilization fixes.
- **[Phase 7: Supabase Migration](docs/progress/phase7.md)** (Feb 2025) — JSON files → Supabase Postgres + placeholder trip.
- **[Phase 8: Config + Booking Hardening](docs/progress/phase8.md)** (2025) — config-driven model selection and live booking handoff.

## VacayClaw Runtime Baseline (April 2026)

- Workspace-scoped backend routes (`/api/workspaces/*`) now exist.
- Telegram webhook ingestion endpoint now exists (`/api/telegram/webhook`).
- Shared workspace snapshots with media-to-place folders now power frontend workspace mode.
- Share-link signing and token-verified workspace loading now exist.
- Legacy trip chat endpoint now proxies to workspace runtime.
- Single-host deployment scaffolding added (`docker-compose.yml`, Dockerfiles, Nginx config).

## Latest Hardening Work (April 26, 2026)

- Telegram now ignores duplicate webhook deliveries by `update_id`.
- Telegram now ignores edited messages instead of re-running the agent on message edits.
- Meal insertion now checks the saved itinerary after replanning before claiming success.
- Browser takeover now keeps the last known URL even after the live session registry entry is gone.
- Rednote short links from `xhslink.com` now work in both backend detection and frontend ingest UI.
- Focused backend tests, frontend tests, frontend build, and `scripts/codex/verify.sh` now pass on the active branch.

## Canonical Planning + Operations Docs

- **[AGENTS.md](AGENTS.md)** — execution rules + skill usage map.
- **[23_Apr_Report.md](23_Apr_Report.md)** — implementation checklist and runtime design decisions.
- **[Agent Handoff](docs/agent_handoff.md)** — operational readiness and explicit untested integrations.
