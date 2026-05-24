# Implementation Plan — Documentation Architecture & Test Quality Strategy

*Produced from: adversarial analysis findings, all 9 phase docs, agreed decisions table.*
*Scope: documentation architecture, test strategy, cross-reference map, consistency
audit, and numbered task list with effort estimates.*

---

## 1. Documentation Architecture

### 1.1 The Navigation Problem

With 9 phase docs, 10 foundation docs, and 7 standalone docs (plus `analysis-and-
enhancements.md` and `future-ideas.md`), the total doc count exceeds 28 files. A flat
`docs/` directory with no index is navigable by the author and no one else. Three
learner failure modes:

1. **Disoriented arrival** — clones the repo, sees `docs/learning/phase-03-...`, opens
   it, is immediately lost because Phase 3 assumes Phases 0–2.
2. **Foundation blindness** — builds Phase 2 without reading `docs/foundations/sqlite-
   basics.md` because they did not know it existed.
3. **Forward ref dead ends** — Phase 3 mentions "see bidirectional inference tradeoffs"
   without saying where that section lives; the learner searches, does not find it.

The architecture below eliminates all three.

---

### 1.2 Root README.md

The root `README.md` is the single entry point. It must answer five questions in
under 90 seconds of reading: what is this, who is it for, what does it produce,
where do I start, and what do I need first.

**Sections, in order:**

```
1. What Is Akanga Mirin          (2 sentences: personal knowledge graph, learning repo)
2. What You Build                (one-sentence per phase, inline — gives scope at a glance)
3. Quick Start                   (clone → prereq check → Phase 0)
4. Prerequisites                 (link to docs/foundations/ index, estimated read time each)
5. Learning Path                 (phase table: number, topic, estimated hours, test file)
6. Reference Docs                (links to standalone docs in docs/)
7. Repository Layout             (tree matching post-implementation structure)
8. Running the Tests             (one block: `PYTHONPATH=src pytest tests/ -v`)
```

The "What You Build" section is the repo's elevator pitch for a learner who is still
deciding whether to commit. It must list every phase output in one line each. Do not
bury this after three paragraphs of philosophy.

The "Learning Path" table is the navigation anchor for returning learners. Format:

| Phase | Topic | Hours | Test File |
|---|---|---|---|
| 0 | File System as Database | 2h | `tests/phase_00/test_parser.py` |
| 1 | Data Modeling | 2h | `tests/phase_01/test_schema.py` |
| 2 | Storage and Indexing | 3h | `tests/phase_02/test_db.py` |
| 3 | Graph Algorithms | 2h | `tests/phase_03/test_graph.py` |
| 4 | Concurrency and Events | 3h | `tests/phase_04/test_eventbus.py` |
| 5 | Terminal UI | 6h | `tests/phase_05/test_tui.py` |
| 6 | REST API | 3h | `tests/phase_06/test_api.py` |
| 7 | Version Control | 2h | `tests/phase_07/test_commit_queue.py` |
| 8 | AI Integration | 3h | `tests/phase_08/test_rag.py` |

---

### 1.3 docs/README.md (Docs Tree Map)

Every file in `docs/` described in one line. This is the index a learner uses when
they know roughly what they are looking for but not the exact filename.

```
docs/
  README.md                      — this file: one-line description of every doc

  learning/
    phase-00-file-system-as-database.md   — parser, atomic write, content hash, UUID
    phase-01-data-modeling.md             — typed edges, dual-key pattern, write-back
    phase-02-storage-and-indexing.md      — SQLite, WAL, FTS5, adjacency list, indexer
    phase-03-graph-algorithms.md          — BFS, cycle detection, ego-graph, ASCII render
    phase-04-concurrency-and-events.md    — watchdog, debouncing, EventBus, sync drain
    phase-05-terminal-ui.md               — Textual, reactive state, graph renderer
    phase-06-rest-api.md                  — FastAPI, Pydantic, WebSocket, OpenAPI
    phase-07-version-control.md           — GitPython, change queue, squash, commit msg
    phase-08-ai-integration.md            — MCP, Graph RAG, triple serialization, FastMCP

  foundations/
    python-type-annotations.md    — type hints, generic types, Optional, Union, Literal
    python-dataclasses.md         — @dataclass, frozen, __eq__, field defaults
    yaml-and-markdown-frontmatter.md — YAML syntax, python-frontmatter library, safe loader
    git-basics.md                 — init, add, commit, log, diff, restore
    sqlite-basics.md              — tables, queries, indexes, ACID, WAL mode primer
    python-threading.md           — threads, Lock, daemon threads, GIL, race conditions
    asyncio-primer.md             — event loop, await, tasks, run_coroutine_threadsafe
    terminal-and-tmux-basics.md   — terminal emulators, Kitty protocol, tmux panes
    http-fundamentals.md          — HTTP methods, status codes, headers, REST conventions
    json-rpc-basics.md            — JSON-RPC 2.0, request/response format, MCP mapping

  observability-module.md         — structured logging, timing decorators, slow query tracing
  deployment.md                   — macOS launchd plist, Linux systemd user service, make target
  facilitator-guide.md            — session timing, pairing, sticking points per phase
  user-stories.md                 — full product vision tagged [MVP] [V1] [V2] [V4+]
  roadmap.md                      — formal MVP/V1/V2/V4+ scope boundaries
  future-ideas.md                 — parked ideas: active nodes, diagrams, vector search
  analysis-and-enhancements.md    — pre-planning adversarial analysis with decisions table
```

---

### 1.4 Navigation Conventions: Cross-Referencing Foundation Docs

**Rule 1 — Reference section at the bottom of each phase doc.**

Each phase doc ends with a "Before You Start" or "Reference" block listing every
foundation doc that is directly relevant, with estimated read times. This is not a
prerequisite gate — it is an opt-in resource table. Format:

```
## Reference

If you need background on any concept in this phase:

- [SQLite Basics](../foundations/sqlite-basics.md) — 15 min read
- [Python Threading](../foundations/python-threading.md) — 20 min read
- [Python Dataclasses](../foundations/python-dataclasses.md) — 10 min read
```

This placement is deliberate: the reference block comes after the deliverable, not
before. Placing it at the top implies the learner must read all of them first, which
is both false and discouraging. The learner reads the phase, gets stuck, looks down.

**Rule 2 — Inline links on first mention only.**

When a phase doc uses a concept that has a foundation doc, the first mention in
Concepts gets an inline link. Subsequent mentions do not. This prevents repeated
visual noise while still giving the learner a path to the explainer at the exact
moment they encounter the concept. Example:

> ### WAL Mode (Write-Ahead Logging)
> SQLite's concurrency mode. [Read the SQLite Basics explainer →](../foundations/sqlite-basics.md)

**Rule 3 — No forward references to phase docs from within phase docs.**

Phase docs must never say "see Phase 6 for how this is used." Forward references
create frustration because the learner cannot yet read Phase 6. Instead, write the
meaning in place. A later phase can say "you built X in Phase N — here is how it
extends." Only backward references are permitted inline.

**Rule 4 — The "Introduced / Used / Deepened" column in the cross-reference map
(Section 3) is the authoritative record.** When adding cross-references to a phase
doc, use this map to verify you are not accidentally forward-referencing a concept
before it has been introduced.

---

### 1.5 Consistent Front-Matter / Header Template

All docs in the repo use the same header block immediately after the H1 title. The
block is YAML inside a comment-fenced block so it does not render as prose — it is
metadata for tooling and navigators, not content for the learner.

**Phase doc header template:**

```markdown
# Phase N — [Topic Name]

> **Estimated time:** Xh (intermediate Python developer)
> **Phase test:** `tests/phase_NN/test_*.py`
> **Previous phase:** [Phase N-1 — Topic](phase-NN-1-topic.md) | **Next:** [Phase N+1](phase-NN+1-topic.md)
> **Foundations used:** [SQLite Basics](../foundations/sqlite-basics.md), [Python Threading](../foundations/python-threading.md)

[Core concept paragraph...]
```

**Foundation doc header template:**

```markdown
# [Concept Name]

> **Read time:** ~Xmin
> **Used in:** [Phase N](../learning/phase-NN-topic.md), [Phase M](../learning/phase-MM-topic.md)
> **Level:** Beginner | Intermediate

[Intro paragraph...]
```

**Standalone doc header template (facilitator-guide, roadmap, etc.):**

```markdown
# [Document Title]

> **Audience:** [Facilitators | Contributors | Learners | All]
> **Last updated:** YYYY-MM-DD
> **Related:** [link to related docs]

[Intro paragraph...]
```

The `Estimated time`, `Phase test`, `Previous / Next`, and `Foundations used` fields
on phase docs serve double duty: they answer the returning-learner orientation
question ("where am I?") and they provide machine-readable metadata for any future
tooling that generates a study dashboard.

---

### 1.6 Versioning Strategy

**Decision: docs version with the code at the phase level, not the file level.**

Akanga has four named versions (MVP, V1, V2, V4+) defined in `docs/roadmap.md`. The
phase docs map cleanly to versions: Phases 0–3 produce MVP, Phases 4–6 produce V1,
Phase 7–8 produce V2. This alignment means a learner who wants to build only MVP
stops after Phase 3.

Each phase doc carries a version badge in its header:

```markdown
> **Ships in:** [MVP](../roadmap.md#mvp) | Phases 0–3
```

**What does not get versioned:**
- Foundation docs are version-agnostic — `sqlite-basics.md` describes SQLite, not
  "SQLite as used in Akanga MVP." They are stable references.
- `analysis-and-enhancements.md` is a planning artifact, not a living doc. It is not
  versioned — it describes a snapshot of decisions made before implementation.
- `future-ideas.md` is explicitly post-V2 and does not track versions.

**How to handle changes:** When a phase's architecture changes between versions (e.g.,
the Phase 5 graph renderer improves from half-block to Kitty in V1), add a `## V1
Changes` section at the bottom of the phase doc rather than editing in place. This
preserves the MVP-era design decisions, which are themselves educational. Never
silently overwrite earlier design choices.

**What the docs do NOT do:** There is no version-specific directory (`docs/v1/`,
`docs/v2/`). The repo is a learning path for building one system progressively; the
learner builds V1 on top of V0, not in a parallel branch. Doc branching would
fragment the narrative unnecessarily.

---

## 2. Test Strategy and Quality Design

### 2.1 Philosophy: Tests as Proof, Not Gatekeeping

A test in a learning repo serves two audiences simultaneously: the verifier (does this
implementation satisfy the contract?) and the teacher (why does this contract exist?).
Most test suites optimise only for the verifier. This repo must optimise for both.

The distinguishing criterion: **a good educational test fails with a message that
tells the learner what design principle they violated, not just what value was wrong.**

Compare:

```python
# Bad — tells the learner what broke, not why it matters
def test_roundtrip():
    assert parsed.title == "Test"

# Good — explains what design invariant was tested
def test_roundtrip():
    """
    Parser roundtrip must be idempotent: parse → write → parse returns equal nodes.
    If this fails, write() is changing data that should be preserved unchanged.
    This is the core contract of Phase 0: the file is the source of truth.
    """
    node = create(title="Test", type="note", vault=tmp_path)
    re_parsed = parse(write_and_read_back(node))
    assert re_parsed == node, (
        f"Roundtrip failed: parse → write → parse is not idempotent.\n"
        f"  Original: {node!r}\n"
        f"  Re-parsed: {re_parsed!r}\n"
        f"Hint: check that write() preserves field order and does not add whitespace."
    )
```

The failure message in the "Good" example tells the learner the principle (idempotence),
the location of the bug (write()), and what to look for (field order, whitespace). This
is achievable with a one-line f-string assert message on every assertion that would
otherwise produce a generic "AssertionError: False is not True."

---

### 2.2 Test Categories by Phase

**Phase 0 — Unit tests (pure functions)**

Target module: `parser.py`. All functions are deterministic and stateless given a
`tmp_path`. No DB, no threads, no network. Pure input-output contracts.

Why unit: the Phase 0 parser has no external dependencies. Testing it in isolation is
both correct and teaches the learner that pure functions are easy to test — the key
message of "design for testability."

Primary tests: roundtrip idempotence, UUID stability, atomic write (no temp files),
content hash determinism, vault config stamping.

**Phase 1 — Unit tests with one integration test**

Target modules: `parser.py` extensions, `sync_queue.py`. The extraction functions
(`extract_inline_edges`, `merge_edges`) are pure and should be tested as units. The
`write_back` function touches the file system and therefore crosses into integration.

The key test is `test_writeback_is_idempotent`: it exercises the full round-trip
through regex extraction, merge, and atomic write. This is the most complex logic of
the phase and the one most likely to produce subtle bugs (off-by-one edge counting,
duplicate detection across case variants). It belongs here, not deferred to Phase 2.

One integration test: `test_write_back_roundtrip` creates a file, appends inline edges
to the prose, calls `write_back`, and verifies the frontmatter edge block. This crosses
file system and parser in one test, which is the right scope — write_back is inherently
a file-touching function.

**Phase 2 — Integration tests (parser + indexer + DB)**

Target modules: `db.py`, `indexer.py`. GraphDatabase cannot be meaningfully tested
without a real SQLite file (in-memory or temp). Two-pass indexing cannot be tested
without real files to index. Both require file system + DB together.

This is the first phase where fixture design matters significantly. The `tmp_db`
fixture (a real `.db` file in `tmp_path`) and a pre-populated vault fixture (3–5 nodes
with edges between them) should be introduced here in `tests/phase_02/conftest.py` and
then promoted to `tests/conftest.py` for reuse in Phases 3–8.

The sentinel test is `test_db_is_expendable`: it indexes a vault, deletes the DB
file, re-indexes, and asserts the query result sets are identical. This is not merely
a correctness check — it is a specification test that proves the architectural promise
("the DB is a derived index, not the source of truth").

**Phase 3 — Unit tests for graph algorithms, integration for ego-graph**

Target module: `graph.py`. The BFS and squash functions are pure: given a graph
structure, produce a traversal result. But the ego-graph function requires DB access
for neighbor lookups, making the full ego-graph test integration-level.

Split explicitly: `test_bfs_pure.py` tests the algorithm with a mock or dict-based
graph (no DB). `test_ego_graph_integrated.py` tests `ego_graph()` against a real
populated DB. Keeping these separate teaches the learner that the BFS algorithm is
independently testable — and therefore the right thing to do is expose it as a
function that takes a callable neighbor-fetcher, not one that calls `db.get_edges`
directly inside the algorithm.

The `test_cycle_does_not_loop` test must have a hard timeout (use `pytest-timeout`
with `@pytest.mark.timeout(2)`). Without the timeout, a buggy traversal hangs the
test suite indefinitely — not just fails. The timeout turns an infinite loop into a
clear failure message.

**Phase 4 — Integration + timing tests (EventBus, file watcher)**

Target modules: `watcher.py`, `eventbus.py`, `sync_worker.py`. These tests involve
real OS file events and real thread interactions. They cannot be pure unit tests.

Timing sensitivity is the primary testing challenge. The debounce test
(`test_watcher_debounces_rapid_saves`) writes 10 files rapidly and asserts exactly
1 event fires after the debounce window. This test is inherently racy: if the CI
machine is under load, the debounce timer may fire between rapid writes. Mitigate:

1. Use a short debounce (50ms) in tests — the production value (500ms) is calibrated
   for real editors, not test speed.
2. Use `time.sleep(debounce_ms * 5 / 1000)` rather than a hardcoded sleep. When the
   debounce changes, the test adapts.
3. Mark timing-sensitive tests with `@pytest.mark.slow` and run them separately in CI
   with `--timeout=10` to prevent suite-level hangs.

The `test_subscriber_error_isolation` test is important for a different reason: it
tests a safety invariant (one bad subscriber does not crash others), not just
correctness. Write its docstring to explain _why_ subscriber isolation matters —
a real-world EventBus without it is a single point of failure for all listeners.

**Phase 5 — TUI pilot tests (Textual async)**

Target module: `tui.py`, `graph_screen.py`. Textual provides `app.run_test()` which
runs the TUI in a headless asyncio pilot for testing. All TUI tests are async and use
`await pilot.press()` / `await pilot.pause()`.

TUI tests are the most fragile in the suite because they depend on widget internal
state (`_nodes`, `visible_nodes`) that may change as the implementation evolves. Write
tests against public contracts (the list of visible items, the currently selected node
ID, whether a screen is the active screen) rather than internal widget fields.

The `test_live_update_adds_node` test involves a real file write, a real watchdog
event, and a real debounce — all inside an async pilot. This will be slow (~600ms per
test due to debounce). Accept this and mark the test `@pytest.mark.integration`. Do
not attempt to mock the file watcher in TUI tests — mocking it removes the very thing
being tested (the full pipeline from file change to TUI refresh).

**Phase 6 — API tests (FastAPI TestClient)**

Target module: `server.py`. All tests use FastAPI's `TestClient` with a
dependency-injected temp vault and temp DB. The lifespan startup should be testable
with a custom `app` fixture that overrides vault and DB paths.

The two most important tests per the phase doc are `test_node_file_is_written` (proves
the API does not bypass the file system) and `test_websocket_broadcast` (proves push
events work). These two tests together prevent the most common architectural regression
in API development: adding a "fast path" that writes directly to the DB without
touching files.

WebSocket tests with `TestClient` require the `with client.websocket_connect("/ws")
as ws:` pattern (synchronous test, synchronous WS client). The `timeout=2` on
`ws.receive_json()` must be explicit — without it a failing broadcast hangs the test.

**Phase 7 — Git integration tests (require real git repos in tmp_path)**

Target modules: `commit_queue.py`, `gitmgr.py`. These tests require real git repos
initialized in `tmp_path`. They do not require network access — `push()` is tested
for its failure behavior (no remote → returns False without raising), not for
successful network push.

Key fixture: `git_vault` — creates a `tmp_path` with a git repo initialized by
`GitManager.init_or_open()`, an initial commit (so `repo.head` exists), and 2–3
sample `.md` files already staged. Without the initial commit, many git operations
fail with "No commits yet" errors that are not the failure being tested.

The `test_startup_commits_leftover_queue` test simulates a crash: it creates a
persisted queue, instantiates a new `GitManager`, calls `load()`, and verifies a
commit was made. This test must explicitly verify the commit exists in `git log` —
not just that no exception was raised. Use `len(list(repo.iter_commits())) >= 1`.

**Phase 8 — MCP tool tests + RAG function tests**

Target modules: `rag.py`, `akanga_mcp/server.py`. Two test levels:

Level 1 (unit/integration): `test_context_for_query` tests the RAG function against
a real populated DB. This is an integration test (requires DB + indexed nodes) but
does not require a running MCP server.

Level 2 (MCP protocol): `test_mcp_search_tool` and `test_mcp_get_context_tool` call
tools through the MCP client. The test fixture should use FastMCP's test client rather
than spawning a real subprocess. FastMCP provides an in-process test mode analogous
to FastAPI's TestClient.

The `test_output_truncated_at_limit` test requires a vault large enough to trigger
truncation (>200 triples). The fixture should build this programmatically (a single
hub node with 250 edges to generated leaf nodes), not by committing 250 `.md` files
to the repo.

---

### 2.3 Test Quality Criteria

**Criterion 1: Every test has a docstring.**

No exceptions. The docstring answers: what is being tested, why it matters, and what
a failure indicates. One to three sentences. This is the single highest-leverage
quality practice for educational tests — it transforms "test_roundtrip FAILED" from a
cryptic error into "the parser's roundtrip idempotence guarantee was violated: write()
is not preserving all fields identically."

**Criterion 2: Assertion messages explain the failure in terms of design principles.**

Every `assert` that is not completely self-explanatory gets an f-string message. The
message should name the design principle being tested, not restate the assertion.

```python
# Wrong
assert result.status_code == 200, f"Expected 200, got {result.status_code}"

# Right
assert result.status_code == 200, (
    f"GET /api/v1/nodes/{node_id} returned {result.status_code}. "
    "A missing node returns 404, but an existing node must always return 200. "
    "Check that the node was actually indexed after creation."
)
```

**Criterion 3: Test names are sentences, not identifiers.**

Names like `test_watcher_fires_on_save` are acceptable. Names like `test_case_1` or
`test_foo` are not. The test name is the first thing a learner reads in the failure
output — it must be informative without opening the source file.

**Criterion 4: The most important test in each phase is explicitly marked.**

Each phase doc already identifies the "most important test" by name. In the test file,
this test gets a `# SENTINEL` comment directly above its docstring. This signals to
the learner: if you implement only one thing, make this pass first. It also gives
facilitators an easy check at session end.

**Criterion 5: No test exceeds 30 lines.**

If a test requires more than 30 lines of code, it is testing too many things at once
and should be split. The limit enforces the single-responsibility principle for tests.
Fixture setup that would push a test over 30 lines belongs in a fixture.

**Criterion 6: Tests avoid magic numbers and strings.**

All fixed values used in assertions should be named constants or come from fixture
objects. `assert len(results) == 7` tells the learner nothing. `assert len(results) ==
len(VAULT_FIXTURE_NODES)` tells the learner exactly what the expected count represents.

---

### 2.4 Test Count Per Phase

The right range is 6–10 tests per phase. The reasoning:

- Fewer than 6: insufficient coverage of the phase's core contracts. A learner can
  pass all tests with a broken implementation by getting lucky on edge cases.
- More than 10: overwhelming for a phase-end session check. A learner who sees 15
  failing tests has no idea where to start.
- The sweet spot is 7–8: covers the main happy path, 2–3 critical edge cases, and
  one "specification test" proving an architectural invariant.

Phase 7 (git integration) is the only phase that justifiably exceeds 10, because git
has more distinct failure modes that must each be proven non-fatal. Cap at 12.

Phase 5 (TUI) is the only phase that justifiably has fewer than 6, because TUI pilot
tests are slow and fragile — 5 well-chosen tests covering navigation, search, edit,
live update, and graph screen are sufficient.

---

### 2.5 conftest.py Design

**`tests/conftest.py` — shared across all phases**

```python
import pytest
from pathlib import Path
from akanga_core.parser import create, write
from akanga_core.db import GraphDatabase
from akanga_core.indexer import VaultIndexer

# ─── Vault Config ──────────────────────────────────────────────────────────────

VAULT_OWNER = "Test Learner"
DEFAULT_WORKSPACE_NAME = "Nhamandu"
DEFAULT_WORKSPACE_ID = "a3f7c2be-0000-0000-0000-000000000001"

@pytest.fixture
def vault_config(tmp_path) -> dict:
    """Minimal akanga.yaml written to tmp_path. All phases that need vault config use this."""
    config = {
        "owner": VAULT_OWNER,
        "default_workspace": {"name": DEFAULT_WORKSPACE_NAME, "id": DEFAULT_WORKSPACE_ID},
        "workspaces": [],
        "git": {"enabled": False}
    }
    import yaml
    (tmp_path / "akanga.yaml").write_text(yaml.dump(config))
    return config

@pytest.fixture
def vault(tmp_path, vault_config) -> Path:
    """Empty vault directory with akanga.yaml. Use this when tests create their own nodes."""
    return tmp_path

# ─── Populated Vault ───────────────────────────────────────────────────────────

VAULT_FIXTURE_NODES = [
    {"title": "Fast Thinking is Unreliable", "type": "note",   "tags": ["cognition"]},
    {"title": "Blink — Malcolm Gladwell",    "type": "note",   "tags": ["cognition", "intuition"]},
    {"title": "Thinking Fast and Slow",      "type": "note",   "tags": ["cognition", "psychology"]},
    {"title": "Python Docs",                 "type": "reference", "tags": ["python"]},
    {"title": "SQLite Documentation",        "type": "reference", "tags": ["sqlite", "database"]},
]

@pytest.fixture
def populated_vault(tmp_path, vault_config) -> Path:
    """
    Vault with 5 pre-created nodes and 2 edges between them.
    Node 0 contradicts Node 1; Node 0 supports Node 2.
    Used by Phases 2–8 to avoid rebuilding fixture setup in every test.
    """
    nodes = []
    for spec in VAULT_FIXTURE_NODES:
        node = create(title=spec["title"], type=spec["type"], vault=tmp_path)
        node.tags = spec["tags"]
        write(node, node.path)
        nodes.append(node)
    # Add edges (frontmatter) to node 0
    # ... (implementation detail: modify node 0's frontmatter after creation)
    return tmp_path

# ─── Database ─────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_db(tmp_path) -> Path:
    """Path to an empty temp DB file. GraphDatabase(tmp_db) opens it fresh."""
    return tmp_path / ".akanga.db"

@pytest.fixture
def indexed_db(populated_vault, tmp_db) -> GraphDatabase:
    """
    Fully indexed GraphDatabase built from populated_vault.
    This is the standard pre-warmed DB fixture for Phases 2–8.
    All 5 nodes from VAULT_FIXTURE_NODES are present; 2 edges are indexed.
    """
    db = GraphDatabase(tmp_db)
    VaultIndexer().index_vault(populated_vault, db)
    return db
```

**Design rationale for `populated_vault` fixture:**

The fixture creates 5 nodes in a fixed, known structure. Every test in Phases 2–8 that
needs a non-empty vault uses `populated_vault` or `indexed_db`. The fixture is defined
once in `tests/conftest.py`, not duplicated in each phase's conftest. This means when
the Node dataclass gains a new field in a later phase, the fixture is updated in one
place and all tests adapt automatically.

The 5-node count is deliberate: large enough to test search (multiple results), BFS
traversal (neighbors at depth 2), and graph rendering (non-trivial layout), but small
enough that fixture setup is fast (<100ms) and the test output is human-inspectable.

**Phase-specific fixtures in `tests/phase_NN/conftest.py`:**

Each phase `conftest.py` contains only fixtures that are specific to that phase and
would not make sense globally. Examples:

- `tests/phase_04/conftest.py`: `eventbus` fixture (creates a real EventBus with
  configured loop), `watcher` fixture (creates and auto-stops VaultWatcher).
- `tests/phase_05/conftest.py`: `app` fixture (creates AkangaTUI backed by
  `indexed_db` and `populated_vault`), `pilot` fixture (runs `app.run_test()`).
- `tests/phase_06/conftest.py`: `client` fixture (FastAPI TestClient with temp vault
  and DB injected), built from `populated_vault` and `indexed_db`.
- `tests/phase_07/conftest.py`: `git_vault` fixture (populated_vault + git init +
  initial commit so `repo.head` exists without error).
- `tests/phase_08/conftest.py`: `mcp_client` fixture (FastMCP in-process test client
  initialized against `indexed_db`).

**The `indexed_db` fixture chain** is the backbone: `vault_config → populated_vault
→ tmp_db → indexed_db`. All downstream tests depend on this chain, not on individual
pieces. A test that needs only the DB gets `indexed_db` and gets the vault for free.
A test that needs to modify vault files gets `populated_vault` directly and calls
`VaultIndexer().index_vault()` itself when it needs DB access after the modification.

---

## 3. Cross-Reference Map

Concepts are marked: **I** = Introduced (concept explained, first code), **U** = Used
(referenced or depended on without re-explaining), **D** = Deepened (extended, new
dimension added, or limitation surfaced).

| Concept | Ph0 | Ph1 | Ph2 | Ph3 | Ph4 | Ph5 | Ph6 | Ph7 | Ph8 |
|---|---|---|---|---|---|---|---|---|---|
| YAML Frontmatter | I | U | U | — | — | U | U | — | — |
| UUID / Stable Identity | I | U | U | — | — | — | U | — | — |
| Idempotence | I | D | — | — | U | — | — | — | — |
| Atomic Write | I | U | — | — | U | — | — | — | — |
| Content Hash (SHA-256) | I | — | U | — | — | — | — | — | — |
| Python Dataclass | I | D | U | D | — | — | U | D | — |
| Vault Configuration | I | D | U | — | U | — | U | U | — |
| Directed Graph | — | I | — | U | — | U | — | — | U |
| Labeled Property Graph | — | I | — | U | — | U | U | — | U |
| Typed Edges (dual-key) | — | I | U | U | U | U | U | — | U |
| Inline Edge Shorthand (`[[…]]`) | — | I | U | — | D | — | — | — | — |
| Write-Back | — | I | — | — | D | — | — | — | — |
| Source of Truth (files) | I | U | I (deepen) | — | — | — | U | U | — |
| Eventual Consistency | — | I | — | — | D | — | — | — | — |
| Background Sync Queue | — | I | U (schema) | — | D | U | U | — | — |
| Node Types as Schema Variants | — | I | U | — | — | U | U | — | — |
| Reference Integrity via UUID | — | I | U | — | — | — | U | — | — |
| SQLite | — | — | I | — | — | — | U | — | U |
| WAL Mode | — | — | I | — | U | — | U | — | U |
| Adjacency List | — | — | I | U | — | — | U | — | U |
| Derived Index | I (concept) | — | I (impl) | — | — | — | U | U | — |
| Two-Pass Indexing | — | — | I | — | U | — | — | — | — |
| FTS5 | — | — | I | — | — | — | U | — | U |
| Thread Safety | — | — | I | — | D | — | — | — | — |
| Graph Traversal | — | — | — | I | — | U | — | — | U |
| BFS | — | — | — | I | — | U | — | — | U |
| Cycle Detection | — | — | — | I | — | U | — | — | — |
| Ego-Graph | — | — | — | I | — | D | D | — | U |
| Directed Edge Traversal | — | — | — | I | — | U | — | — | U |
| Graph Density Ceiling | — | — | — | I | — | D | — | — | — |
| File Watching | — | — | — | — | I | — | — | — | — |
| Debouncing | — | — | — | — | I | — | — | U | — |
| Threads vs asyncio | — | — | — | — | I | — | U | U | — |
| Event Bus | — | — | — | — | I | D | — | U | — |
| `run_coroutine_threadsafe` | — | — | — | — | I | — | — | — | — |
| Sync Queue Drain | — | I (enqueue) | U (schema) | — | I (drain) | U | U | — | — |
| Reactive TUI | — | — | — | — | — | I | — | — | — |
| Widget Composition | — | — | — | — | — | I | — | — | — |
| Event-Driven UI | — | — | — | — | U | I | — | — | — |
| Keyboard-First / Mouse-Aware | — | — | — | — | — | I | — | — | — |
| Two-Layer Graph Renderer | — | — | — | U (ASCII) | — | I | — | — | — |
| Suspend / Resume | — | — | — | — | — | I | — | — | — |
| REST | — | — | — | — | — | — | I | — | — |
| FastAPI | — | — | — | — | — | — | I | — | U |
| Lifespan Context Manager | — | — | — | — | U | — | I | — | — |
| Pydantic Models | — | — | — | — | — | — | I | — | — |
| WebSocket (Push Events) | — | — | — | — | U | U | I | — | — |
| Path Traversal Protection | — | — | — | — | — | — | I | — | U |
| API Boundary vs Library Consumer | — | — | — | — | — | — | I | — | D |
| OpenAPI | — | — | — | — | — | — | I | — | — |
| Git as User Feature | — | — | — | — | — | — | — | I | — |
| GitPython | — | — | — | — | — | — | — | I | — |
| Change Queue | — | — | — | — | U (event) | — | — | I | — |
| Squash Algorithm | — | — | — | — | — | — | — | I | — |
| Queue Persistence | — | — | — | — | — | — | — | I | — |
| Commit Triggers | — | — | — | — | — | — | — | I | — |
| Commit Message Generation | — | — | — | — | — | — | — | I | — |
| Non-Fatal Git Errors | — | — | — | — | — | — | — | I | — |
| `.gitignore as Contract` | — | — | — | — | — | — | — | I | — |
| MCP | — | — | — | — | — | — | — | — | I |
| FastMCP | — | — | — | — | — | — | U | — | I |
| Graph RAG | — | — | — | — | — | — | — | — | I |
| Triple Serialization | — | — | — | — | — | — | — | — | I |
| MCP Tool Design | — | — | — | — | — | — | — | — | I |
| API Boundary for AI Clients | — | — | — | — | — | — | D | — | I |
| Output Size Limits | — | — | — | — | — | — | — | — | I |
| SQL Injection Prevention | — | — | I* | — | — | — | — | — | — |
| CORS Configuration | — | — | — | — | — | — | I* | — | — |
| YAML Safe Loader | I* | — | — | — | — | — | — | — | — |
| Git Remote Trust | — | — | — | — | — | — | — | I* | — |

*Security callout — added per agreed decisions, not originally present.

**How to use this map when adding cross-references to phase docs:**

1. Before adding a "see also" or inline link, check whether the target concept has
   been Introduced (I) in a previous phase. If not, it is a forward reference — do
   not add it inline; add it to the "coming up" section at the end of the phase doc.
2. When deepening (D) a concept, the phase doc should explicitly say "you first built
   X in Phase N — here is what changes." The "D" marker flags where to add these
   backward references.
3. The "U" entries are the places where a concept is used without re-introduction.
   These are the points where a learner who skipped a phase will be confused. Each "U"
   entry should have a one-line backward reference: "recall from Phase N that…"

---

## 4. Consistency Audit

### 4.1 Structure Consistency

**Finding:** All 9 phase docs follow a roughly consistent structure (concept intro →
Vault Nodes table → What You Build → Deliverable), but the structure is not identical
across docs and the variation is not meaningful.

**Specific deviations:**

| Doc | Deviation |
|---|---|
| Phase 0 | Has "Vault Nodes to Create" — calls it "Vault Nodes to Create" |
| Phase 2 | Has "The Complete DB Schema" section between Concepts and "Vault Nodes to Create" — a structural addition not present in other phases |
| Phase 3 | Does NOT have a "Vault Nodes to Create" table as a separate heading — vault nodes are listed under "Vault Nodes to Create" but without the introductory paragraph that Phases 0–2 have |
| Phase 5 | Has additional "Layout" and "Keybindings" sections between Vault Nodes and "What You Build" — no other phase has these mid-doc reference sections |
| Phase 6 | Has "Endpoints" and "Key Design Decisions" sections between Vault Nodes and "What You Build" |
| Phase 7 | Has no explicit "Vault Nodes to Create" introductory paragraph (minor) |
| Phase 8 | Has "Architecture" section (code tree) between "What You Build" and "Deliverable" — unique to this phase |

**Recommended fix:** Establish a canonical section order and apply it to all phases:

```
1. H1 Title + header block (time estimate, phase test, prev/next, foundations)
2. Core concept paragraph (2–4 sentences, already exists and is consistent)
3. ## Concepts (already exists)
4. ## Reference Materials (new: layout diagrams, schemas, endpoint tables, keybindings)
   — This consolidates the "floating" sections (DB Schema, Endpoints, Layout) into
     one clearly named section that all phases have, even if some have it empty.
5. ## Vault Nodes to Create (already exists)
6. ## Guided Build (new per G3 decision)
7. ## What You Build (already exists)
8. ## Common Pitfalls (new per P3 decision)
9. ## Deliverable (already exists)
10. ## Reflect (new per P2/W1 decision)
11. ## Reference (foundation doc links — new per this architecture plan)
```

---

### 4.2 Code Example Formatting

**Finding:** All code examples use fenced markdown code blocks with language tags.
This is consistent across all phases.

**Specific deviation:** Phase 3's BFS traversal shows partially complete code (the
`edges.append(EgoEdge(..., direction=EdgeDirection.OUTGOING))` line uses `...` as a
stub inside what looks like a complete function). This is inconsistent with Phase 6
and Phase 8, where the "What You Build" functions are shown complete. Learners
reading Phase 3 may not know whether the `...` is intentional (skeleton) or a doc
omission.

**Recommended fix:** Add a `# Partial — learner completes the missing fields` comment
above any stub line in code examples. Never use `...` as a silent stub — it reads as
a Python Ellipsis, which is valid syntax but not what is meant here.

---

### 4.3 Vault Node Table Consistency

**Finding:** All phases have "Vault Nodes to Create" tables with consistent column
names (`Node`, `Type`, `Key Edges`). This is the most consistently formatted element
across all 9 docs.

**Specific deviation:** Phase 6's vault node table has a `| FastMCP | reference | ...
| uses → FastAPI |` entry that references `FastMCP` as both a node in Phase 6 and
the primary subject of Phase 8. This creates an awkward situation: the Phase 6 learner
is creating a node about something they have not yet built.

**Recommended fix:** Move the `FastMCP` and `FastAPI` vault nodes from Phase 6 to the
phases where they are actually introduced. Check the cross-reference map: FastAPI is
introduced in Phase 6 (correct), FastMCP is introduced in Phase 8. The Phase 6 vault
node table should not include FastMCP. The `WebSocket → uses → FastAPI` edge is
accurate and should stay.

---

### 4.4 Terminology Inconsistencies

**Finding 1 — "note" vs "node":**

Phase 0 introduces the `Node` dataclass and the term "node" consistently. Phase 7's
commit message generation examples use `"note"` as a shorthand in examples:
`"update: 3 notes (Fast Thinking, Akanga, SQLite)"`. The commit message vocabulary
uses "notes" as a synonym for "nodes" — which is a reasonable user-facing term, but
inconsistent with the technical vocabulary established in Phases 0–6 where "node" is
always used.

**Recommended fix:** In Phase 7's commit message examples, replace all occurrences of
"notes" with "nodes" to maintain terminology consistency. The generated commit messages
are user-facing, but the doc is teaching the implementation — the implementation should
use the correct internal term.

**Finding 2 — "edge" vs "relation":**

Phase 1 introduces the `Edge` dataclass with a `relation` field. The `relation` field
holds the human-readable edge type name. In some places, "relation" and "edge" are
used interchangeably when they should not be. Specifically:

- Phase 2, Adjacency List section: "edges carry a type label — the relation" is
  correct usage.
- Phase 6, endpoint table: `GET /api/v1/nodes/{id}/edges` is correct (returns Edge
  objects). `POST /api/v1/edges` is correct (creates an Edge). This is consistent.
- Phase 8, Triple Serialization section: "Relations:" is the section header for what
  are technically `EgoEdge` objects. This is intentionally LLM-oriented language
  (triples use "relation" as the predicate term) and is not an inconsistency — it is
  context-appropriate vocabulary. No fix needed.

**Finding 3 — "active nodes" vs "active-service" vs "reference":**

The original `noteapp` (the production repo) has node types: `note`, `active`,
`active-service`, `diagram`, `virtual`. The learning repo's Phase 0 defines types as
`"note" | "reference"`. Phase 1 adds `reference` with `url`, `external_type`,
`description`. Phases 5 and 6 reference `reference` type nodes in examples.

The production system's `virtual` type (external resources with URL) maps to the
learning repo's `reference` type. The production `active` type is explicitly deferred
to `future-ideas.md`. This is intentional and correct — but the learning repo docs
should explicitly note "the production system also has `active`, `active-service`, and
`virtual` types; these are out of scope for the learning path and documented in
`future-ideas.md`." Without this note, a learner who reads the production CLAUDE.md
alongside the phase docs will be confused by the type mismatch.

**Recommended fix:** Add a one-paragraph note to Phase 0 or Phase 1 clarifying that
the learning path uses a simplified `reference` type where the production system uses
`virtual`, and that `active` and `active-service` types are future work.

**Finding 4 — "relation-id" vs "relation_id" casing:**

The YAML frontmatter spec (Phase 1) uses hyphenated keys: `relation-id`, `target-id`.
The `Edge` dataclass uses underscored fields: `relation_id`, `target_id`. Python
conventions require underscores in identifiers. This is intentional (YAML keys differ
from Python attribute names) but the docs do not state this explicitly.

**Recommended fix:** Add a "YAML vs Python naming" note to Phase 1's "The Edge
Format" section: "Note: YAML frontmatter uses hyphenated keys (`relation-id`) while
the Python dataclass uses underscores (`relation_id`). The parser maps between them on
read and write."

---

### 4.5 Factual Contradictions Between Phases

**Contradiction 1 — FTS5 scope:**

Phase 2 states: "FTS5 covers `title`, `tags`, and `description` (reference node short
description) only — never the prose body."

Phase 8 states: `db.search(query, limit=5)` is used as the seed search for RAG. The
RAG function description says "FTS5 seed search." These are consistent.

However, Phase 8's `context_for_query` implementation shows `desc = node.description
or node.body[:120].replace("\n", " ")` — this accesses `node.body`. The DB schema
(Phase 2) explicitly does NOT store body content: "The DB never stores prose content."
If `node.body` is populated from the DB, this contradicts Phase 2's architecture.

**Resolution:** The `node` object returned by `db.search()` should have `body = ""`
because the DB does not store body text. The RAG function should load the full node
from disk if it needs the body (`parse(node.path).body`), or accept that `desc` falls
back to `""` when `node.description` is also empty. The Phase 8 code example contains
a latent architectural contradiction that will surface as a test failure when
implemented. Fix the code example in Phase 8 to either (a) load body from disk
explicitly, or (b) use description only and add a comment explaining why body is not
available from the index.

**Contradiction 2 — GitManager in app.py:**

Phase 4's `app.py` startup sequence includes:

```
on file_changed:
  git_manager.stage_and_commit()     → debounced 5s (Phase 8)
```

But Phase 7 clarifies that commit triggers are: session-end, periodic, and manual —
not file-changed. Phase 4's note "(Phase 8)" is misleading — git integration is
introduced in Phase 7, not Phase 8. The parenthetical should read "(Phase 7)."

**Recommended fix:** Update Phase 4's `app.py` startup sequence comment to "(Phase 7)"
and add a note: "The commit-on-file-changed pattern is NOT used; commits are triggered
by the three mechanisms defined in Phase 7."

**Contradiction 3 — Ego-graph in Phase 6 endpoint table:**

Phase 6 lists `GET /api/v1/nodes/{id}/ego-graph` as an endpoint. Phase 3 defines the
`EgoGraph` data structure and `render_ascii()`. Phase 5 defines `render_graph_kitty()`
and `render_graph_canvas()`. The Phase 6 API endpoint returns "ego-graph data" but
does not specify what format: JSON? Rendered ASCII? The renderers are TUI-specific
(Pillow Image, Textual Canvas) and would not make sense over HTTP.

**Resolution:** Phase 6's ego-graph endpoint should return the raw `EgoGraph` data
structure serialized as JSON (nodes + edges as dicts), not a rendered representation.
The rendering always happens client-side. Clarify this in Phase 6's endpoint
documentation: "Returns the ego-graph as JSON (nodes and typed edges). Rendering is
the client's responsibility."

---

## 5. Numbered Task List

### Tier 1 — Navigation and Entry Point (must complete before repo is shared)

**T-01 — Create root README.md**
- Sections: What Is This, What You Build (one-liner per phase), Quick Start, Prerequisites, Learning Path table, Reference Docs, Repo Layout, Running Tests.
- Acceptance: a learner who has never seen the repo can open `README.md` and know exactly which file to open next within 90 seconds.
- Effort: 2h

**T-02 — Create docs/README.md (docs tree map)**
- One-line description per file in the docs/ tree (post-implementation structure).
- Acceptance: every file in docs/ appears exactly once with an accurate description.
- Effort: 1h

**T-03 — Apply phase doc header template to all 9 phase docs**
- Add the standard header block (time estimate, test link, prev/next, foundations list) to each phase doc.
- Acceptance: all 9 phase docs open with the consistent 4-line header block. Links to prev/next phase resolve correctly.
- Effort: 1.5h (10min per phase)

**T-04 — Apply foundation doc header template to all 10 foundation docs**
- Add header block (read time, used in phases, level) to each foundation doc.
- Acceptance: all 10 foundation docs have the header block. "Used in" links resolve to real phase docs.
- Effort: 1h (6min per doc)

**T-05 — Standardize phase doc section order**
- Apply the 11-section template to all 9 phase docs. Rename "floating" sections (DB Schema, Endpoints, Layout, Keybindings) to live under "Reference Materials" (section 4).
- Acceptance: all 9 phase docs follow the section order defined in §1.4. Diff is structural only — no content changes.
- Effort: 3h (20min per phase for restructuring)

---

### Tier 2 — Cross-Reference Integration (must complete before path is usable end-to-end)

**T-06 — Add "Reference" section to all 9 phase docs**
- Add the foundation doc link block at the bottom of each phase doc (after "Reflect", before any future appendix).
- Derive the list from the cross-reference map in §3 — only link foundations that are [I]ntroduced or [U]sed in that phase.
- Acceptance: every foundation doc that is [I] or [U] in a given phase has a working link from that phase doc's Reference section. No broken links.
- Effort: 2h (using the cross-reference map as input — mechanical task)

**T-07 — Add backward-reference "recall" notes to all [U] entries in phase docs**
- For each concept marked [U] in the cross-reference map, add a one-line "recall from Phase N that…" at its first mention in the current phase doc.
- Acceptance: every concept used in a phase but first introduced in an earlier phase has a backward reference. A learner who skips a phase is explicitly told where to find the introduction.
- Effort: 3h (approximately 40 [U] entries across 9 phases)

**T-08 — Add "coming up" forward notice for [I] entries in the next phase**
- Each phase doc ends with a one-sentence "In the next phase, you will build X" that prepares the learner for the next introduction. This is not a forward reference — it names the concept without explaining it.
- Acceptance: all 8 phase transitions (0→1, 1→2, …, 7→8) have a "coming up" sentence. The sentence does not introduce or define the next concept.
- Effort: 45min (5min per transition)

---

### Tier 3 — Test Infrastructure (enables test execution)

**T-09 — Create tests/conftest.py with shared fixtures**
- Implement all fixtures described in §2.5: `vault_config`, `vault`, `populated_vault` (5 nodes, 2 edges), `tmp_db`, `indexed_db`.
- Acceptance: `pytest tests/ --collect-only` shows all phase test files discovered. `pytest tests/ -k "test_nothing"` (no tests matched) exits with code 0 and no import errors.
- Effort: 3h

**T-10 — Create phase-specific conftest.py files for Phases 4–8**
- Phase 4: `eventbus`, `watcher` fixtures.
- Phase 5: `app`, `pilot` fixtures.
- Phase 6: `client` fixture (FastAPI TestClient).
- Phase 7: `git_vault` fixture.
- Phase 8: `mcp_client` fixture.
- Acceptance: each phase conftest imports cleanly. Fixtures are documented with docstrings. No fixture creates network connections.
- Effort: 4h (45min per phase)

**T-11 — Translate Phase 0 pseudocode tests to real pytest file**
- File: `tests/phase_00/test_parser.py`
- Tests: roundtrip idempotence (SENTINEL), UUID stability, atomic write no-temp, content hash determinism, vault config stamping on create.
- Add docstrings and assertion messages per §2.3 criteria.
- Acceptance: `pytest tests/phase_00/ -v` produces 5 passing or clearly failing (not erroring) tests against a working parser implementation.
- Effort: 2h

**T-12 — Translate Phase 1 pseudocode tests to real pytest file**
- File: `tests/phase_01/test_schema.py`
- Tests: inline edge extraction, inline inside code block ignored, merge deduplication (SENTINEL), merge adds new edges, writeback roundtrip, writeback idempotence.
- Acceptance: `pytest tests/phase_01/ -v` produces 6 passing or failing tests (not erroring).
- Effort: 2h

**T-13 — Translate Phase 2 pseudocode tests to real pytest file**
- File: `tests/phase_02/test_db.py`
- Tests: upsert and get, content hash skip, two-pass edge resolution, backlinks, FTS5 search, db is expendable (SENTINEL).
- Acceptance: `pytest tests/phase_02/ -v` produces 6 tests. The `test_db_is_expendable` test uses the `indexed_db` fixture and verifies result set equality after DB deletion and re-index.
- Effort: 2.5h

**T-14 — Translate Phase 3 pseudocode tests to real pytest file**
- File: `tests/phase_03/test_graph.py`
- Tests: ego depth 1, ego incoming, cycle does not loop (SENTINEL, `@pytest.mark.timeout(2)`), depth boundary, disconnected node, ASCII render arrows.
- Acceptance: `pytest tests/phase_03/ -v` produces 6 tests. The cycle test has a 2-second timeout enforced by `pytest-timeout`.
- Effort: 2.5h

**T-15 — Translate Phase 4 pseudocode tests to real pytest file**
- File: `tests/phase_04/test_eventbus.py`
- Tests: watcher fires on save, watcher debounces rapid saves (SENTINEL, `@pytest.mark.slow`), watcher ignores temp files, subscriber error isolation, sync queue drain node title.
- Acceptance: `pytest tests/phase_04/ -v` produces 5 tests. Timing tests pass with >95% reliability on a standard developer laptop.
- Effort: 3h (timing tests require iteration)

**T-16 — Translate Phase 5 pseudocode tests to real pytest file**
- File: `tests/phase_05/test_tui.py`
- Tests: node tree populated, search filters tree, j/k navigation, edit-save roundtrip, live update adds node (SENTINEL, `@pytest.mark.integration`), graph screen opens.
- All tests must be `async def` and use `app.run_test()` pilot.
- Acceptance: `pytest tests/phase_05/ -v` produces 6 tests. Tests assert against public API (selected_node_id, visible count) not internal widget fields.
- Effort: 4h (Textual pilot tests require environment setup)

**T-17 — Translate Phase 6 pseudocode tests to real pytest file**
- File: `tests/phase_06/test_api.py`
- Tests: create and get, node file written (SENTINEL), delete removes file, path traversal rejected, search by tag, websocket broadcast (SENTINEL), ego-graph endpoint.
- Acceptance: `pytest tests/phase_06/ -v` produces 7 tests. WebSocket test uses `timeout=2` on `receive_json()`.
- Effort: 3h

**T-18 — Translate Phase 7 pseudocode tests to real pytest file**
- File: `tests/phase_07/test_commit_queue.py`
- Tests: git init creates repo, db not committed, queue deduplicates edits, queue cancels create-delete (SENTINEL), queue edit-then-delete, message generation, queue persists to disk, startup commits leftover queue (SENTINEL), git failure non-fatal, push non-fatal without remote.
- Acceptance: `pytest tests/phase_07/ -v` produces 10 tests. All git tests use `tmp_path`-based repos. No test requires network access.
- Effort: 4h (git fixture setup is complex)

**T-19 — Translate Phase 8 pseudocode tests to real pytest file**
- File: `tests/phase_08/test_rag.py`
- Tests: context for query (SENTINEL), context depth 2 multi-hop, context caps triples, MCP search tool, MCP get-context tool (SENTINEL), MCP ego-graph tool, MCP create node, MCP resource returns markdown, output truncated at limit (SENTINEL).
- Acceptance: `pytest tests/phase_08/ -v` produces 9 tests. The large-vault truncation test builds nodes programmatically (not from committed .md files).
- Effort: 4h

---

### Tier 4 — Content Fixes (consistency and accuracy)

**T-20 — Fix Phase 8 body-from-DB architectural contradiction**
- In `context_for_query` code example, replace `node.body[:120]` with a comment explaining that body is not in the index and must be loaded from disk if needed.
- Acceptance: Phase 8's RAG code example contains no reference to `node.body` without a corresponding `parse(node.path)` call or an explicit comment about DB-vs-disk.
- Effort: 30min

**T-21 — Fix Phase 4 git integration comment (Phase 7 not Phase 8)**
- Update the "(Phase 8)" comment in Phase 4's `app.py` startup sequence to "(Phase 7)".
- Add one-sentence note clarifying that commit-on-file-changed is not used.
- Effort: 15min

**T-22 — Fix Phase 6 ego-graph endpoint specification**
- Clarify that the endpoint returns JSON (nodes + edges as dicts), not a rendered representation.
- Effort: 20min

**T-23 — Fix terminology: "notes" → "nodes" in Phase 7 commit message examples**
- Find all occurrences of "notes" used as a synonym for "nodes" in Phase 7's commit message generation section and replace with "nodes".
- Acceptance: `grep -n "notes" docs/learning/phase-07-version-control.md` returns zero results (outside of literal commit message strings that say "notes" as user-facing text).
- Effort: 20min

**T-24 — Fix Phase 1: Move FastMCP vault node to Phase 8**
- Remove `FastMCP` from Phase 6's vault node table (it is introduced in Phase 8).
- Acceptance: Phase 6's vault node table contains only nodes that reference concepts introduced in Phases 0–6.
- Effort: 15min

**T-25 — Add YAML-vs-Python naming note to Phase 1 Edge Format section**
- One paragraph explaining that YAML uses `relation-id` (hyphen) and Python uses `relation_id` (underscore), and that the parser maps between them.
- Effort: 20min

**T-26 — Add node type clarification note to Phase 0 or Phase 1**
- One paragraph: "The learning path uses `note` and `reference` types. The production system also has `active`, `active-service`, and `virtual` — these are out of scope here and documented in `future-ideas.md`."
- Effort: 15min

**T-27 — Add Phase 3 code stub clarification**
- Add `# Partial — learner completes the EgoEdge fields` comment to the incomplete `edges.append(EgoEdge(...))` lines in Phase 3's traversal code.
- Effort: 10min

---

### Summary Table

| ID | Task | Tier | Effort | Acceptance Criteria |
|---|---|---|---|---|
| T-01 | Root README.md | 1 | 2h | 90-second orientation test |
| T-02 | docs/README.md | 1 | 1h | Every file described exactly once |
| T-03 | Phase doc header template | 1 | 1.5h | 9 phase docs with consistent header |
| T-04 | Foundation doc header template | 1 | 1h | 10 foundation docs with consistent header |
| T-05 | Standardize section order | 1 | 3h | All 9 phases follow 11-section template |
| T-06 | Add Reference section to phase docs | 2 | 2h | All foundation links resolve, no broken links |
| T-07 | Add backward-reference "recall" notes | 2 | 3h | ~40 [U] entries annotated |
| T-08 | Add "coming up" forward notices | 2 | 45min | 8 transitions have a forward sentence |
| T-09 | tests/conftest.py shared fixtures | 3 | 3h | Collect-only passes, no import errors |
| T-10 | Phase-specific conftest.py (Phases 4–8) | 3 | 4h | All fixtures documented, no network calls |
| T-11 | Phase 0 test file | 3 | 2h | 5 tests, run to pass/fail not error |
| T-12 | Phase 1 test file | 3 | 2h | 6 tests |
| T-13 | Phase 2 test file | 3 | 2.5h | 6 tests, expendable test verifies re-index |
| T-14 | Phase 3 test file | 3 | 2.5h | 6 tests, cycle test has 2s timeout |
| T-15 | Phase 4 test file | 3 | 3h | 5 tests, timing tests stable >95% |
| T-16 | Phase 5 test file | 3 | 4h | 6 async tests against public API |
| T-17 | Phase 6 test file | 3 | 3h | 7 tests, WS test has 2s timeout |
| T-18 | Phase 7 test file | 3 | 4h | 10 tests, no network access |
| T-19 | Phase 8 test file | 3 | 4h | 9 tests, large vault built programmatically |
| T-20 | Fix body-from-DB contradiction (Ph 8) | 4 | 30min | No `node.body` without disk load |
| T-21 | Fix "(Phase 8)" comment (Ph 4) | 4 | 15min | Correct phase number cited |
| T-22 | Fix ego-graph endpoint spec (Ph 6) | 4 | 20min | Endpoint returns JSON, not rendered |
| T-23 | Fix "notes" vs "nodes" (Ph 7) | 4 | 20min | Zero unintended "notes" uses |
| T-24 | Move FastMCP vault node to Phase 8 | 4 | 15min | Phase 6 table contains only Ph0–6 concepts |
| T-25 | Add YAML-vs-Python naming note (Ph 1) | 4 | 20min | Note present in Edge Format section |
| T-26 | Add node type clarification (Ph 0/1) | 4 | 15min | Learner knows virtual/active are out of scope |
| T-27 | Add code stub clarification (Ph 3) | 4 | 10min | Partial stubs are marked with comments |

**Total effort estimate:** ~49 hours

**Recommended execution order:**
- Sprint 1 (12h): T-01 through T-05 (repo becomes navigable)
- Sprint 2 (6h): T-06 through T-08 (cross-references live)
- Sprint 3 (15h): T-09 through T-13 (Phases 0–2 fully testable)
- Sprint 4 (13h): T-14 through T-19 (Phases 3–8 fully testable)
- Sprint 5 (2h): T-20 through T-27 (consistency fixes)

Sprint 3 unblocks the first usable session of the learning path (Phases 0–2). The
learning path can be run end-to-end (if slowly) after Sprint 4. Sprint 5 is polish
that prevents learner confusion but does not block path execution.
