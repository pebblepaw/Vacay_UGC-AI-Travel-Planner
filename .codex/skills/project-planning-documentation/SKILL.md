---
name: project-planning-documentation
description: Plan projects from zero with a BRD-first, phase-indexed workflow and strict documentation discipline. Use when starting a new project, defining BRD.md scope and formulas, creating Progress.md feature checklists, maintaining progress/phaseX.md files, and designing compact indexes so new agents can load only relevant docs.
---

This skill defines a strict, reusable project-planning and documentation system for asynchronous coding agents.

Use it when a project needs:
- A detailed BRD.md at the start
- Agent-defined phase decomposition and ownership boundaries
- Feature/subtask checkbox-based progress tracking
- Continuous doc updates as implementation evolves
- Minimal-context onboarding for new agents

## Core Principles

1. BRD first, code second.
2. Every deliverable maps to a phase.
3. Every phase has a single source-of-truth document.
4. Every major change updates both execution docs and indexes.
5. New agents should read indexes first, then only targeted files.

## Required Project Documentation Layout

Create or maintain this structure:

- BRD.md
- Progress.md
- progress/index.md
- progress/phaseX.md (one file per agent-defined phase; X is not fixed)
- docs/decision_log.md
- docs/architecture.md
- docs/handoffs/latest_handoff.md

If the repository already has an established docs layout, keep that layout and map these logical roles to existing files.

## Workflow

### Step 1: Author BRD.md (Detailed)

BRD.md must include:

- Problem statement and business objective
- Success criteria (quantitative and qualitative)
- Scope and non-goals
- Constraints (technical, data, timeline, compute, compliance)
- Selected tech stack and rationale
- Optional project-structure details when relevant:
	- Data model / schemas / interfaces (if data-heavy project)
	- Service/module architecture (if software/system project)
- Optional formulas and scoring definitions where relevant
- Phase breakdown (indexable, independently executable, agent-defined)
- Artifact index (file path table for all core docs)

BRD phase section must be explicit enough for asynchronous execution:

- Phase name and intent
- Inputs
- Outputs
- Dependencies
- Acceptance criteria
- Estimated effort

### Step 2: Create Progress.md (Checkbox Control Plane)

Progress.md is the dashboard for execution status.

Use feature-oriented checkbox decomposition:

1. Phase-level checkboxes (macro progress)
2. Feature-level checkboxes inside each phase
3. Indexed subtask checkboxes under each feature (micro progress)

Each phase row should include:
- Status checkbox
- Owner (agent/human)
- Target files
- Last updated timestamp
- Link to phase document

### Step 3: Maintain progress/phaseN.md Files

Each phase file is the operational log for that phase.

Required sections:
- Goal
- Current status
- Tasks (checkboxes)
- Completed work
- Open issues
- Decisions made
- Next actions
- Evidence (metrics, logs, test results, links)

Rule: Any meaningful implementation change must update the corresponding phase file in the same work cycle.

Phase count is dynamic. The coding agent defines phases based on project shape (for example: one phase per feature group).

### Step 4: Keep Indexes Fresh

Update indexes whenever files are added, renamed, archived, or deprecated.

Minimum indexes:
- BRD artifact index table
- progress/index.md mapping of phases to documents
- Progress.md links to each phase file

### Step 5: Handoff Discipline

Before ending a work session, update docs/handoffs/latest_handoff.md with:
- What changed
- What is stable
- What is risky
- What is blocked
- Exact next recommended actions
- File links for immediate continuation

## Context-Efficient Retrieval Protocol (For New Agents)

A new agent should read in this order:

1. BRD.md (index + phase map sections first pass)
2. Progress.md (global status)
3. progress/index.md (locate exact phase docs)
4. Only the relevant phase file(s)
5. docs/handoffs/latest_handoff.md

Then, only if needed for the active task, load targeted BRD sections (for example formulas or constraints). Do not read the full BRD by default.

Do not load all project docs by default. Load only files referenced by the active phase and current task.

## BRD.md Template (Condensed)

Use this skeleton:

```markdown
# BRD

## 1. Vision and Objectives
## 2. Problem Statement
## 3. Scope / Non-Goals
## 4. Success Metrics
## 5. Constraints and Assumptions
## 6. Tech Stack and Rationale
## 7. Project Structure Details (optional, project-dependent)
## 8. Core Formulas (if applicable)
## 9. Phase Plan (agent-defined; number of phases is dynamic)
### Phase A
### Phase B
### ...
## 10. Artifact Index
| Purpose | File | Owner | Update Rule |
```

## Progress.md Template (Condensed)

```markdown
# Progress Tracker

## Global Status

## Phase Checklist
- [ ] Phase A - [progress/phaseA.md](progress/phaseA.md)
- [ ] Phase B - [progress/phaseB.md](progress/phaseB.md)

## Feature and Subtask Checklists
### Phase A
- [ ] Feature A1
	- [ ] A1.1 Subtask
	- [ ] A1.2 Subtask
- [ ] Feature A2
```

If nested checkboxes are not preferred in a repo, flatten with indexed labels:

```markdown
- [ ] A1 Feature
- [ ] A1.1 Subtask
- [ ] A1.2 Subtask
```

## Strict Rules

- Never mark a phase complete without acceptance evidence in its phase file.
- Never merge substantial code changes without corresponding doc updates.
- Never create orphan docs; every doc must be indexed.
- Never rename files without updating all index references.

## Definition of Done (Documentation)

Documentation is complete only when:
- BRD.md reflects current architecture and phase plan
- Progress.md reflects current truth
- Every active phase has an up-to-date phase document
- Index links are valid
- latest_handoff.md enables immediate continuation
