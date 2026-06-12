# CLAUDE.md — Akanga Mirin Contributor Guide for Claude Code

This file provides context for Claude Code sessions working on the **akanga_mirin**
repository (the learning path).

---

## Two kinds of sessions: contributor vs learner

This file is written for **contributor** sessions (working on the curriculum
itself). **Learner** sessions — someone studying a phase — run under the tutor
brief in `.claude/commands/tutor.md` instead: doc routing, a hint ladder, and
hard anti-spoiler rules (never open `solutions/` for the learner's current or
future phases; `make peek` is the only sanctioned escape hatch). `make study`
launches Claude with `/tutor <phase>` automatically. If someone is clearly
asking learning questions about a phase and `/tutor` hasn't run, suggest they
run `/tutor <phase>` and follow the tutor brief, not the contributor focus below.

---

## What this repo is

A structured build-to-learn curriculum that teaches Python developers systems-level
concepts by having them build a personal knowledge graph in 9 phases (10 phase docs —
Phase 1 is split into 1A + 1B). Each phase ships as a set of parallel artifacts:

- A phase doc (`docs/learning/phase-NN-*.md`) — the spec and guide
- A skeleton (`skeletons/phase_NN/`) — stub code with WHAT/WHY/HOW docstrings
- A test suite (`tests/phase_NN/`) — pytest tests run against learner code
- A reference solution (`solutions/phase_NN/`) — lives on `main`
- A runnable example (`examples/phase_NN/`)

---

## Repo structure at a glance

```
docs/learning/          phase docs (Phase 1 split into 1A + 1B)
docs/foundations/       background explainer docs
docs/                   planning, analyses, facilitator guide — map in docs/README.md
scripts/                study.sh, skeleton_check.py, skeleton_merge.py,
                        sync_forward.py + sync_manifest.toml,
                        check_doc_contracts.py, validate_vault.py
templates/              project-makefile template for learners
tests/                  phase test suites
skeletons/              skeleton code per phase
solutions/              reference implementations (on main; usage norms in
                        solutions/README.md)
examples/               runnable examples per phase
```

**This file carries no completion claims.** Run `make status` for the live
skeleton/tests/solution matrix; current findings, adopted decisions, and the
remediation handoff live in `docs/status-remediation.md`. Trust the tooling and
that log over any prose — including this file.

---

## Current focus

Round 4 remediation — resolving the findings of `docs/adversarial-analysis-v4.md`
(consolidated findings, risk matrix, and priority tiers). The running handoff log
with per-finding status and adopted decisions is `docs/status-remediation.md`.

---

## How testing works

```bash
AKANGA_SRC=./src make test PHASE=2     # learner's code in ./src
make test-solution PHASE=2             # reference solution for one phase
make verify PHASE=3                    # cumulative: solution N against suites 0..N
make test-all                          # all phases against their solutions/ trees
```

The `AKANGA_SRC` env var points pytest at learner code; if unset it defaults to
`./src`. If the directory is missing, `tests/conftest.py` **fails fast with a clear
error** (there is NO fallback to solutions). Always set it explicitly when testing
learner code.

---

## Makefile key targets

```bash
make help               # full target list with descriptions
make status             # phase completion matrix (skeleton/tests/solution per phase)
make where-is-my-src    # show what AKANGA_SRC resolves to

make study PHASE=3      # three-pane tmux study session
make docs-phase PHASE=2 # open a phase doc in glow
make foundations TOPIC=sqlite-basics  # open a foundation doc in glow

make vault-init         # create ./vault + canonical akanga.yaml
make vault-check PHASE=2  # validate the vault (per-phase node manifest; FULL=1 for the end-of-path check)

make run                # launch the learner's TUI from AKANGA_SRC (Phase 5+)
make serve              # launch the learner's FastAPI server (Phase 6+)
make mcp                # launch the learner's MCP server (Phase 8; binds 127.0.0.1)

make resume             # show last green phase + commands to continue
make peek PHASE=2 FILE=akanga_core/parser.py  # one solution file, logged in PEEKS.md
make checkpoint         # commit src/ + vault/ into the private learner repo

make lint               # ruff check
make sync-forward FROM=2 FILE=src/akanga_core/parser.py BASE=solutions  # propagate a fix (BASE explicit: solutions|skeletons)
```

CI additionally runs the **drift gate** (`sync_forward.py --check-all` — multi-copy
modules must stay byte-identical per `scripts/sync_manifest.toml`) and the
doc-contract lint (`check_doc_contracts.py`). A **weekly canary workflow**
(`.github/workflows/canary.yml`) upgrades all dependencies to latest compatible
versions and runs the suites, opening an issue on failure.

---

## Key design decisions (full decision log: docs/status-remediation.md)

| Decision | Resolution |
|---|---|
| Split Phase 1 into 1A + 1B | YES — edge schema / workspace registry boundary |
| Solutions on separate branch | **REVERSED 2026-06-10** — solutions live in `solutions/phase_NN/` on `main`; tooling and CI read the working tree |
| Solo/Group Reflect tracks | YES — `> **Solo:**` / `> **Group:**` callouts |
| Open-ended vault exercises | YES — replace half of fixed tables with open prompts |
| Prerequisite self-assessment | YES — checklist at top of each phase doc |

---

## Things NOT to do

- `solutions/phase_NN/` on `main` is the authoritative home for reference solutions — contributions welcome, but every solution must pass its own phase test suite (`make test-solution PHASE=N`) before merge
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

Three security properties are enforced in this curriculum's own `solutions/` and
`skeletons/` trees (they originate from fixes in the noteapp reference
implementation that preceded this repo):

- SEC-02: path traversal — `Path.resolve().is_relative_to()` containment in the Phase 6/8 `server.py` trees
- SEC-06: FTS5 operator injection — user terms wrapped in double quotes in `db.py`
- SEC-01/04: Phase 8 wraps LLM context in `[KNOWLEDGE GRAPH CONTEXT]` delimiters and binds MCP to `127.0.0.1`

See `SECURITY.md` for the disclosure process.
