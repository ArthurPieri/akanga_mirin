# CLAUDE.md — Akanga Mirin Contributor Guide for Claude Code

This file provides context for Claude Code sessions working on the **akanga_mirin**
repository (the learning path), not the noteapp reference implementation.

---

## What this repo is

A structured build-to-learn curriculum that teaches Python developers systems-level
concepts by having them build a personal knowledge graph in 9 phases (10 after Phase 1
is split into 1A + 1B). Each phase has:

- A phase doc (`docs/learning/phase-NN-*.md`) — the spec and guide
- A skeleton (`skeletons/phase_NN/`) — stub code with WHAT/WHY/HOW docstrings
- A test suite (`tests/phase_NN/`) — pytest tests run against learner code
- A reference solution (`solutions` branch — not on `main`)

---

## Repo structure at a glance

```
docs/learning/          9 phase docs — DONE
docs/foundations/       10 explainer docs — 3/10 done, 7 in progress
docs/                   planning, security, roadmap, user stories, etc.
scripts/                study.sh, skeleton_check.py, sync_forward.py
templates/              project-makefile template for learners
tests/                  phase test suites — NOT YET WRITTEN (Sprint 2)
skeletons/              skeleton code per phase — NOT YET WRITTEN (Sprint 2)
solutions branch        reference implementations — NOT YET WRITTEN (Sprint 3)
```

---

## Current sprint

**Sprint 1** — Infrastructure + phase doc quality. See `docs/implementation-plan.md`.

Work in progress:
- Writing the 10 foundation explainer docs (`docs/foundations/`)
- Fixing phase doc cross-references and content bugs

Not yet started:
- Test suites (`tests/phase_NN/`) — Sprint 2
- Skeleton files (`skeletons/phase_NN/`) — Sprint 2
- Reference solutions (`solutions` branch) — Sprint 3

---

## How testing works (once tests exist)

```bash
AKANGA_SRC=./src make test PHASE=2     # learner's code in ./src
make test-solution PHASE=2             # reference solution (solutions branch)
make test-all                          # all phases against solutions
```

The `AKANGA_SRC` env var points pytest at learner code. Without it, tests fall back to
the solutions directory. Always set it explicitly when testing learner code.

---

## Makefile key targets

```bash
make help               # full target list with descriptions
make status             # phase completion matrix (skeleton/tests/solution per phase)
make where-is-my-src    # show what AKANGA_SRC resolves to
make study PHASE=3      # open three-pane tmux study session
make docs-phase PHASE=2 # open a phase doc in glow
make foundations TOPIC=sqlite-basics  # open a foundation doc in glow
make lint               # ruff check
make sync-forward FROM=2 FILE=src/akanga_core/parser.py  # propagate bug fix
```

---

## Key design decisions (recorded in docs/adversarial-analysis.md §6)

| Decision | Resolution |
|---|---|
| Split Phase 1 into 1A + 1B | YES — edge schema / workspace registry boundary |
| Solutions on separate branch | YES — `solutions` branch, not `solutions/` dir on `main` |
| Solo/Group Reflect tracks | YES — `> **Solo:**` / `> **Group:**` callouts |
| Open-ended vault exercises | YES — replace half of fixed tables with open prompts |
| Prerequisite self-assessment | YES — checklist at top of each phase doc |

---

## Things NOT to do

- Do not modify `solutions/` content directly — the solutions branch is the authoritative source
- Do not add SENTINEL comments to non-skeleton files — SENTINEL is a skeleton mechanism
- Do not create Docker-based workflows — explicitly out of scope
- Do not add cloud sync, multi-user, or vector embedding features — parked in `docs/future-ideas.md`
- Do not commit `src/`, `vault/`, `*.db` — these are learner runtime artifacts

---

## The 71 relation types

All 71 built-in relation types live in `docs/foundations/relation-vocabulary.md`.
11 categories with prefix codes: EP, HT, SC, CT, AP, DR, CC, EV, PA, SO, TC.
Phase 1 builds the relation registry. Phase 8's `list_relation_types()` MCP tool exposes it.

---

## Security context

Three security issues already fixed in the reference implementation (noteapp):
- SEC-02: path traversal now uses `Path.resolve().is_relative_to()` in `server.py`
- SEC-06: FTS5 operator injection now wraps user terms in double-quotes in `db.py`
- SEC-01/04: Phase 8 spec uses `[KNOWLEDGE GRAPH CONTEXT]` delimiters and binds MCP to `127.0.0.1`

See `SECURITY.md` for the disclosure process.
