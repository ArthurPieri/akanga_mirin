# Phase 1B — Data Modeling: Workspace Registry and Background Sync

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
- Implement `enqueue_title_sync` and `pending_sync_jobs` and explain why the queue is stored in the DB rather than in memory
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
  → See `docs/foundations/sqlite-basics.md` (queue table patterns)

---

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
unfolding thought gave rise to the cosmos). Its UUID is generated at `akanga init`.
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

> → Foundation doc: `docs/foundations/sqlite-basics.md` (queue table patterns)

> → Foundation doc: `docs/foundations/design-patterns.md` (Debounce / deferred execution section)

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
def create(title: str, type: str, vault: Path,
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

**`sync_queue.py`** — a new module, two operations at this phase:

| Function | What it does |
|---|---|
| `enqueue_title_sync(db, node_id, new_title)` | Add a pending job when a title change is detected |
| `pending_sync_jobs(db) → list[dict]` | Return all unprocessed jobs — consumed by Phase 4 |

The queue is stored in the DB as a `sync_queue` table (defined in Phase 2):

```
sync_queue — id, job_type, entity_id, new_name, enqueued_at, processed_at (nullable)
```

Processing logic — scanning referencing files and updating their `target` fields —
is implemented in Phase 4 alongside the file watcher and event bus.

---

## Deliverable

```python
def test_reference_node_create():
    node = create(
        title="Python Docs",
        type="reference",
        vault=tmp_path,
        url="https://docs.python.org",
        external_type="webpage",
        description="Official Python documentation"
    )
    assert node.type == "reference"
    re_parsed = parse(node.path)
    assert re_parsed.url == "https://docs.python.org"
    assert re_parsed.external_type == "webpage"
    assert re_parsed.description == "Official Python documentation"

def test_enqueue_title_sync(tmp_db):
    db = connect(tmp_db)
    enqueue_title_sync(db, node_id="abc-123", new_title="Renamed Title")
    jobs = pending_sync_jobs(db)
    assert len(jobs) == 1
    assert jobs[0]["entity_id"] == "abc-123"
    assert jobs[0]["new_name"] == "Renamed Title"
    assert jobs[0]["processed_at"] is None

def test_sync_queue_survives_restart(tmp_db):
    db = connect(tmp_db)
    enqueue_title_sync(db, node_id="abc-123", new_title="Renamed Title")
    db.close()
    db2 = connect(tmp_db)   # reopen — queue must persist
    jobs = pending_sync_jobs(db2)
    assert len(jobs) == 1

def test_enqueue_is_idempotent(tmp_db):
    db = connect(tmp_db)
    enqueue_title_sync(db, node_id="abc-123", new_title="Renamed Title")
    enqueue_title_sync(db, node_id="abc-123", new_title="Renamed Title")
    jobs = pending_sync_jobs(db)
    assert len(jobs) == 1   # duplicate enqueue does not create two jobs
```

Plus 6 vault nodes with typed edges (including Nhamandu and Akanga with full seed
body content). The vault is the proof of understanding, not just the tests.

---

## Reflect

> **Solo:** The sync queue stores jobs in the DB so they survive restarts. Think about what would happen if jobs were stored only in memory. Under what scenarios (common ones, not exotic failures) would a user lose sync work silently, and what would they observe?

> **Group:** Workspace rename and node title rename both enqueue the same kind of job. Is it correct to unify them in one `sync_queue` table with a `job_type` field, or should they be separate tables? What does unifying them make easier, and what does it obscure? Is there a case where the distinction matters at drain time?
