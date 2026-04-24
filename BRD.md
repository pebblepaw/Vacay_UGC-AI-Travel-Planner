# VACAY - Documentation Index

**Current Status (April 23, 2026)**: VacayClaw workspace-runtime baseline is implemented on top of the existing VACAY planner stack.

## Read Order for Active Work

1. **[AGENTS.md](AGENTS.md)** — operating contract and required skills usage.
2. **[23_Apr_Report.md](23_Apr_Report.md)** — implementation checklist and architecture decisions.
3. **[docs/agent_handoff.md](docs/agent_handoff.md)** — real tested vs simulated coverage and handoff actions.
4. **[PROGRESS.md](PROGRESS.md)** — phase summary and runtime baseline status.

## Supporting Documentation (in `docs/`)

- **[Overview](docs/brd/overview.md)** — product flow and user-facing features.
- **[Architecture](docs/brd/architecture.md)** — prior architecture context.
- **[Agent Architecture](docs/architecture/agent_architecture.md)** — LangGraph node-level internals.
- **[Env Vars](docs/brd/env_vars.md)** — `.env` and `config/config.yaml` setup.
- **[Test Data](docs/brd/test_data.md)** — video URLs and manual test prompts.
- **[Progress Logs](docs/progress/)** — historical implementation records by phase.

## Note on Staleness

Some historical phase documents predate the VacayClaw workspace-runtime revamp. When conflicts appear, follow `AGENTS.md` and `23_Apr_Report.md`.
