# Learning Path — Analysis & Enhancement Findings

This document captures the findings from a multi-perspective adversarial analysis of
the 9-phase Akanga learning path. It is a pre-planning artifact: all items here are
**documented and agreed upon**, but nothing has been implemented yet. An implementation
plan will be created separately after this document is reviewed.

The **Decisions** section at the bottom records the final agreed resolution for every
finding. The implementation plan will be derived directly from that table.

---

## Critical Gaps (agreed, must fix before the path is usable)

### Gap 1 — No Runnable Test Files

**What exists:** Each phase document contains test specs written as pseudocode — they
describe what should be tested and show approximate code shape, but they are not
valid pytest files and cannot be executed.

**Impact:** A learner has no way to verify their implementation is correct. "The
deliverable" in each phase is currently a description of success, not a verification
mechanism. Everything else in the plan depends on tests existing.

**What is needed:**
- A `tests/` directory in the repo
- One test file per phase (e.g. `tests/phase_02/test_db.py`)
- A shared `tests/conftest.py` with common fixtures (`tmp_path`, `db`, `vault`,
  `client`, etc.)
- Tests must be executable: `pytest tests/phase_02/ -v` should run and produce
  pass/fail output

### Gap 2 — No Reference Implementation

**What exists:** The phase documents specify what to build (data structures,
interfaces, function signatures). There is no working code.

**Impact:** A learner who gets stuck mid-phase has nothing to compare against. This
is the single biggest dropout risk in any project-based learning path. A learner who
cannot unblock will abandon.

**What is needed:**
- A `solutions/` directory with a complete, tested, cumulative implementation for
  each phase
- `solutions/phase_NN/src/akanga_core/...` — runnable against the test suite
- Each solution builds on the previous (phase 3 solution includes all of phase 0–2)

### Gap 3 — Missing Guided Build (the First 20%)

**What exists:** Each phase moves from concept explanation directly to deliverable
spec. There is no middle step.

**Impact:** A learner who understands the concept but has never written this kind of
code has no entry point. "Build `GraphDatabase` with WAL mode" is unambiguous to a
senior engineer and completely opaque to an intermediate one.

**What is needed:**
- A "Guided Build" section in each phase doc — placed between Concepts and Deliverable
- Shows the file skeleton (empty class with method stubs)
- Shows the first passing test and exactly what to run to see it pass
- Leaves the rest for the learner to complete independently

---

## Pedagogical Enhancements

### Worked Micro-Examples

Each concept should have a standalone runnable script (~30 lines) that demonstrates
exactly one idea in isolation. Example: `examples/phase_02_wal_demo.py` creates an
in-memory SQLite DB, enables WAL, and shows two threads reading simultaneously.

These are not mandatory — experienced learners skip them. But they are essential for
learners who need to see something work before they can build on it.

### Reflection Prompts Per Phase

PBL requires a reflection step for learning transfer. Each phase should end with 2–3
questions the learner answers for themselves before moving on:

- "What surprised you about this implementation?"
- "What would break if you removed the threading.Lock?"
- "How would this design change if the vault had 100,000 nodes?"

### Common Mistakes Guide

A short list per phase of what beginners invariably get wrong. Examples:
- Phase 0: forgetting `PYTHONPATH=src` when running pytest
- Phase 2: string-formatting SQL instead of using parameterized queries
- Phase 4: calling `publish()` from a watchdog thread without checking if an event
  loop is running

### Prerequisite Checklist

The path assumes comfort with: Python dataclasses, type annotations, SQLite basics,
async/await, and terminal navigation. Learners who lack these will stall in Phase 0.
A one-page prerequisite checklist should be the first document in the repo.

### Time Estimates

No phase has a time estimate. Without this, the path cannot be structured as a
workshop and learners cannot plan their study time.

Rough estimates (intermediate Python developer):

| Phase | Topic | Estimated Hours |
|---|---|---|
| 0 | File System + Parser | 2h |
| 1 | Data Modeling | 2h |
| 2 | Storage & Indexing | 3h |
| 3 | Graph Algorithms | 2h |
| 4 | Concurrency & Events | 3h |
| 5 | Terminal UI (Part 1 — layout, navigation) | 3h |
| 5 | Terminal UI (Part 2 — graph renderer) | 3h |
| 6 | REST API | 3h |
| 7 | Version Control | 2h |
| 8 | AI Integration | 3h |
| **Total** | | **~26h** |

---

## Software Architecture Enhancements

### Observability (missing from all phases)

No phase covers structured logging, how to debug a crashed vault, or how to trace a
slow FTS query. Learners building production tools need this. Recommend a short
section in Phase 4 (where the EventBus is introduced) covering Python `logging`
and how to add a `--verbose` flag to the CLI.

### Performance Characterization (missing)

No phase asks "what breaks at 10,000 nodes?" Both FTS5 and BFS ego-graph have real
scaling limits. Teaching learners to benchmark their own code (via `pytest-benchmark`
or simple `time` measurements) is a missing architectural skill. Recommend adding a
"scaling notes" section to Phase 2 (indexer) and Phase 3 (graph algorithms).

### Deployment (missing)

The learning path ends with a working MCP server but never covers how to run Akanga
unattended: systemd unit file, launchd plist (macOS), or Docker. Without this, the
Phase 6 REST API and Phase 8 MCP server are development-only artifacts.

---

## Knowledge Graph Design Enhancements

### Ontology Evolution Strategy (missing from Phase 1)

Phase 1 defines the 71 relation types but no phase addresses how to extend the
vocabulary safely. If a learner adds a new relation type in month 3, do existing
edges break? What is the migration path? This needs a short section in Phase 1.

### Bidirectional Inference (gap between Phase 1 and Phase 3)

Phase 1 introduces `inverse_id` on relation types (e.g. `uses` ↔ `is_used_by`).
Phase 3's BFS traverses outgoing edges only. This means `A contradicts B` is not
discoverable from B's side without an explicit reverse edge. The learner should
understand this tradeoff explicitly — it is a design decision, not an oversight.

### Graph Validation (intentionally absent, should be documented)

Nothing prevents logically contradictory edges (`A supports B` AND `A contradicts B`
simultaneously). For a personal knowledge graph this is acceptable — contradictions
can represent unresolved intellectual tension and are often intentional. This design
decision should be stated in Phase 1 rather than discovered by surprise.

---

## Security Enhancements

### SQL Injection Prevention (missing explicit callout in Phase 2)

Every `db.py` query must use parameterized SQLite queries (`?` placeholders), never
string formatting. This is the most important security rule in any database layer.
Phase 2 should include a "never do this" example alongside the correct pattern.
A learner who internalizes this in Phase 2 will use it instinctively everywhere.

### CORS Configuration (missing from Phase 6)

Phase 6's REST API correctly binds to `127.0.0.1` by default. But a learner who
changes to `0.0.0.0` without understanding CORS has opened their vault to any browser
tab on the same network. The Phase 6 security section should cover FastAPI's
`CORSMiddleware` and when it is needed.

### YAML Safe Loader Verification (missing from Phase 0)

`python-frontmatter` uses PyYAML's safe loader by default, which blocks
`!!python/object:` injection. This should be verified and documented in Phase 0
rather than assumed — a learner who swaps the loader for convenience could introduce
a critical vulnerability.

### Git Remote Trust (should be explicit in Phase 7)

The `auto_push: false` default in Phase 7 is correct. But a learner who enables
auto-push against a shared or public remote is automatically publishing their personal
knowledge graph. This risk should be flagged explicitly in Phase 7's security notes.

---

## Workshop / Facilitator Enhancements

### Session Debrief Questions

Each session (phase) should end with structured debrief questions for group
discussion. These are the reflection mechanism that makes PBL transfer to long-term
retention rather than just short-term task completion.

### Checkpoint Exercises Within Phases

Each phase currently has one large deliverable at the end. Longer phases (5, 6) need
2–3 intermediate checkpoints — short (15-minute) exercises that verify a sub-concept
before the learner builds the next layer on top of it.

### Facilitator Guide

A separate document for workshop facilitators covering: session timing, common
sticking points, how to pair learners, how to handle learners at different speeds,
and how to run the reference implementation check at session end.

---

## Business Analysis Enhancements

### User Stories (missing)

The phases are implementation-driven. A short companion document with user stories
("as a developer, I want to capture insights from code reviews so that I can build
on them in future projects") would ground technical decisions in user value and help
contributors prioritize features.

### Version Roadmap (informal only)

MVP, V1, V2, V4+ are referenced throughout the phase docs and future-ideas.md but
never formally defined. A one-page version roadmap clarifying what ships in each
version would prevent scope creep and help contributors prioritize.

### Demo as Sales Artifact

`demo_tui.py` is the most important artifact for convincing someone to try Akanga.
It must work perfectly in any common terminal environment including tmux. (The tmux
Sixel corruption issue discovered during this session is a blocking bug for this
use case.)

---

## Summary Table

| # | Finding | Category | Priority |
|---|---|---|---|
| G1 | No runnable test files | Critical Gap | P0 |
| G2 | No reference implementation | Critical Gap | P0 |
| G3 | Missing Guided Build (first 20%) | Critical Gap | P0 |
| P1 | Micro-examples missing | Pedagogical | P1 |
| P2 | No reflection prompts | Pedagogical | P1 |
| P3 | No common mistakes guide | Pedagogical | P1 |
| P4 | No prerequisite checklist | Pedagogical | P1 |
| P5 | No time estimates | Pedagogical | P1 |
| A1 | No observability coverage | Architecture | P2 |
| A2 | No performance characterization | Architecture | P2 |
| A3 | No deployment coverage | Architecture | P2 |
| K1 | Ontology evolution not addressed | Knowledge Graph | P2 |
| K2 | Bidirectional inference tradeoff undocumented | Knowledge Graph | P2 |
| K3 | Graph validation design choice undocumented | Knowledge Graph | P2 |
| S1 | SQL injection prevention not explicit | Security | P1 |
| S2 | CORS configuration missing from Phase 6 | Security | P1 |
| S3 | YAML safe loader not verified | Security | P2 |
| S4 | Git remote trust risk not flagged | Security | P2 |
| W1 | No session debrief questions | Workshop | P2 |
| W2 | No checkpoint exercises within phases | Workshop | P2 |
| W3 | No facilitator guide | Workshop | P3 |
| B1 | No user stories | Business | P3 |
| B2 | Version roadmap informal only | Business | P2 |
| B3 | Demo not robust in tmux | Business | P0 (fixed) |

---

## Decisions

Complete agreed resolution for every finding. This table is the direct input to the
implementation plan.

| # | Finding | Decision | Artifact |
|---|---|---|---|
| G1 | No runnable test files | Create `tests/` directory with one file per phase and shared `conftest.py`. Tests translated from pseudocode in phase docs. | `tests/phase_NN/test_*.py` + `tests/conftest.py` |
| G2 | No reference implementation | Create `solutions/` directory with cumulative working implementation at each phase checkpoint. Each solution is runnable and passes its test suite. | `solutions/phase_NN/src/akanga_core/...` |
| G3 | Missing Guided Build | Skeleton code files with full class/method stubs, rich docstrings explaining what each method must do, type annotations, and inline hints. Learner fills in implementations. | `skeletons/phase_NN/src/akanga_core/...` |
| P1 | Micro-examples missing | New `examples/` directory. One standalone runnable script per phase (~30 lines), demonstrating exactly one concept in isolation. | `examples/phase_NN_*.py` |
| P2 | No reflection prompts | Add "Reflect" section to the end of each phase doc. 2–3 questions. Combined with W1 (same section, two purposes). | Addition to each `docs/learning/phase-NN-*.md` |
| P3 | No common mistakes guide | Add "Common Pitfalls" section to each phase doc. | Addition to each `docs/learning/phase-NN-*.md` |
| P4 | Prerequisite checklist too gatekeeping | New `docs/foundations/` directory with ~9 standalone explainers. Phase docs link to them with estimated read time. Learners choose what to read. Never blocking. | `docs/foundations/*.md` |
| P5 | No time estimates | Add estimated time one-liner to the top of each phase doc. | Addition to each `docs/learning/phase-NN-*.md` |
| S1 | SQL injection not explicit | Add "Security" callout section to `phase-02-storage-and-indexing.md` with before/after parameterized query example. | Addition to `docs/learning/phase-02-*.md` |
| S2 | CORS missing from Phase 6 | Add "Security" section to `phase-06-rest-api.md` covering `CORSMiddleware` and binding defaults. | Addition to `docs/learning/phase-06-*.md` |
| A1 | Observability coverage | Two artifacts: (1) short "Logging & Debugging" section in Phase 4 for Akanga-specific wiring; (2) comprehensive standalone `docs/observability-module.md` covering structured logging, timing/tracing decorators, EventBus introspection, SQLite slow-query analysis, `--verbose` CLI flag — designed as reusable knowledge applicable beyond Akanga. | Addition to `phase-04` + `docs/observability-module.md` |
| A2 | No performance characterisation | Add "Scaling Notes" section to Phase 2 (indexer limits) and Phase 3 (BFS limits at large graph sizes). | Additions to `phase-02` and `phase-03` |
| A3 | No deployment coverage | New `docs/deployment.md` covering: macOS launchd plist (auto-start on login), Linux systemd user service, `make serve` target. **No Docker** — local-first personal tool, containers add no value here. | `docs/deployment.md` |
| K1 | Ontology evolution not addressed | Add short "Extending the Vocabulary" section to Phase 1 covering safe addition of new relation types and migration of existing edges. | Addition to `phase-01` |
| K2 | Bidirectional inference tradeoff | Add short "Traversal Tradeoffs" section to Phase 3 documenting the outgoing-only BFS decision and when to add explicit reverse edges. | Addition to `phase-03` |
| K3 | Graph validation undocumented | Add one paragraph to Phase 1's data model section stating the intentional "no contradiction enforcement" design decision. Graph visualisation enhancements (node sizing by connection count or recency, gravity/force weighting by relation strength) captured in `future-ideas.md` as V3/V4. | Addition to `phase-01` + `future-ideas.md` |
| S3 | YAML safe loader not verified | Add security callout to Phase 0 verifying `python-frontmatter` uses PyYAML safe loader. | Addition to `phase-00` |
| S4 | Git remote trust risk | Add security callout to Phase 7 flagging auto-push risk against public/shared remotes. | Addition to `phase-07` |
| W1 | No session debrief questions | Merged with P2 — "Reflect" section at end of each phase doc serves both purposes. | Addition to each `docs/learning/phase-NN-*.md` |
| W2 | No checkpoint exercises | Add intermediate checkpoint exercises to the two longest phases only: Phase 5 (TUI) and Phase 6 (REST API). | Additions to `phase-05` and `phase-06` |
| W3 | No facilitator guide | New `docs/facilitator-guide.md` covering session timing, pairing strategies, common sticking points per phase, how to run reference implementation checks. | `docs/facilitator-guide.md` |
| B1 | No user stories | New `docs/user-stories.md` covering the **full product vision** — all stories tagged `[MVP]`, `[V1]`, `[V2]`, or `[V4+]`. No artificial cap on count; covers everything discussed across all sessions. | `docs/user-stories.md` |
| B2 | Version roadmap informal | New `docs/roadmap.md` formally defining MVP, V1, V2, V4+ scope boundaries. | `docs/roadmap.md` |
| B3 | Demo broken in tmux | Fixed: `demo_tui.py` now detects `$TMUX` env var and falls back to Rich renderer. Sixel escape codes no longer corrupt adjacent panes. | Fixed in `noteapp/demo_tui.py` |

---

## New Repo Structure (post-implementation)

```
akanga_mirin/
  docs/
    learning/
      phase-00-file-system-as-database.md   ← + Security, Pitfalls, Reflect, Time, Guided skeleton ref
      phase-01-data-modeling.md             ← + K1 (ontology), K3 (validation), Pitfalls, Reflect
      phase-02-storage-and-indexing.md      ← + S1 (SQL injection), A2 (scaling), Pitfalls, Reflect
      phase-03-graph-algorithms.md          ← + K2 (inference tradeoff), A2 (scaling), Pitfalls, Reflect
      phase-04-concurrency-and-events.md    ← + A1 (logging section), Pitfalls, Reflect
      phase-05-terminal-ui.md               ← + W2 (checkpoints), Pitfalls, Reflect
      phase-06-rest-api.md                  ← + S2 (CORS), W2 (checkpoints), Pitfalls, Reflect
      phase-07-version-control.md           ← + S4 (remote trust), Pitfalls, Reflect
      phase-08-ai-integration.md            ← + Pitfalls, Reflect
    foundations/
      python-type-annotations.md
      python-dataclasses.md
      yaml-and-markdown-frontmatter.md
      git-basics.md
      sqlite-basics.md
      python-threading.md
      asyncio-primer.md
      terminal-and-tmux-basics.md
      http-fundamentals.md
      json-rpc-basics.md
    observability-module.md
    deployment.md
    facilitator-guide.md
    user-stories.md
    roadmap.md
    future-ideas.md                         ← + K3 graph viz, force/gravity
    analysis-and-enhancements.md            ← this file
  examples/
    phase_00_parser_demo.py
    phase_01_schema_demo.py
    phase_02_wal_demo.py
    phase_03_bfs_demo.py
    phase_04_eventbus_demo.py
    phase_05_textual_demo.py
    phase_06_fastapi_demo.py
    phase_07_queue_demo.py
    phase_08_rag_demo.py
  skeletons/
    phase_00/src/akanga_core/parser.py      ← stubs + docstrings
    phase_01/src/akanga_core/schema.py
    phase_02/src/akanga_core/db.py
    ...
  solutions/
    phase_00/src/akanga_core/parser.py      ← complete reference implementation
    phase_01/src/akanga_core/...
    ...
  tests/
    conftest.py                             ← shared fixtures, AKANGA_SRC env wiring
    phase_00/test_parser.py
    phase_01/test_schema.py
    phase_02/test_db.py
    phase_03/test_graph.py
    phase_04/test_eventbus.py
    phase_05/test_tui.py
    phase_06/test_api.py
    phase_07/test_commit_queue.py
    phase_08/test_rag.py
  scripts/
    study.sh
```
