# Orchestrator — How to Use This System

This document explains how the task system works and how to hand tasks to a coding agent (Claude Sonnet, Cursor, etc.) so they produce clean, architecture-aligned implementations.

---

## The Problem This Solves

When you hand a large refactor to an AI coding agent, three things go wrong:

1. **Scope creep.** The agent "improves" things not in the spec, introduces abstractions for hypothetical future needs, adds error handling for impossible states, refactors nearby code it didn't need to touch.
2. **Corner-cutting.** The agent gets 90% done and fakes the last 10% — leaves TODOs, stubs out the hard part, silently drops edge cases, claims success without verifying.
3. **Context loss.** Each task is implemented in isolation. The agent doesn't know why previous decisions were made, what the next task needs, or what invariants it must preserve.

The task system addresses all three by giving each task:
- A **SPEC** that defines exactly what to do, what NOT to do, and how to verify
- A **KICKOFF** section that links to the architecture philosophy and the next task's spec
- A **HANDOFF** section that captures what the next implementer needs to know

---

## Task Structure

Each task file (`tasks/TASK_XX.md`) contains three sections:

### 1. Kickoff (Read Before Coding)

**Purpose:** Orient the implementer. Before writing a single line of code, the agent reads:
- Its own spec (obviously)
- The next task's spec (to understand what it's enabling — this prevents decisions that make the next step harder)
- Relevant sections of the architecture philosophy

**Contains:**
- Pre-conditions to verify (is the app working? did the previous task complete?)
- Lessons from the previous task (populated by the previous implementer)
- Links to read

### 2. Spec (The Contract)

**Purpose:** Define the exact scope. This is a contract, not a suggestion.

**Contains:**
- Goal (one paragraph)
- What this enables (why this task matters for the chain)
- Exact files to create, modify, or delete
- Code patterns to follow (with examples)
- **DO NOT** list (specific anti-patterns this task is likely to introduce)
- Acceptance criteria (checklist — all must pass)
- Verification commands

### 3. Handoff (Write After Coding)

**Purpose:** Capture context for the next implementer.

**Contains a template** that the implementer fills in:
- What decisions were made and why
- What was harder than expected
- What the next task should watch out for
- Any deviations from the spec (and why)

---

## How to Hand a Task to an Agent

Copy-paste this prompt template, filling in the task number:

```
You are implementing Task [XX] of the Bildung architecture migration.

BEFORE writing any code:
1. Read the task spec: docs/002_architecture/tasks/TASK_[XX].md
2. Read the NEXT task's spec (linked at the top of your task) to understand what you're enabling
3. Read the sections of docs/002_architecture/02_target_architecture.md referenced in your kickoff

WHILE implementing:
- Follow the spec exactly. Do not add features, refactor nearby code, or "improve" things outside scope.
- Check every item in the DO NOT list before committing.
- If you're unsure about a decision, err on the side of doing less, not more.

AFTER implementing:
- Run every verification command in the spec.
- Check every acceptance criterion.
- Fill in the HANDOFF section of your task file.
- Read the next task's KICKOFF section and update its "Lessons from Previous Task" field.

Do not declare the task complete until all acceptance criteria pass.
```

---

## Task Sequence

Tasks are numbered `Phase.Subtask` (e.g., `0A`, `1B`, `2C`). Within a phase, tasks are sequential — each depends on the previous one. Across phases, some chains are parallelizable:

```
CHAIN 1 (Backend):  0B → 0C → 1A → 1B → 1C → 2A → 2B → 2C → 5A → 5B
CHAIN 2 (Frontend): 0A → 4A → 4B
CHAIN 3 (Tests):    (after 1C) → 3A → 3B
```

**Chain 1** is the critical path. Chain 2 (frontend) and Chain 3 (tests) can run in parallel with Chain 1 after their prerequisites are met.

### Full Task List

| Task | Name | Depends On | Enables |
|------|------|-----------|---------|
| 0A | Frontend component extraction | — | 4A |
| 0B | Stats service extraction | — | 0C |
| 0C | Backend fixes (IDs, dead code, ports, config) | 0B | 1A |
| 1A | Domain models | 0C | 1B |
| 1B | Repository layer | 1A | 1C |
| 1C | Service + dependency + router rewiring | 1B | 2A, 3A |
| 2A | PostgreSQL entity schema | 1C | 2B |
| 2B | Neo4j → PostgreSQL data migration | 2A | 2C |
| 2C | Repository + ingestion migration to PG | 2B | 5A |
| 3A | Test infrastructure (testcontainers + conftest) | 1C | 3B |
| 3B | Test suites (service, API, XP) | 3A | — |
| 4A | TanStack Query + hooks | 0A | 4B |
| 4B | Page updates + error boundaries + pagination | 4A | — |
| 5A | YAML enrichment data + deterministic matching | 2C | 5B |
| 5B | OpenLibrary enrichment integration | 5A | — |

---

## Guiding Principles (For Every Task)

These apply to every task. If a task's spec conflicts with these, the spec wins (it's more specific).

### 1. Leave the app working after every task

Run the backend. Run the frontend. Click through the main pages. If anything is broken, fix it before declaring the task done. "But the tests pass" is not sufficient — the tests are empty stubs until Phase 3.

### 2. Do not add what the spec doesn't ask for

If the spec says "create WorkRepository with list() and get()" and you think "I should also add search() and count()" — stop. The next task will add what it needs. Speculative code is tech debt.

### 3. Do not "improve" code you're touching

If you're moving a Cypher query from a service to a repository, move it. Don't also rewrite the query to be "more efficient." Don't add logging that wasn't there. Don't rename variables. The goal is structural change with minimal behavioral change.

### 4. When in doubt, match the existing pattern

If the codebase does something a specific way (even if it's not ideal), match that pattern unless the spec explicitly says to change it. Consistency beats local optimality.

### 5. Verify with running code, not with your confidence

"I'm confident this works" is not verification. Run the command. Check the output. Click the link. Read the response body.
