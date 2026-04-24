# VACAY / VacayClaw Agent Guide

This repo is moving from `VACAY` to `VacayClaw`.

Start every substantial task by reading:

1. [23_Apr_Report.md](23_Apr_Report.md)
2. [BRD.md](BRD.md)
3. [docs/agent_handoff.md](docs/agent_handoff.md)
4. [PROGRESS.md](PROGRESS.md)

## What This Repo Is Building

`VacayClaw` is a travel-first collaborative agent runtime.

It is not:

- a thin layer of prompts on top of Hermes
- a thin layer of prompts on top of OpenClaw
- a single-user trip planner anymore

Keep the travel-specific planner logic. Replace the runtime around it: Telegram gateway, shared workspace state, durable memory, cloud browser handoff, and shared web control.

## Current Product Rules

- One Telegram group or forum topic equals one workspace.
- One workspace equals one trip.
- New TikTok, YouTube, Instagram, Douyin, and Rednote links merge into that workspace.
- The website is a second control surface for the same workspace.
- Flights stay in scope. Hotels and attractions do not.
- Stop before payment.
- Design for desktop demo use. Do not spend time optimizing mobile first.

## Repo-Vendored Skills

This branch vendors local skill content into:

- `.codex/skills/`
- `.codex/superpowers/`

Use them as repo-local reference material in cloud tasks. Read only the skills that match the task.

Read these first when they apply:

- Documentation, plans, implementation notes:
  - `.codex/skills/the-hemingway-rule/SKILL.md`
- General code changes, refactors, prompt or schema work:
  - `.codex/skills/coding-practices/SKILL.md`
- Frontend work:
  - `.codex/skills/frontend-skills/frontend-design/SKILL.md`
  - `.codex/skills/frontend-skills/adapt/SKILL.md`
  - `.codex/skills/frontend-skills/polish/SKILL.md`
  - `.codex/skills/frontend-skills/harden/SKILL.md`
  - `.codex/skills/frontend-skills/optimize/SKILL.md`
- Browser testing and web automation:
  - `.codex/skills/playwright-cli/SKILL.md`
- Multi-agent execution:
  - `.codex/superpowers/skills/subagent-driven-development/SKILL.md`
  - `.codex/superpowers/skills/dispatching-parallel-agents/SKILL.md`
- Test-first implementation:
  - `.codex/superpowers/skills/test-driven-development/SKILL.md`
- Debugging:
  - `.codex/superpowers/skills/systematic-debugging/SKILL.md`
- Final verification before claiming success:
  - `.codex/superpowers/skills/verification-before-completion/SKILL.md`

Do not read the whole vendored skill tree by default. Pull in only the files that match the current task.

## Execution Rules

- Do not push to `main`.
- Use feature branches and open reviewable PRs.
- Keep commits small enough for the user to test incrementally.
- Update the checklist in [23_Apr_Report.md](23_Apr_Report.md) as work lands.
- If you copy code from external repos, update [docs/research/donor_code_log.md](docs/research/donor_code_log.md).
- Keep `docs/` in the repo. It is part of the cloud context, not optional background material.
- `docs/project_proposal/credentials.json` and `docs/project_proposal/token.json` are intentionally excluded from GitHub. Treat them as secrets.

## Coding Rules

- Prefer clear interfaces over prompt-only glue.
- Prefer durable state over module memory.
- Prefer workspace-scoped APIs over trip-scoped APIs for new work.
- Keep prose short and direct in docs, commit messages, and reports.
- When changing the frontend, preserve the current quality bar and keep the design intentional.
- When changing the agent, remove brittle history scraping before adding new behavior on top of it.

## Verification Rules

Before claiming work is complete:

- run `scripts/codex/verify.sh`
- call out any live integrations you could not test
- state clearly whether Telegram, browser automation, or cloud-only paths were simulated or run for real

## Cloud Setup

For Codex cloud environments:

- use `scripts/codex/setup_cloud.sh` as the environment setup script
- keep secrets in the environment, never in repo files
- use `AGENTS.md` and `23_Apr_Report.md` as the persistent context

Do not assume the cloud task remembers prior chat context. The repo must carry the context it needs.
