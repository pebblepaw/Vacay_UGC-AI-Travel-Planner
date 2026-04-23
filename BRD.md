# VACAY - Documentation Index

**Current Status**: Phase 8 work is on `main`. The app now includes config-driven model selection, `google.genai` video analysis, stricter location resolution, and a live Playwright-backed Trip.com flight handoff. One search/critic experiment was rolled back and is documented for future rework.

## Documentation (in `docs/`)
Only read what you need. Start with the handoff guide.

- **[Handoff Guide](docs/agent_handoff.md)** — Start here. Current state, risks, and the rolled-back work.
- **[Overview](docs/brd/overview.md)** — Product flow and user-facing features.
- **[Architecture](docs/brd/architecture.md)** — Tech stack, folder structure, and runtime shape.
- **[Agent Architecture](docs/architecture/agent_architecture.md)** — LangGraph graph, nodes, tools, and booking flow.
- **[Env Vars](docs/brd/env_vars.md)** — `.env` and `config/config.yaml` setup.
- **[Test Data](docs/brd/test_data.md)** — Video URLs and manual test prompts.
- **[Phase 8 Progress](docs/progress/phase8.md)** — Recent booking, config, and stabilization work. Includes the reverted search/critic sub-phase.

## Historical Docs
- **[Project Proposal](docs/project_proposal/Project_Proposal.md)** — Historical proposal. Do not treat it as the current source of truth.
