# Implementation Plan — Akanga Mirin

> **Audience:** contributors. HISTORICAL snapshot (May 2026) — status and hour
> totals are stale; trust `make status` and `adversarial-analysis-v2.md` instead.

> **Audience:** Contributors and maintainers executing the post-analysis work.
> **Status:** Active. Derived from 9 specialist agent outputs. All decisions are agreed
> (see `docs/analysis-and-enhancements.md`). Tasks are organized into sprints.
> **Total estimated effort:** ~270 hours across all categories.

---

## 1. Overview

### What This Document Is

This is the single authoritative task list and execution guide for completing the
Akanga Mirin learning repository. It consolidates outputs from 9 specialist agents
(architecture, security, knowledge graph theory, business/observability, pedagogy,
UX, technical writing, Makefile design, and marketing) into one sequenced plan a
developer can pick up and execute.

The specialist plan documents contain the *territory* — detailed content ready to
insert, code samples, acceptance criteria, and deep rationale. This document is the
*map* — what to do, in what order, and how long it will take.

### Current State (what already exists)

**Created by the agent session:**

- `Makefile` — full root Makefile with all targets (DONE)
- `docs/analysis-and-enhancements.md` — 23 findings + agreed decisions (DONE)
- `docs/roadmap.md` — formal MVP/V1/V2/V4+ scope boundaries (DONE)
- `docs/user-stories.md` — 38 user stories tagged by version (DONE)
- `docs/deployment.md` — macOS launchd, Linux systemd, tmux deployment (DONE)
- `docs/observability-module.md` — structured logging, timing decorators (DONE)
- `docs/future-ideas.md` — parked features with V3/V4 scope markers (DONE)
- `docs/plan-security-and-deployment.md` — S1–S4 content + task list (DONE)
- `docs/plan-kg-theory-and-integration.md` — K1/K2/K3 content + integration analysis (DONE)
- `docs/plan-doc-and-test-strategy.md` — test strategy, cross-reference map, consistency audit (DONE)
- `docs/plan-makefile-strategy.md` — MF-1 through MF-8 task list (DONE)
- `docs/learning/phase-00-*.md` through `docs/learning/phase-08-*.md` — all 9 phase docs (DONE)
- `docs/foundations/makefile-basics.md` — Makefile foundations doc (DONE)
- `scripts/study.sh` — tmux study session script (DONE)
- `scripts/skeleton_check.py` — skeleton integrity checker (DONE)
- `templates/project-makefile` — learner's own project Makefile (DONE)

**Not yet created (the work of this plan):**

- `tests/` directory — no runnable test files exist
- `solutions/` directory — no reference implementations exist
- `skeletons/` directory — no skeleton files exist
- `examples/` directory — no runnable micro-examples exist
- `docs/README.md` — no docs navigation index
- `docs/foundations/` — 10 foundation docs (only `makefile-basics.md` exists)
- `docs/facilitator-guide.md` — no facilitator guide
- `docs/workshop-brief.md` — no workshop brief
- Root `README.md` content — exists but needs full rewrite for marketing
- All phase doc enhancements — pitfalls, reflect sections, KG theory sections, security callouts
- Observability implementation — `--verbose` flag, `@timed` decorator, `/health` endpoint

### How to Read This Document

- **Section 2** shows the target repository structure with DONE/TODO annotations.
- **Section 3** is the master task list organized by category.
- **Section 4** organizes tasks into 5 sprints — this is what to execute.
- **Section 5** identifies the critical path and risks.
- **Section 6** is a reference table pointing to each specialist plan document.
- **Section 7** lists what is explicitly out of scope.

Start with Section 4 (sprint plan) for the execution sequence. Use Section 3 to look
up any task's dependencies, effort, and status.

---

## 2. Repository Target Structure

The structure below shows what the repo should look like after full implementation.
`[DONE]` = exists now. `[TODO]` = needs to be created.

```
akanga_mirin/
├── Makefile                               [DONE]
├── README.md                              [TODO — MKT-01: full rewrite]
├── CONTRIBUTING.md                        [TODO — MKT-03]
├── pyproject.toml                         [DONE]
├── docs/
│   ├── README.md                          [TODO — MKT-02: navigation index]
│   ├── implementation-plan.md             [DONE — this file]
│   ├── analysis-and-enhancements.md       [DONE]
│   ├── roadmap.md                         [DONE]
│   ├── user-stories.md                    [DONE]
│   ├── observability-module.md            [DONE]
│   ├── deployment.md                      [DONE]
│   ├── future-ideas.md                    [DONE]
│   ├── plan-security-and-deployment.md    [DONE]
│   ├── plan-kg-theory-and-integration.md  [DONE]
│   ├── plan-doc-and-test-strategy.md      [DONE]
│   ├── plan-makefile-strategy.md          [DONE]
│   ├── facilitator-guide.md               [TODO — PED-13]
│   ├── workshop-brief.md                  [TODO — MKT-04]
│   ├── learning/
│   │   ├── phase-00-file-system-as-database.md  [DONE + enhancements TODO]
│   │   ├── phase-01-data-modeling.md            [DONE + enhancements TODO]
│   │   ├── phase-02-storage-and-indexing.md     [DONE + enhancements TODO]
│   │   ├── phase-03-graph-algorithms.md         [DONE + enhancements TODO]
│   │   ├── phase-04-concurrency-and-events.md   [DONE + enhancements TODO]
│   │   ├── phase-05-terminal-ui.md              [DONE + enhancements TODO]
│   │   ├── phase-06-rest-api.md                 [DONE + enhancements TODO]
│   │   ├── phase-07-version-control.md          [DONE + enhancements TODO]
│   │   └── phase-08-ai-integration.md           [DONE + enhancements TODO]
│   └── foundations/
│       ├── makefile-basics.md             [DONE]
│       ├── design-patterns.md             [DONE]
│       ├── relation-vocabulary.md         [DONE — 71 built-in relation types]
│       ├── python-type-annotations.md     [TODO — PED-10]
│       ├── python-dataclasses.md          [TODO — PED-10]
│       ├── yaml-and-markdown-frontmatter.md [TODO — PED-10]
│       ├── git-basics.md                  [TODO — PED-10]
│       ├── sqlite-basics.md               [TODO — PED-10]
│       ├── python-threading.md            [TODO — PED-10]
│       ├── asyncio-primer.md              [TODO — PED-10]
│       ├── terminal-and-tmux-basics.md    [TODO — PED-10]
│       ├── http-fundamentals.md           [TODO — PED-10]
│       └── json-rpc-basics.md             [TODO — PED-10]
├── tests/
│   ├── conftest.py                        [TODO — ARCH-01]
│   ├── phase_00/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_parser.py                 [TODO — ARCH-19]
│   ├── phase_01/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_schema.py                 [TODO — ARCH-20]
│   ├── phase_02/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_db.py                     [TODO — ARCH-21]
│   ├── phase_03/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_graph.py                  [TODO — ARCH-22]
│   ├── phase_04/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_eventbus.py               [TODO — ARCH-23]
│   ├── phase_05/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_tui.py                    [TODO — ARCH-24]
│   ├── phase_06/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_api.py                    [TODO — ARCH-25]
│   ├── phase_07/
│   │   ├── conftest.py                    [TODO — ARCH-01]
│   │   └── test_commit_queue.py           [TODO — ARCH-26]
│   └── phase_08/
│       ├── conftest.py                    [TODO — ARCH-01]
│       └── test_rag.py                    [TODO — ARCH-27]
├── solutions/
│   ├── phase_00/src/akanga_core/          [TODO — ARCH-10]
│   ├── phase_01/src/akanga_core/          [TODO — ARCH-11]
│   ├── phase_02/src/akanga_core/          [TODO — ARCH-12]
│   ├── phase_03/src/akanga_core/          [TODO — ARCH-13]
│   ├── phase_04/src/akanga_core/          [TODO — ARCH-14]
│   ├── phase_05/src/                      [TODO — ARCH-15]
│   ├── phase_06/src/                      [TODO — ARCH-16]
│   ├── phase_07/src/                      [TODO — ARCH-17]
│   └── phase_08/src/                      [TODO — ARCH-18]
├── skeletons/
│   ├── phase_00/src/akanga_core/          [TODO — ARCH-02]
│   ├── phase_01/src/akanga_core/          [TODO — ARCH-03]
│   ├── phase_02/src/akanga_core/          [TODO — ARCH-04]
│   ├── phase_03/src/akanga_core/          [TODO — ARCH-05]
│   ├── phase_04/src/akanga_core/          [TODO — ARCH-06]
│   ├── phase_05/src/                      [TODO — ARCH-07]
│   ├── phase_06/src/                      [TODO — ARCH-08]
│   ├── phase_07/src/                      [TODO — ARCH-08]
│   └── phase_08/src/                      [TODO — ARCH-09]
├── examples/
│   └── foundations/
│       ├── phase_00_parser_demo.py        [TODO — PED-11]
│       ├── phase_01_schema_demo.py        [TODO — PED-11]
│       ├── phase_02_wal_demo.py           [TODO — PED-11]
│       ├── phase_03_bfs_demo.py           [TODO — PED-11]
│       ├── phase_04_eventbus_demo.py      [TODO — PED-11]
│       ├── phase_05_textual_demo.py       [TODO — PED-11]
│       ├── phase_06_fastapi_demo.py       [TODO — PED-11]
│       ├── phase_07_queue_demo.py         [TODO — PED-11]
│       ├── phase_08_rag_demo.py           [TODO — PED-11]
│       └── phase_09_makefile_demo.py      [TODO — PED-11]
├── scripts/
│   ├── study.sh                           [DONE]
│   └── skeleton_check.py                  [DONE]
└── templates/
    └── project-makefile                   [DONE]
```

**Directory purposes:**
- `tests/` — one pytest file per phase. Run against learner code or solutions via `AKANGA_SRC`.
- `solutions/` — cumulative reference implementations. Phase N contains all Phase 0..N code.
- `skeletons/` — stub files with `NotImplementedError` bodies and rich docstrings. Learner fills them in.
- `examples/foundations/` — standalone ~30-line runnable scripts demonstrating one concept each.

---

## 3. Master Task List

Tasks are grouped by category. Each task shows its ID, title, effort estimate,
dependencies, status, and originating agent.

For full task details (content, code samples, acceptance criteria), see the referenced
specialist plan document in Section 6.

### 3.1 Infrastructure (tests, solutions, skeletons)

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| ARCH-01 | Create `tests/conftest.py` + all phase `conftest.py` files | 7h | Nothing | TODO |
| ARCH-02 | Create skeleton for Phase 0 (`parser.py`) | 1.5h | Nothing | TODO |
| ARCH-03 | Create skeleton for Phase 1 (`schema.py`, edge extraction) | 1.5h | Nothing | TODO |
| ARCH-04 | Create skeleton for Phase 2 (`db.py`, `indexer.py`) | 2h | Nothing | TODO |
| ARCH-05 | Create skeleton for Phase 3 (`graph.py`) | 1.5h | Nothing | TODO |
| ARCH-06 | Create skeleton for Phase 4 (`eventbus.py`, `watcher.py`) | 1.5h | Nothing | TODO |
| ARCH-07 | Create skeleton for Phase 5 (TUI module stubs) | 2h | Nothing | TODO |
| ARCH-08 | Create skeletons for Phases 6 and 7 (server + git stubs) | 2h | Nothing | TODO |
| ARCH-09 | Create skeleton for Phase 8 (`rag.py`, MCP stubs) | 2h | Nothing | TODO |
| ARCH-10 | Create `solutions/phase_00/` reference implementation | 3h | Bug fixes TW-01..TW-03 | TODO |
| ARCH-11 | Create `solutions/phase_01/` (Phase 0 + Phase 1 code) | 4h | ARCH-10 | TODO |
| ARCH-12 | Create `solutions/phase_02/` (cumulative through Phase 2) | 5h | ARCH-11 | TODO |
| ARCH-13 | Create `solutions/phase_03/` (cumulative through Phase 3) | 5h | ARCH-12 | TODO |
| ARCH-14 | Create `solutions/phase_04/` (cumulative through Phase 4) | 6h | ARCH-13 | TODO |
| ARCH-15 | Create `solutions/phase_05/` (cumulative through Phase 5) | 8h | ARCH-14 | TODO |
| ARCH-16 | Create `solutions/phase_06/` (cumulative through Phase 6) | 6h | ARCH-15 | TODO |
| ARCH-17 | Create `solutions/phase_07/` (cumulative through Phase 7) | 5h | ARCH-16 | TODO |
| ARCH-18 | Create `solutions/phase_08/` (cumulative through Phase 8) | 6h | ARCH-17 | TODO |
| ARCH-19 | Create `tests/phase_00/test_parser.py` | 2h | ARCH-01 | TODO |
| ARCH-20 | Create `tests/phase_01/test_schema.py` | 2h | ARCH-01 | TODO |
| ARCH-21 | Create `tests/phase_02/test_db.py` | 2.5h | ARCH-01 | TODO |
| ARCH-22 | Create `tests/phase_03/test_graph.py` | 2.5h | ARCH-01 | TODO |
| ARCH-23 | Create `tests/phase_04/test_eventbus.py` | 3h | ARCH-01 | TODO |
| ARCH-24 | Create `tests/phase_05/test_tui.py` | 4h | ARCH-01 | TODO |
| ARCH-25 | Create `tests/phase_06/test_api.py` | 3h | ARCH-01 | TODO |
| ARCH-26 | Create `tests/phase_07/test_commit_queue.py` | 4h | ARCH-01 | TODO |
| ARCH-27 | Create `tests/phase_08/test_rag.py` | 4h | ARCH-01 | TODO |

**Category total: ~95h**

See `docs/plan-doc-and-test-strategy.md` §2 for the full test strategy and per-phase test count.

### 3.2 Phase Doc Enhancements

All enhancements are additive — no existing content is removed or changed.

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| PED-01 | Add time estimate one-liner to all 9 phase docs | 0.5h | Nothing | TODO |
| PED-02 | Add K3 graph validation paragraph to Phase 1 | 0.25h | Nothing | TODO |
| PED-03 | Add K1 "Extending the Vocabulary" section to Phase 1 | 0.5h | PED-02 | TODO |
| PED-04 | Add K2 "Traversal Tradeoffs" section to Phase 3 | 0.5h | Nothing | TODO |
| PED-05 | Add Scaling Notes to Phase 2 and Phase 3 | 1h | Nothing | TODO |
| PED-06 | Add Common Pitfalls section to all 9 phase docs | 4h | Nothing | TODO |
| PED-07 | Add Reflect section to all 9 phase docs | 3h | PED-06 | TODO |
| PED-08 | Add Checkpoint Exercises to Phase 5 doc | 1h | Nothing | TODO |
| PED-09 | Add Checkpoint Exercises to Phase 6 doc | 1h | Nothing | TODO |
| PED-12 | Add foundation doc links (Reference section) to all phase docs | 1h | PED-10 | TODO |
| TW-03a | Apply consistent 11-section header template to all 9 phase docs | 3h | Nothing | TODO |
| TW-03b | Add backward-reference "recall" notes to all phase docs | 3h | Nothing | TODO |
| TW-03c | Add "coming up" forward notice to all phase transitions | 0.75h | Nothing | TODO |
| KG-INT1 | Add cross-cutting forward/backward references (EventBus, FTS5, ego-graph, WAL) | 1.5h | Nothing | TODO |
| KG-THEORY | Add "Broader Context" KG ecosystem sidebar to Phase 1 | 0.5h | Nothing | TODO |
| SEC-T2 | Insert S3 YAML safe loader callout into Phase 0 | 0.5h | Nothing | TODO |
| SEC-T3 | Insert S1 SQL injection callout into Phase 2 | 0.33h | Nothing | TODO |
| SEC-T4 | Insert S2 CORS callout into Phase 6 | 0.42h | Nothing | TODO |
| SEC-T5 | Insert S4 git remote trust callout into Phase 7 | 0.33h | Nothing | TODO |
| SEC-T7 | Add structural security paragraphs (trust boundary, Phase 8 MCP) | 1.5h | SEC-T2..T5 | TODO |
| MF-04 | Add Makefile quick-reference callout to all 9 phase docs | 1h | Nothing | TODO |
| MF-05 | Add `makefile-basics.md` link to Phase 0 | 0.17h | Nothing | TODO |
| UX-01 | Reformat phase doc tables as definition lists for glow rendering | 2h | Nothing | TODO |
| UX-02 | Enforce 55-char code line limit in all phase docs | 2h | Nothing | TODO |

**Category total: ~29h**

See `docs/plan-security-and-deployment.md` for S1–S4 insertion content.
See `docs/plan-kg-theory-and-integration.md` for K1/K2/K3 section text.
See `docs/plan-doc-and-test-strategy.md` §1 for cross-reference map and section template.

### 3.3 New Documentation

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| PED-10 | Create `docs/foundations/` — 10 explainer docs | 8h | Nothing | TODO |
| PED-11 | Create `examples/foundations/` — 10 micro-example scripts | 4h | PED-10 | TODO |
| PED-13 | Create `docs/facilitator-guide.md` | 2h | PED-01..PED-09 | TODO |
| TW-01a | Create root `README.md` (navigation + quick start) | 2h | Nothing | TODO |
| TW-01b | Create `docs/README.md` (docs tree map) | 1h | Nothing | TODO |
| MF-03 | Create `docs/foundations/makefile-basics.md` | 0h | Nothing | DONE |
| MKT-01 | Write root README.md (marketing + full rewrite) | 4h | TW-01a | TODO |
| MKT-02 | Write `docs/README.md` — learner navigation | 1.5h | Nothing | TODO |
| MKT-03 | Write `CONTRIBUTING.md` — open source guide | 2.5h | Nothing | TODO |
| MKT-04 | Write `docs/workshop-brief.md` — one-page proposal template | 3.5h | PED-13 | TODO |

**Category total: ~29h**

Note: MKT-01 and TW-01a overlap in scope. MKT-01 is the final version; TW-01a is the
minimal functional version. Execute TW-01a first so the repo is navigable, then expand
to MKT-01 in Sprint 5.

### 3.4 Implementation Tasks (code to write)

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| BIZ-01 | Wire `--verbose` flag into all Akanga CLI commands | 1.5h | Nothing | TODO |
| BIZ-02 | Implement `@timed` decorator and `TimedConnection` | 2h | Nothing | TODO |
| BIZ-03 | Implement `MetricsRegistry` + `GET /metrics` endpoint | 1.5h | BIZ-02 | TODO |
| BIZ-04 | Implement `GET /health` structured endpoint | 1.5h | Nothing | TODO |
| BIZ-05 | Add JSON log formatter and rotating file handler | 1h | Nothing | TODO |
| UX-03 | Fix `COL_DIM` color in TUI (`#585b70` → `#6c7086`) | 0.25h | Nothing | TODO |
| UX-04 | Add shape encoding to graph renderer (color-blind accessibility) | 2h | Nothing | TODO |
| UX-05 | Implement density-adaptive edge labels in graph renderer | 2h | Nothing | TODO |
| UX-06 | Update `study.sh` to open skeleton file in neovim (not directory) | 0.25h | Nothing | TODO |
| MF-06 | Smoke-test all Makefile targets | 1.5h | ARCH-10..ARCH-19 | TODO |
| MF-07 | Integration-test learner's project Makefile template | 0.75h | Nothing | TODO |
| MF-08 | Makefile review pass | 0.75h | MF-06, MF-07 | TODO |
| SEC-T1 | Verify `python-frontmatter` safe loader and document version | 0.5h | Nothing | TODO |
| SEC-T6 | Write `docs/deployment.md` | 0h | Nothing | DONE |
| SEC-T8 | Security review and cross-link pass | 0.75h | SEC-T2..T6 | TODO |

**Category total: ~20h**

See `docs/observability-module.md` for full observability implementation specs.
See `docs/plan-security-and-deployment.md` §Part 4 for security task acceptance criteria.

### 3.5 Bug Fixes (factual contradictions)

These must be completed before solutions are written. A latent bug in the spec
propagates to all 8 later solutions if not fixed first.

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| TW-BUG-01 | Fix Phase 8: `node.body` accessed from DB object (DB never stores body text) | 0.5h | Nothing | TODO |
| TW-BUG-02 | Fix Phase 4: "(Phase 8)" cross-ref for git auto-commit should be "(Phase 7)" | 0.25h | Nothing | TODO |
| TW-BUG-03 | Fix Phase 6: ego-graph endpoint returns JSON, not rendered image | 0.33h | Nothing | TODO |
| TW-BUG-04 | Fix Phase 7: replace "notes" with "nodes" in commit message examples | 0.33h | Nothing | TODO |
| TW-BUG-05 | Fix Phase 1: Move `FastMCP` vault node entry to Phase 8 | 0.25h | Nothing | TODO |
| TW-BUG-06 | Add YAML-vs-Python naming note to Phase 1 Edge Format section | 0.33h | Nothing | TODO |
| TW-BUG-07 | Add node type clarification note (learning path vs production types) | 0.25h | Nothing | TODO |
| TW-BUG-08 | Add `# Partial` comment to Phase 3 stub code lines | 0.17h | Nothing | TODO |

**Category total: ~2.5h**

See `docs/plan-doc-and-test-strategy.md` §4.5 for full analysis of each contradiction.

### 3.6 Marketing

| ID | Title | Hours | Depends On | Status |
|----|-------|-------|------------|--------|
| MKT-01 | Write root `README.md` — full marketing rewrite | 4h | TW-01a | TODO |
| MKT-02 | Write `docs/README.md` — learner navigation index | 1.5h | Nothing | TODO |
| MKT-03 | Write `CONTRIBUTING.md` — open source contribution guide | 2.5h | Nothing | TODO |
| MKT-04 | Write `docs/workshop-brief.md` — workshop proposal template | 3.5h | PED-13 | TODO |
| MKT-05 | Write launch blog post (GitHub Discussions / dev.to) | 5h | MKT-01 | TODO |

**Category total: ~17h**

Key marketing content (from marketing agent):

Elevator pitch: "Akanga Mirin is a project-based curriculum where you build a personal
knowledge graph from scratch — in nine phases. You start with nothing but a file system
and atomic writes. By the end, you have a working TUI, a REST API, git-backed history,
and an AI integration using the Model Context Protocol. Every phase produces something
you can actually use. No cloud, no subscription, no toy project."

README hook: "Across nine phases, you construct a personal, offline-first knowledge
graph: from atomic file writes and UUID identity through SQLite indexing, graph
algorithms, a Textual TUI, a FastAPI server, GitPython version control, and finally
an AI layer using the Model Context Protocol."

Key callouts: "Ship a working artifact at the end of every phase." / "Your knowledge
graph. Your vault. No cloud required." / "Nine phases. One artifact. Zero subscriptions."

---

## 4. Implementation Sequence (Sprints)

### Sprint 1 — Foundation (Unblocks Everything)

**Total effort: ~35h**
**Goal: Repo becomes runnable — learner can clone, run `make test PHASE=0`, see pass/fail.**

- [ ] TW-BUG-01 — Fix Phase 8 `node.body` contradiction (0.5h)
- [ ] TW-BUG-02 — Fix Phase 4 "(Phase 8)" cross-ref (0.25h)
- [ ] TW-BUG-03 — Fix Phase 6 ego-graph endpoint description (0.33h)
- [ ] TW-BUG-04 — Fix Phase 7 "notes" vs "nodes" (0.33h)
- [ ] TW-BUG-05 — Move FastMCP vault node to Phase 8 (0.25h)
- [ ] TW-BUG-06 — YAML-vs-Python naming note in Phase 1 (0.33h)
- [ ] TW-BUG-07 — Node type clarification note (0.25h)
- [ ] TW-BUG-08 — Phase 3 stub code comment (0.17h)
- [ ] ARCH-01 — Create `tests/conftest.py` + all phase conftest files (7h)
- [ ] ARCH-02 — Skeleton: Phase 0 (`parser.py`) (1.5h)
- [ ] ARCH-10 — Solution: Phase 0 reference implementation (3h)
- [ ] ARCH-19 — Test file: `tests/phase_00/test_parser.py` (2h)
- [ ] TW-01a — Root `README.md` minimal version (2h)
- [ ] TW-01b — `docs/README.md` minimal navigation index (1h)
- [ ] SEC-T1 — Verify `python-frontmatter` safe loader (0.5h)
- [ ] MF-07 — Integration-test learner Makefile template (0.75h)
- [ ] UX-06 — Fix `study.sh` to open skeleton file in neovim (0.25h)
- [ ] UX-03 — Fix TUI `COL_DIM` color (0.25h)

**What becomes usable after Sprint 1:**
A learner can clone the repo, run `make setup`, run `make skeleton PHASE=0`,
implement Phase 0, and run `make test PHASE=0` to see pass/fail results. The
bug fixes eliminate latent errors that would corrupt later solutions. The root
README tells them where to start.

---

### Sprint 2 — Phase Doc Structure

**Total effort: ~35h**
**Goal: All 9 phase docs have complete structure — time estimates, pitfalls, reflect,
KG theory sections, security callouts, and consistent header format.**

- [ ] PED-01 — Time estimate one-liners in all 9 phase docs (0.5h)
- [ ] PED-02 — K3 graph validation paragraph in Phase 1 (0.25h)
- [ ] PED-03 — K1 "Extending the Vocabulary" in Phase 1 (0.5h)
- [ ] PED-04 — K2 "Traversal Tradeoffs" in Phase 3 (0.5h)
- [ ] PED-05 — Scaling Notes in Phase 2 and Phase 3 (1h)
- [ ] PED-06 — Common Pitfalls in all 9 phase docs (4h)
- [ ] PED-07 — Reflect sections in all 9 phase docs (3h)
- [ ] PED-08 — Checkpoint Exercises in Phase 5 (1h)
- [ ] PED-09 — Checkpoint Exercises in Phase 6 (1h)
- [ ] TW-03a — Apply consistent 11-section template to all 9 phase docs (3h)
- [ ] TW-03b — Backward-reference "recall" notes in all phase docs (3h)
- [ ] TW-03c — "Coming up" forward notices for all 8 transitions (0.75h)
- [ ] KG-INT1 — Cross-cutting forward/backward references (EventBus, FTS5, ego-graph, WAL) (1.5h)
- [ ] KG-THEORY — "Broader Context" KG ecosystem sidebar in Phase 1 (0.5h)
- [ ] SEC-T2 — S3 YAML safe loader callout in Phase 0 (0.5h)
- [ ] SEC-T3 — S1 SQL injection callout in Phase 2 (0.33h)
- [ ] SEC-T4 — S2 CORS callout in Phase 6 (0.42h)
- [ ] SEC-T5 — S4 git remote trust callout in Phase 7 (0.33h)
- [ ] SEC-T7 — Structural security paragraphs (1.5h)
- [ ] SEC-T8 — Security review and cross-link pass (0.75h)
- [ ] MF-04 — Makefile quick-reference callouts in all 9 phase docs (1h)
- [ ] MF-05 — `makefile-basics.md` link in Phase 0 (0.17h)
- [ ] MF-08 — Makefile review pass (0.75h)
- [ ] UX-01 — Reformat phase doc tables as definition lists (2h)
- [ ] UX-02 — Enforce 55-char code line limit in phase docs (2h)

**What becomes usable after Sprint 2:**
All 9 phase docs are complete pedagogically. A learner can read any phase and find:
the time estimate, prerequisite context, KG theory context, security guidance,
common mistakes, checkpoints (where applicable), and reflection prompts. The path
is ready for workshop delivery using the existing phase docs, even before solutions
are complete.

---

### Sprint 3 — New Documentation

**Total effort: ~30h**
**Goal: Foundation docs exist, facilitator guide exists, examples exist.**

- [ ] PED-10 — Create `docs/foundations/` 10 explainer docs (8h)
- [ ] PED-11 — Create `examples/foundations/` 10 micro-example scripts (4h)
- [ ] PED-12 — Add foundation doc links (Reference section) to all phase docs (1h)
- [ ] PED-13 — Create `docs/facilitator-guide.md` (2h)
- [ ] BIZ-01 — Wire `--verbose` flag into CLI (1.5h)
- [ ] BIZ-02 — Implement `@timed` decorator and `TimedConnection` (2h)
- [ ] BIZ-03 — Implement `MetricsRegistry` + `GET /metrics` (1.5h)
- [ ] BIZ-04 — Implement `GET /health` structured endpoint (1.5h)
- [ ] BIZ-05 — JSON log formatter and rotating file handler (1h)
- [ ] UX-04 — Shape encoding in graph renderer (2h)
- [ ] UX-05 — Density-adaptive edge labels in graph renderer (2h)

**What becomes usable after Sprint 3:**
A learner who hits a wall in Phase 0 can open `docs/foundations/python-dataclasses.md`
(12-minute read) and continue. Foundation docs reduce dropout at Phase 0 entry.
Observability features make the production tool debuggable. The facilitator guide
enables the first workshop run.

---

### Sprint 4 — Complete Test Suite and All Solutions

**Total effort: ~100h**
**Goal: `make test-all` passes. Every phase is fully testable end-to-end.**

Skeletons (can be parallelized across contributors):
- [ ] ARCH-03 — Skeleton: Phase 1 (1.5h)
- [ ] ARCH-04 — Skeleton: Phase 2 (2h)
- [ ] ARCH-05 — Skeleton: Phase 3 (1.5h)
- [ ] ARCH-06 — Skeleton: Phase 4 (1.5h)
- [ ] ARCH-07 — Skeleton: Phase 5 (2h)
- [ ] ARCH-08 — Skeletons: Phase 6 and 7 (2h)
- [ ] ARCH-09 — Skeleton: Phase 8 (2h)

Test files (can be parallelized, depends on ARCH-01 from Sprint 1):
- [ ] ARCH-20 — Test: Phase 1 `test_schema.py` (2h)
- [ ] ARCH-21 — Test: Phase 2 `test_db.py` (2.5h)
- [ ] ARCH-22 — Test: Phase 3 `test_graph.py` (2.5h)
- [ ] ARCH-23 — Test: Phase 4 `test_eventbus.py` (3h)
- [ ] ARCH-24 — Test: Phase 5 `test_tui.py` (4h)
- [ ] ARCH-25 — Test: Phase 6 `test_api.py` (3h)
- [ ] ARCH-26 — Test: Phase 7 `test_commit_queue.py` (4h)
- [ ] ARCH-27 — Test: Phase 8 `test_rag.py` (4h)

Solutions (strictly serial — each builds on the previous):
- [ ] ARCH-11 — Solution: Phase 1 (cumulative 0–1) (4h)
- [ ] ARCH-12 — Solution: Phase 2 (cumulative 0–2) (5h)
- [ ] ARCH-13 — Solution: Phase 3 (cumulative 0–3) (5h)
- [ ] ARCH-14 — Solution: Phase 4 (cumulative 0–4) (6h)
- [ ] ARCH-15 — Solution: Phase 5 (cumulative 0–5) (8h)
- [ ] ARCH-16 — Solution: Phase 6 (cumulative 0–6) (6h)
- [ ] ARCH-17 — Solution: Phase 7 (cumulative 0–7) (5h)
- [ ] ARCH-18 — Solution: Phase 8 (cumulative 0–8) (6h)
- [ ] MF-06 — Smoke-test all Makefile targets (1.5h)

**What becomes usable after Sprint 4:**
`make test-all` passes. `make verify-all` confirms cumulative correctness. Any
learner who gets stuck can run `make test-solution PHASE=N` to see a passing reference.
The learning path can be completed end-to-end.

---

### Sprint 5 — Marketing and Polish

**Total effort: ~30h**
**Goal: Repo is presentable for GitHub, ready for public announcement and workshop use.**

- [ ] MKT-01 — Root `README.md` full marketing rewrite (4h)
- [ ] MKT-02 — `docs/README.md` learner navigation (1.5h)
- [ ] MKT-03 — `CONTRIBUTING.md` open source guide (2.5h)
- [ ] MKT-04 — `docs/workshop-brief.md` workshop proposal template (3.5h)
- [ ] MKT-05 — Launch blog post (5h)

**What becomes usable after Sprint 5:**
The repo can be announced publicly. The README answers the five questions a learner
needs answered in 90 seconds. The workshop brief enables facilitators to pitch and
run the curriculum. The CONTRIBUTING guide enables external contributors.

---

## 5. Critical Path and Risk

### Longest Dependency Chain

The strictly serial solutions chain is the critical path:

```
Bug fixes (TW-BUG-01..08)
  → ARCH-10 (Phase 0 solution)
    → ARCH-11 (Phase 1 solution)
      → ARCH-12 → ARCH-13 → ARCH-14 → ARCH-15 → ARCH-16 → ARCH-17 → ARCH-18
```

**Total critical path: ~51h for solutions alone** (cannot be parallelized).

ARCH-01 (conftest.py) unblocks all 9 test files simultaneously — those CAN be
parallelized. Maximum parallelism: 9 contributors working on test files simultaneously
after ARCH-01 completes.

### Tasks That Block the Most Other Tasks

1. **ARCH-01** (conftest.py) — blocks all 9 test files. Do this first in Sprint 1.
2. **TW-BUG-01..08** (bug fixes) — must precede ARCH-10. Bugs in the spec propagate
   to all 8 subsequent solutions if written before fixes are applied.
3. **ARCH-10** (Phase 0 solution) — the root of the serial chain. All later solutions
   depend on it being correct.
4. **PED-10** (foundation docs) — blocks PED-11 (examples) and PED-12 (links).
5. **PED-01..09** (phase doc enhancements) — collectively block PED-13 (facilitator guide).

### The Critical Bug Fixes (Fix Before Writing Solutions)

These contradictions were identified by the technical writer agent and the adversarial
analysis. A solution written before fixing them will implement the wrong behavior.

**Bug 1 (TW-BUG-01): Phase 8 RAG code accesses `node.body` from a DB object.**
The DB explicitly does NOT store prose body text (established in Phase 2). The RAG
`context_for_query` example shows `node.body[:120]` — this will be empty or fail.
Resolution (strengthened by adversarial analysis):
- Replace `node.body` with `parse(node.path).body[:500] if node.path.exists() else ""`
- Add a total character cap: stop adding triples once the running total exceeds 12,000
  chars regardless of `max_triples`. A 10 MB node body must not produce gigabytes of LLM
  context.
- Explicit `desc = node.description or body` — do not chain `.description` and `.body`
  without a fallback.
Fix this before writing the Phase 8 solution (ARCH-18).

**Bug 2 (ADV-BUG-A): Phase 8 `max_triples=200` is incompatible with the `<15,000` char
assertion in `test_context_for_query`.**
200 triples × average serialized length ≈ 31,000 characters. The test will always fail.
These two limits were specified in different places without cross-checking.
Resolution: reduce `max_triples` default to 80 (yields ~12,000 chars at average length)
AND add the total character cap from Bug 1. Both constants must be set consistently
before ARCH-18 or ARCH-27 are written.

**Bug 3 (ADV-BUG-B): Inverse edge direction in Phase 8 `_serialize_triples`.**
Incoming edges (where the current node is the *target*) must be serialized using the
`inverse_id` relation name, not the forward relation name. Using the forward name
produces `B --[contradicts]--> A` from A's perspective, which silently inverts the
knowledge graph semantics passed to the LLM.
Resolution: for incoming edges, look up `inverse_id` in the relation registry and use
that name; if no `inverse_id` is defined, prefix with `<--` to indicate direction. Add
a directed-edge test that verifies serialized strings from both source and target
perspectives. Fix before ARCH-18.

**Bug 4 (TW-BUG-02): Phase 4 says git auto-commit is "(Phase 8)."**
Git integration is Phase 7. Update the cross-reference before writing Phase 4 or
Phase 7 solutions (ARCH-14, ARCH-17).

**Bug 5 (TW-BUG-03): Phase 6 ego-graph endpoint spec does not clarify return format.**
The endpoint returns JSON (nodes + edges as dicts), not a rendered image. Renderers
are TUI-specific. Clarify before writing the Phase 6 solution (ARCH-16) and test
(ARCH-25).

**Verified OK — EventBus startup race (ADV-BUG-C):**
The adversarial analysis predicted a race where `watcher.start()` fires before
`eventbus.set_loop()`. Verified against the reference implementation: `app.py`
`start_all()` calls `set_loop()` on line 141 before `self.start()` on line 142, which
calls `start_watcher()`. Startup order is correct. EventBus publish gracefully handles
missing loop (logs warning, does not crash). No fix required.

**Verified OK — macOS `os.replace()` fires `on_moved` (ADV-BUG-D):**
The adversarial analysis predicted that macOS atomic writes would be missed by the
watcher's `on_moved` handler. Verified against the reference implementation: `parser.py`
uses `tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")` — the temp file has `.md.tmp`
extension (in `IGNORED_SUFFIXES`) and lives in the same vault directory. The `on_moved`
handler in `watcher.py` checks `dest_path` independently of `src_path`. Atomic writes
trigger re-indexing correctly. No fix required.

### Design Decisions (Resolved 2026-05-24)

These five decisions were raised by the adversarial analysis and resolved by the project
owner before Sprint 1 began.

| Decision | Resolution | Impact |
|---|---|---|
| Split Phase 1 into 1A + 1B? | **YES** — split at edge schema / workspace registry boundary | Path becomes 10 phases; all phase numbering shifts after Phase 1A |
| Move solutions to separate git branch? | **YES** — `solutions` branch, not `solutions/` dir on `main` | `make solution PHASE=N` must check out the branch; no 9× propagation in `main` |
| Add Solo/Group tracks to Reflect sections? | **YES** — `> **Solo:** …` / `> **Group:** …` callouts | 9 × 2 callout blocks across all phase docs (PED-05) |
| Replace transcription vault node tables with open-ended prompts? | **YES** — replace half with open-ended "find the connection" prompts | Checkpoint auto-validation harder; deeper learning transfer (PED-04) |
| Add 2-minute prerequisite self-assessment per phase? | **YES** — checklist at top of each phase doc | 9 checklists to write; surfaces readiness gaps before learners stall mid-phase |

### Risk Register

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Phase 0 solution has an implementation bug that propagates to all 8 later solutions | Medium | High | Run `make verify PHASE=0` (cumulative check) before starting ARCH-11. Fix forward, not backward. |
| Test files written before bug fixes are applied | High (if order ignored) | Medium | Sprint 1 requires all TW-BUG-* tasks before ARCH-10. Sprint 4 test files are written against a known-correct Phase 0 solution. |
| Phase 4/5 TUI and timing tests are flaky on CI | Medium | Low | Use 50ms debounce in tests (not 500ms production value). Mark with `@pytest.mark.slow`. |
| Skeleton files accidentally contain solution code | Low | High | Run `make skeleton-check PHASE=N` after every skeleton is written. This is what `scripts/skeleton_check.py` exists for. |
| Solutions accumulation error (Phase N+1 omits Phase N code) | Medium | High | Run `make verify PHASE=N` after each solution — it re-runs tests 0..N cumulatively. |
| Foundation docs become stale relative to phase docs | Low | Low | Foundation docs cover stable Python/SQLite/git concepts, not Akanga-specific code. |

---

## 6. Specialist Plan Reference

Each specialist plan document is the authoritative source for its domain. When
executing a task in that domain, open the relevant plan for the exact content to
insert, the code examples, and the acceptance criteria.

| Domain | Document | Key Content |
|--------|----------|-------------|
| Security callouts (S1–S4) | `docs/plan-security-and-deployment.md` | Exact insertion blocks for Phases 0, 2, 6, 7. Task list T1–T8 with acceptance criteria. |
| Security architecture | `docs/plan-security-and-deployment.md` Part 3 | Structural recommendations — trust boundary, Phase 8 MCP prompt injection risk. |
| Knowledge graph theory (K1–K3) | `docs/plan-kg-theory-and-integration.md` Parts 1–3 | Complete section text for K1 (vocabulary extension), K2 (traversal tradeoffs), K3 (validation design). |
| Cross-cutting integration | `docs/plan-kg-theory-and-integration.md` Part 4 | Forward/backward reference wording for EventBus, FTS5, ego-graph, WAL integration points. |
| Test strategy | `docs/plan-doc-and-test-strategy.md` §2 | Test philosophy, per-phase test categories, test quality criteria, test count targets. |
| conftest.py design | `docs/plan-doc-and-test-strategy.md` §2.5 | Exact fixture code for `vault_config`, `populated_vault`, `tmp_db`, `indexed_db`. |
| Cross-reference map | `docs/plan-doc-and-test-strategy.md` §3 | Concept × Phase matrix showing where each concept is introduced, used, deepened. |
| Consistency fixes | `docs/plan-doc-and-test-strategy.md` §4 | All structural, terminology, and factual consistency findings with exact fix instructions. |
| Makefile targets | `docs/plan-makefile-strategy.md` Parts 1–5 | Full Makefile source, learner template, smoke-test matrix, phase doc callout format. |
| Observability implementation | `docs/observability-module.md` | `--verbose` flag, `@timed` decorator, `/health` endpoint, JSON logging, rotating handler. |
| Version scope | `docs/roadmap.md` | Authoritative MVP/V1/V2/V4+ scope definitions with done criteria. |
| User value | `docs/user-stories.md` | 38 user stories grouped by persona, tagged by version. |
| Deployment | `docs/deployment.md` | macOS launchd plist, Linux systemd user service, tmux approach, Makefile targets. |
| Future scope | `docs/future-ideas.md` | Parked features — reference this when explaining why something is out of scope. |
| All findings + decisions | `docs/analysis-and-enhancements.md` | The 23 original findings with agreed resolutions. Ground truth for any disputed decision. |

---

## 7. What NOT to Build Yet

The following features are explicitly out of scope for Phases 0–8 and for the
current work described in this plan. They are documented in `docs/future-ideas.md`
and tagged V3 or V4+ in `docs/roadmap.md`.

Do not add implementation tasks for these unless the roadmap is formally revised:

**Deferred to V4+:**
- Active nodes (HTTP health checks, TCP probes, code execution)
- Active-service nodes (long-running background services)
- Diagram/canvas nodes (Mermaid, BPMN, architecture diagrams)
- Graph visualisation enhancements beyond current renderer (node sizing by connection
  count, gravity/force weighting by relation strength, visual encoding by category prefix)
- Temporal animation (graph evolution via git history replay)
- Semantic search / vector embeddings (`sentence-transformers`, semantic seed retrieval)
- Relation inference (transitivity, symmetric inference beyond `inverse_id` lookup)
- Multi-user vaults (requires auth, access control, conflict resolution)
- Collaborative editing
- Akanga Cloud sync (requires CRDTs or git-based conflict model)
- Mobile or web client
- LlamaIndex PropertyGraphStore connector

**Explicitly excluded from the learning path (not deferred — permanently out):**
- Docker (local-first personal tool; containers add no value here and contradict the
  offline-first design philosophy)
- Any cloud authentication or credential management in the learning repo

**Out of scope for the current sprint cycle (may revisit after V2 ships):**
- Graph RAG semantic reranking (FTS5 + BFS is the intended Phase 8 architecture)
- MCP server network transport hardening beyond localhost (addressed in deployment.md)
- Workshop participant tracking or LMS integration

---

## Appendix A — conftest.py Design Reference

The root `tests/conftest.py` must implement the `_resolve_akanga_src` pattern so
tests run against either the learner's `AKANGA_SRC` or the reference solution:

```python
import os
import pytest
import yaml
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent
SOLUTIONS_DIR = REPO_ROOT / "solutions"

def _resolve_akanga_src(phase: int) -> Path:
    env_src = os.environ.get("AKANGA_SRC")
    if env_src:
        src = Path(env_src).resolve()
        if not src.exists():
            pytest.fail(
                f"AKANGA_SRC={env_src!r} does not exist. "
                f"Set it to your src/ directory or unset to use the reference solution."
            )
        return src
    fallback = SOLUTIONS_DIR / f"phase_{phase:02d}" / "src"
    if not fallback.exists():
        pytest.fail(
            f"No AKANGA_SRC set and reference solution not found at {fallback}. "
            f"Run: AKANGA_SRC=./src pytest tests/phase_{phase:02d}/"
        )
    return fallback

MINIMAL_VAULT_CONFIG = {
    "owner": "Test User",
    "default_workspace": {
        "name": "Nhamandu",
        "id": "aaaaaaaa-0000-0000-0000-000000000001"
    },
    "workspaces": [
        {"name": "Nhamandu", "id": "aaaaaaaa-0000-0000-0000-000000000001"}
    ],
    "relations": []
}

@pytest.fixture
def tmp_vault(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "akanga.yaml").write_text(yaml.dump(MINIMAL_VAULT_CONFIG))
    return vault
```

Each phase's `tests/phase_NN/conftest.py` calls `_resolve_akanga_src(N)` and inserts
the returned path into `sys.path` before importing from `akanga_core`.

See `docs/plan-doc-and-test-strategy.md` §2.5 for the complete fixture set
(`vault_config`, `populated_vault`, `tmp_db`, `indexed_db`, and phase-specific
fixtures for Phases 4–8).

---

## Appendix B — Solutions Accumulation Pattern

Each solution directory contains a complete working system up to that phase:

- `solutions/phase_00/src/` — ONLY Phase 0 code (`parser.py`)
- `solutions/phase_01/src/` — Phase 0 + Phase 1 code (copied forward, then extended)
- `solutions/phase_N/src/` — All Phase 0..N code

**Why strictly cumulative:** The test suite for Phase N tests the entire system built
so far, not just Phase N additions. `make verify PHASE=3` runs tests 00, 01, 02, and
03 against the Phase 3 solution. If Phase 3 accidentally omits Phase 1 code, tests
01 will fail and the issue is caught immediately.

**Implementation workflow for each solution:**
1. Copy the previous solution directory as a starting point.
2. Add Phase N modules and extend existing modules as specified in the phase doc.
3. Run `make verify PHASE=N` — all tests 00..N must pass.
4. Only commit when verification passes.

---

## Appendix C — Skeleton File Format

Skeleton files must have:
- Full class and method signatures with type annotations
- Rich `WHAT / WHY / HOW` docstrings explaining what the method must do
- `raise NotImplementedError("TODO: specific hint")` in every method body
- NO implementation code (enforced by `make skeleton-check PHASE=N`)

Example (`parser.py` skeleton):

```python
def parse(path: Path) -> Node:
    """
    WHAT: Read a Markdown file with YAML frontmatter and return a Node dataclass.
    WHY: The file is the source of truth; the DB is a derived index.
         Everything starts with a clean parse of the frontmatter.
    HOW: Use python-frontmatter to load the file. Map frontmatter keys to
         Node fields. Generate a UUID if the 'id' field is absent and write
         it back immediately (so future parses return the same UUID).
    """
    raise NotImplementedError(
        "TODO: use frontmatter.load(path), map keys to Node fields, "
        "handle missing 'id'"
    )
```

---

*Last updated: 2026-05-24. See `docs/analysis-and-enhancements.md` for the source
decisions that produced this plan.*
