# VACAY / VacayClaw Agent Guide

This repo is moving from `VACAY` to `VacayClaw`.

Start every substantial task by reading:

1. [23_Apr_Report.md](23_Apr_Report.md)
2. [BRD.md](BRD.md)
3. [docs/agent_handoff.md](docs/agent_handoff.md)

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

## Execution Rules

- Do not push to `main`.
- Use feature branches and open reviewable PRs.
- Keep commits small enough for the user to test incrementally.
- Update the checklist in [23_Apr_Report.md](23_Apr_Report.md) as work lands.
- If you copy code from external repos, update [docs/research/donor_code_log.md](docs/research/donor_code_log.md).

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
