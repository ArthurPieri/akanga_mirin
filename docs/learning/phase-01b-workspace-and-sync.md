# Phase 1B — Data Modeling: Workspace Registry and Background Sync

**Estimated time: 2–3h**

**Core concept:** Not all mutations can happen on the critical path. When a node is
renamed, every edge pointing to it has a stale `target` display name. Updating those
files immediately would make every save proportionally slower as the vault grows.
Phase 1B introduces the workspace registry and the background sync queue — the two
mechanisms that keep the system fast by deferring expensive, vault-wide mutations to
a controlled background process.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Explain the dual-key pattern (display name + UUID) as applied to workspace membership and why it tolerates renames without breaking references
- Describe what the sync queue stores, when jobs are enqueued, and when they are drained
- Implement `enqueue_title_sync`, `pending_sync_jobs`, and `mark_processed` and explain why the queue is stored in the DB rather than in memory
- Extend `create()` to produce `reference` nodes with `url`, `external_type`, and `description` fields

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] Phase 1A is complete: I have a working `Edge` dataclass, `extract_inline_edges`, `merge_edges`, and `write_back`
  → Required: complete Phase 1A deliverable tests first
- [ ] I understand the dual-key pattern as applied to edges (`relation` + `relation_id`, `target` + `target_id`)
  → Covered in Phase 1A — The Edge Format section
- [ ] I can explain the difference between a source of truth and a derived index
  → Covered in Phase 1A — Source of Truth concept
- [ ] I have a basic understanding of what a database queue or work queue is
  → See `docs/foundations/sqlite-basics.md`

---

## Quick Start

```bash
make skeleton PHASE=1    # copy the starting code into ./src/ (shared by 1A and 1B)
make test PHASE=1        # full phase 1 suite (1A schema + 1B sync queue)
make study PHASE=1b      # open the tmux study session for 1B
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### Node Types as Schema Variants

Not all nodes have the same shape. A `note` has a body and edges. A `reference` has
a URL, an external type, and a short description — and may have a minimal body. Both
share the common frontmatter fields (id, title, type, tags, author, created_at,
updated_at, meta, edges). The `type` field determines which additional fields are
expected. This is a schema variant pattern — one base schema, multiple typed
extensions.

> Akanga node: `Node Types as Schema Variants`

### Reference Integrity via UUID

Reference integrity is the guarantee that a reference always points to something that
exists and is correctly identified. In a relational database, a foreign key constraint
enforces this at write time — the DB rejects invalid references. In Akanga, enforcing
this at write time is impossible: files are edited by any text editor, outside
Akanga's control.

The UUID is what makes this safe. Every edge stores both `target-id` (UUID, never
changes) and `target` (title, human-readable display cache). When a node is renamed,
the UUID still points to the correct node — the graph remains structurally correct.
Only the `target` display name becomes stale. This is a deliberate tradeoff: human
editability over strict consistency.

**Path changes are free:** No node stores another node's path. Moving a file costs
nothing — the indexer finds it at the new location by UUID and updates the DB. Zero
other files need editing.

**Title changes create stale display names:** When "Blink — Gladwell" is renamed to
"Blink by Malcolm Gladwell", every edge with `target: Blink — Gladwell` has a stale
display name. Not broken — the UUID still resolves correctly — but misleading when a
human reads the raw file. A background sync queue resolves this lazily without
blocking the save path.

> Akanga node: `Reference Integrity`

### Workspace Registry

Workspaces are named, UUID-identified entities stored in `akanga.yaml` — not in
the vault's node files. This is the same dual-key pattern as edges: `name` is the
human-readable display cache, `id` is the authoritative UUID generated once at
workspace creation and never changed. When a workspace is renamed, only `akanga.yaml`
changes; a sync queue job lazily updates the `name` display field in all node
frontmatter files that belong to that workspace.

The default workspace is **Nhamandu** (Mbya Guaraní: the primordial being whose
unfolding thought gave rise to the cosmos). Its UUID is generated when the vault
is scaffolded (`make vault-init` creates `akanga.yaml`).
The name is configurable in `akanga.yaml` — changing it enqueues a workspace name
sync job without breaking any node's graph membership.

Every node's `graph` field follows the same structure as edges — `name` + `id`:

```yaml
graph:
  - name: Nhamandu
    id: a3f7c2be-1234-5678-abcd-ef0123456789
  - name: ProjectX
    id: b2c3d4e5-abcd-ef01-2345-678901234567
```

Absent or empty `graph` auto-populates with the default workspace on first
write-back. The universal workspace (Nhamandu) always shows all nodes in the TUI
regardless of `graph` field — named workspaces are additive filters on top.

> Akanga node: `Workspace Registry`

> → Foundation doc: `docs/foundations/yaml-and-markdown-frontmatter.md` (YAML config patterns)

### Background Sync Queue

A queue of pending work items that are too expensive to execute on the critical path
(file save, TUI render) but must eventually be completed. In Akanga, the sync queue
holds two kinds of jobs: node title changes ("update all edges pointing to node X to
display the new title") and workspace renames ("update the workspace name display
cache in all nodes belonging to workspace Y"). The queue is stored in the DB so it
survives restarts.

The queue decouples *detection* (cheap, happens on every title or workspace rename)
from *execution* (expensive, involves reading and writing multiple files). Triggers
for draining: TUI opens, a specific node is opened (drains only jobs relevant to
that node), explicit sync command, or a background schedule. This keeps
initialization and save times fast regardless of vault size.

> Akanga node: `Background Sync Queue`

> → Foundation doc: `docs/foundations/sqlite-basics.md`

> → Foundation doc: `docs/foundations/design-patterns.md` (Debounce / deferred execution section)

### Relation Hygiene

The mechanisms in this phase open two graph-integrity loops. Both get an explicit
contract here so they don't become silent corruption later.

**Typo-minting.** The inline edge syntax accepts any relation name — typing
`[[Blink by Gladwell | contradcits]]` silently mints a brand-new custom relation
type. One character of typo and the graph now contains `contradicts` and
`contradcits` as two unrelated relations, splitting every query that filters on the
real one. The contract is **soft validation at write-back**: when `write_back`
encounters a relation name that is neither in the 71-type registry nor
pre-registered, it never rejects the edge (files must stay writable by any editor),
but it logs a warning with a nearest-match suggestion from
`difflib.get_close_matches`:

```
WARNING: unknown relation 'contradcits' in blink.md — did you mean 'contradicts'?
```

Genuinely custom relation types are allowed — but they must be pre-registered in
`akanga.yaml`, one line each under `custom_relations:`:

```yaml
custom_relations:
  - refutes_methodology_of
```

A pre-registered name produces no warning. `make vault-check` already applies the
same soft check (warning + nearest-match suggestion) across the whole vault; the
write-back warning is that check moved to the moment of mutation, where a typo is
cheapest to fix.

**Rename convergence.** The sync queue does not promise ordered delivery, and
convergence is not automatic: two renames of the same node in quick succession leave
one pending row (enqueue is idempotent) whose `new_name` snapshot may already be
stale by the time the drain runs. The contract that makes out-of-order processing
safe: **the drain must re-read current truth at processing time.** A drain worker
never trusts the job's `new_name` snapshot — it looks up the entity's *current*
name by `entity_id` (the node's title in the DB, or the workspace's name in
`akanga.yaml`) at the moment it processes the job, and writes that. A job row is a
dirty flag — "this entity's display caches need refreshing" — not a value to apply.
Under this contract, late, duplicate, and out-of-order jobs all converge to the
same final state: whatever is true now.

*Future work (not built in this learning path):* even with the re-read contract, an
edge can stay stale forever if its job row is lost — say, a crash after the rename
commits but before the enqueue does. The V1 anti-entropy backstop is a full-vault
reconciliation pass, `akanga sync --full`: walk every edge, compare each `target`
display name against the current title of its `target_id`, rewrite mismatches. It
needs no queue state at all and bounds staleness to "since the last full sync." It
is specced here for completeness and deliberately deferred.

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Node Types as Schema Variants` | note | `is_applied_in` → `Node Data Model`; `subtype_of` → `Schema Design Pattern` |
| `Reference Integrity` | note | `qualifies` → `Edge Target Field` |
| `UUID` | note | `solves` → `Reference Integrity` |
| `Background Sync Queue` | note | `solves` → `Stale Title Display`; `solves` → `Stale Workspace Name`; `enables` → `Lazy Sync` |
| `Workspace Registry` | note | `is_part_of` → `Vault Configuration`; `implements` → `Named Graph Scoping`; `uses` → `UUID` |
| `Nhamandu` | note | `subtype_of` → `Guaraní Deity`; `is_applied_in` → `Akanga Default Workspace`; `is_analogous_to` → `Primordial Source` |
| `Akanga` | note | `subtype_of` → `Tupi-Guaraní Word`; `is_applied_in` → `Personal Knowledge Graph Tool`; `has_context` → `Tupi-Guaraní Language` |

### Seed Notes

**Nhamandu** — full body for the vault node:

> Nhamandu (also written Ñamandú or Nhamandu Tenonde, "Our Father Who Comes First")
> is the primordial being in Mbya Guaraní cosmology. Before the cosmos existed,
> Nhamandu unfolded his own thought — and from that thought arose language, then the
> earth, then all living things. He is not a creator who builds from outside, but a
> source from whom existence unfolds from within.
>
> In Akanga, *Nhamandu* is the name of the default universal workspace — the container
> that holds all knowledge before it is organized into named workspaces. Just as
> Nhamandu precedes all things, the Nhamandu workspace encompasses all nodes.
>
> Source: Cadogan, León (1959). *Ayvu Rapyta: Textos míticos de los Mbyá-Guaraní del
> Guairá*. University of São Paulo. The foundational academic text on Mbya cosmology.

**Akanga** — full body for the vault node:

> Akanga is a word from Tupi-Guaraní, one of the most widely spoken indigenous
> language families in South America (Brazil, Paraguay, Bolivia, Argentina). It means
> "head" or "mind" — the seat of thought, knowledge, and identity.
>
> In Tupi-Guaraní languages, the head is not merely an anatomical part but the locus
> of the person's inner life — thought, memory, will. The word appears across the
> Tupi-Guaraní language family with closely related forms.
>
> In this project, *Akanga* is the name of the personal knowledge graph tool: the
> external mind, the structured record of what you know and how things relate.
> The name reflects the core purpose — building a second mind outside your head,
> organized not as documents but as a graph of connected, meaningful relationships.

---

## What You Build

New module `sync_queue.py`, plus extensions to `parser.py` from Phase 1A.

**`create()` extended** to handle reference nodes:

```python
def create(title: str, node_type: str, vault: Path,
           url: str = "",
           external_type: str = "",
           description: str = "") -> Node:
    ...
```

The reference node type adds three top-level frontmatter fields:

```yaml
type: reference
url: https://www.example.com
external_type: webpage   # webpage | github | paper | book | api | file
description: Short description of the resource
```

> **Vault-verified exercise.** The reference-node extension has no automated tests
> in `tests/phase_01/` — the base `create()` contract is covered by Phase 0's
> create tests, and the extension is verified through your vault: create a real
> `reference` node (e.g., `os.replace` from the Phase 0 table), open the file,
> and confirm `url`, `external_type`, and `description` land in frontmatter and
> survive a `parse → write → parse` roundtrip.

**`sync_queue.py`** — a new module, three operations at this phase:

| Function | What it does |
|---|---|
| `enqueue_title_sync(db, node_id, new_title)` | Add a pending job when a title change is detected; idempotent — re-enqueueing the same pending node does not create a duplicate row |
| `pending_sync_jobs(db) → list[dict]` | Return all unprocessed jobs (`processed = 0`) — consumed by Phase 4 |
| `mark_processed(db, job_id)` | Set `processed = 1` for one job — how a drained job leaves the queue |

All three take `db` as a plain `sqlite3.Connection` — `GraphDatabase` does not
exist until Phase 2. Anything that can `execute()` and `commit()` works, which is
exactly what makes the module testable in isolation.

The queue is stored in the DB as a `sync_queue` table, added to GraphDatabase.DB_SCHEMA in Phase 2:

```
sync_queue — id, entity_id, new_name, processed (0/1, default 0), created_at (default now)
```

Note: there is no `job_type` column at this phase — all rows are node-title
propagation jobs, and `processed` is a 0/1 integer flag rather than a timestamp.
Workspace-name jobs (Phase 4+) reuse the same row shape and are distinguished by
the caller, not by a column.

Processing logic — scanning referencing files and updating their `target` fields —
is implemented in Phase 4 alongside the file watcher and event bus.

---

## Deliverable

Passing the 1B half of the Phase 1 suite: `tests/phase_01/test_sync_queue.py`.
These are the tests, by name:

- `test_enqueue_creates_row` — `enqueue_title_sync` inserts exactly one row into `sync_queue`
- `test_enqueue_is_idempotent` — enqueueing the same `node_id` twice leaves only one pending row
- `test_pending_jobs_returns_unprocessed` — `pending_sync_jobs` returns only rows with `processed = 0`
- `test_mark_processed_sets_flag` — `mark_processed(db, job_id)` sets `processed = 1` for that job
- `test_sync_queue_survives_restart` — a job enqueued on one connection is visible after closing and reopening the DB file (enqueue must commit)

The contract your functions are tested against — note that `db` is a **raw
`sqlite3.Connection`**, not a `GraphDatabase` (which doesn't exist until Phase 2).
The `tmp_db` fixture in `tests/phase_01/conftest.py` pre-creates the table:

```python
# tests/phase_01/conftest.py (excerpt) — what your functions receive as `db`
conn = sqlite3.connect(str(tmp_path / "test.db"))
conn.execute("""
    CREATE TABLE IF NOT EXISTS sync_queue (
        id TEXT PRIMARY KEY,
        entity_id TEXT NOT NULL,
        new_name TEXT NOT NULL,
        processed INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL DEFAULT (datetime('now'))
    )
""")
conn.commit()
```

And the shape of a typical test (illustrative — the real suite is `tests/phase_01/`):

```python
def test_enqueue_creates_row(tmp_db):           # tmp_db is a sqlite3.Connection
    enqueue_title_sync(tmp_db, node_id="node-001", new_title="New Title")
    rows = tmp_db.execute("SELECT * FROM sync_queue").fetchall()
    assert len(rows) == 1
```

The reference-node `create()` extension is the vault-verified half of this phase
(see the callout in What You Build): create at least one real `reference` node
and confirm its frontmatter by hand.

Plus 7 vault nodes with typed edges (including Nhamandu and Akanga with full seed
body content). The vault is the proof of understanding, not just the tests.

---

## Reflect

> **Solo:** The sync queue stores jobs in the DB so they survive restarts. Think about what would happen if jobs were stored only in memory. Under what scenarios (common ones, not exotic failures) would a user lose sync work silently, and what would they observe?

> **Group:** Workspace rename and node title rename both enqueue the same kind of job. Is it correct to unify them in one `sync_queue` table with a `job_type` field, or should they be separate tables? What does unifying them make easier, and what does it obscure? Is there a case where the distinction matters at drain time?
