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
- A reference solution (location under review — currently `solutions/phase_08/` on `main`; see decision note below)

---

## Repo structure at a glance

```
docs/learning/          10 phase docs (Phase 1 split into 1A + 1B) — DONE
docs/foundations/       15 explainer docs — DONE
docs/                   planning, security, roadmap, user stories, etc.
scripts/                study.sh, skeleton_check.py, sync_forward.py
templates/              project-makefile template for learners
tests/                  phase test suites — DONE for all 9 phases (145 tests)
skeletons/              skeleton code per phase — DONE for all 9 phases
solutions/              reference implementations — IN PROGRESS (phase_08 only,
                        currently on main; branch-vs-directory decision pending,
                        see docs/adversarial-analysis-v2.md #7)
examples/               runnable examples per phase — DONE for all 9 phases
```

Run `make status` for the live completion matrix — trust it over any static list.

---

## Current focus

Resolving the findings of the Round 2 adversarial analysis — see
`docs/adversarial-analysis-v2.md` (risk matrix + priority tiers). Headlines:
- Reference solutions for phases 0–7 do not exist yet
- Doc↔skeleton↔test contract drift is being reconciled (skeleton+tests win on conflict)
- `docs/implementation-plan.md` is a historical snapshot — its "current state" and
  hour totals are stale; do not trust them over the filesystem / `make status`

---

## How testing works

```bash
AKANGA_SRC=./src make test PHASE=2     # learner's code in ./src
make test-solution PHASE=2             # reference solution (only exists for phase 8)
make test-all                          # all phases against solutions/ dirs that exist
```

The `AKANGA_SRC` env var points pytest at learner code. If it is unset, the Makefile
warns and defaults to `./src`; if the directory is missing, `tests/conftest.py`
**fails fast with a clear error** (there is NO fallback to solutions). Always set it
explicitly when testing learner code.

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
| Solutions on separate branch | DECIDED YES in Round 1, **never implemented** — no `solutions` branch exists; `solutions/phase_08/` sits on `main` and all Makefile/CI tooling reads the working tree. Re-decision pending (adversarial-analysis-v2 #7) |
| Solo/Group Reflect tracks | YES — `> **Solo:**` / `> **Group:**` callouts |
| Open-ended vault exercises | YES — replace half of fixed tables with open prompts |
| Prerequisite self-assessment | YES — checklist at top of each phase doc |

---

## Things NOT to do

- Do not modify `solutions/` content without flagging it — the branch-vs-directory decision is unresolved (adversarial-analysis-v2 #7); note that the current `solutions/phase_08/` is known-broken (fails its own phase tests)
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
