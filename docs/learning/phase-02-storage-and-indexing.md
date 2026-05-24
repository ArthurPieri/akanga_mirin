# Phase 2 — Storage and Indexing

**Core concept:** The DB is not the source of truth — it is an expendable structural
index derived from the files. Delete it at any time: `akanga index` rebuilds it
completely. This constraint shapes every decision in this phase: never put anything
in the DB that can't be reconstructed from a file or from `akanga.yaml`.

**What makes this non-obvious:** The instinct is to treat the DB as the primary store
and files as exports. Here it's inverted. The DB exists because querying "give me all
nodes with tag `cognition`" against flat files would require scanning every file every
time. The DB makes reads fast. Nothing more.

---

## Concepts

### SQLite

An embedded, serverless, single-file relational database. No daemon process, no
network socket, no configuration — the DB is a single `.akanga.db` file you can copy,
delete, or inspect with any SQLite client. ACID-compliant: every write either fully
completes or fully rolls back. The right choice for a local personal tool: zero
operational overhead, fast for reads up to millions of rows, and the file format is
stable across decades.

> Akanga node: `SQLite`

### WAL Mode (Write-Ahead Logging)

SQLite's concurrency mode. In the default journal mode, any write locks the entire
DB file — readers block. In WAL mode, writers append to a separate log file while
readers continue reading the last committed snapshot. Readers and writers don't block
each other (except at checkpoint time, when the log is merged back). Akanga needs WAL
because three things access the DB concurrently: the file watcher thread, the asyncio
event loop (active manager, API), and CLI commands. Without WAL, they would deadlock
under normal use.

> Akanga node: `WAL Mode`

### Adjacency List (Graph in Relational Tables)

The standard way to store a directed graph in a relational DB. Two tables: `nodes`
(one row per node) and `edges` (one row per edge, with `source_id` and `target_id`
foreign keys). To find all neighbors of node X: `SELECT * FROM edges WHERE source_id
= X`. To find all backlinks: `SELECT * FROM edges WHERE target_id = X`. Simple, fast,
and joins cleanly. The alternative (adjacency matrix) wastes space for sparse graphs
and requires schema changes when new nodes are added.

> Akanga node: `Adjacency List`

### Derived Index

A data structure that is fully reconstructible from its source and therefore
expendable. The Akanga DB is a derived index: every row in `nodes` was parsed from a
`.md` file; every row in `edges` was parsed from a frontmatter `edges:` block; every
row in `workspaces` and `relations` was loaded from `akanga.yaml`. If the DB is
deleted, `akanga index --vault ./vault` rebuilds it identically. This means the DB is
never committed to git, can be excluded from backups, and can be safely deleted to
resolve corruption. The corollary: never write anything to the DB that doesn't have a
corresponding representation in a file or in `akanga.yaml`.

> Akanga node: `Derived Index`

### Two-Pass Indexing

When indexing a vault, edges must be resolved after all nodes are indexed. An edge
`target-id` is a UUID — to resolve it, the target node must already be in the `nodes`
table. If you process edges as you encounter files, you will hit edges pointing to
nodes you haven't seen yet, leaving `target_id` empty even when the target exists.
The solution: pass 1 indexes all nodes (UUID → path mapping complete), pass 2 resolves
all edges against the complete node registry.

> Akanga node: `Two-Pass Indexing`

### FTS5 (Full-Text Search)

SQLite's built-in full-text search extension. Creates a virtual table with an
inverted index: for each word in the indexed fields, it stores which rows contain it.
`SELECT * FROM nodes_fts WHERE nodes_fts MATCH 'cognition'` returns all matching
nodes fast, regardless of vault size. In Akanga, FTS5 covers `title`, `tags`, and
`description` (reference node short description) only — never the prose body. Body
search is handled by ripgrep at the filesystem level. The DB never stores prose
content.

> Akanga node: `FTS5`

### Thread Safety

Shared mutable state accessed from multiple threads without synchronization produces
data races: corrupted writes, partial reads, crashes. Akanga's DB is shared between
the file watcher thread (sync), the asyncio event loop (active manager, API), and CLI
commands. WAL mode handles concurrent SQLite-level access, but application-level
sequences like "check if node exists → upsert" must be atomic at the application
level. A `threading.Lock` wraps each compound operation so only one thread executes
it at a time.

> Akanga node: `Thread Safety`

---

## The Complete DB Schema

```sql
-- Structural graph index
CREATE TABLE nodes (
    id            TEXT PRIMARY KEY,
    path          TEXT NOT NULL UNIQUE,
    title         TEXT NOT NULL,
    type          TEXT NOT NULL,
    tags          TEXT NOT NULL DEFAULT '[]',
    author        TEXT,
    created_at    TEXT,
    updated_at    TEXT,
    meta          TEXT NOT NULL DEFAULT '{}',
    content_hash  TEXT NOT NULL,
    url           TEXT,
    external_type TEXT,
    description   TEXT
);

CREATE TABLE edges (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id    TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    target_id    TEXT,
    target_title TEXT NOT NULL,
    relation     TEXT NOT NULL,
    relation_id  TEXT NOT NULL,
    UNIQUE(source_id, relation_id, target_title)
);

-- Config mirror (loaded from akanga.yaml at startup)
CREATE TABLE workspaces (
    id         TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE node_workspaces (
    node_id      TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    workspace_id TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
    PRIMARY KEY (node_id, workspace_id)
);

CREATE TABLE relations (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL,
    description TEXT,
    symmetric   INTEGER NOT NULL DEFAULT 0,
    inverse_id  TEXT
);

-- Unified sync queue (drained in Phase 4)
CREATE TABLE sync_queue (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    job_type     TEXT NOT NULL,
    entity_id    TEXT NOT NULL,
    new_name     TEXT NOT NULL,
    enqueued_at  TEXT NOT NULL,
    processed_at TEXT
);

-- Active node health check results (Phase 7)
CREATE TABLE active_results (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    node_id   TEXT NOT NULL REFERENCES nodes(id) ON DELETE CASCADE,
    timestamp TEXT NOT NULL,
    status    TEXT NOT NULL,
    payload   TEXT
);

-- FTS5: title + tags + description only (no prose body)
CREATE VIRTUAL TABLE nodes_fts USING fts5(
    title, tags, description,
    content=nodes, content_rowid=rowid
);
```

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `SQLite` | reference | `is_applied_in` → `Akanga DB`; `is_a` → `Embedded Database` |
| `WAL Mode` | note | `is_part_of` → `SQLite`; `enables` → `Concurrent DB Access`; `solves` → `Reader-Writer Blocking` |
| `Adjacency List` | note | `is_a` → `Graph Representation`; `is_applied_in` → `Akanga Edge Table`; `contrasts_with` → `Adjacency Matrix` |
| `Derived Index` | note | `qualifies` → `Akanga DB`; `contrasts_with` → `Source of Truth`; `enables` → `Safe DB Deletion` |
| `Two-Pass Indexing` | note | `is_applied_in` → `Akanga Indexer`; `solves` → `Unresolved Edge Targets` |
| `FTS5` | note | `is_part_of` → `SQLite`; `is_applied_in` → `Akanga Search`; `contrasts_with` → `ripgrep` |
| `Thread Safety` | note | `is_applied_in` → `GraphDatabase`; `uses` → `threading.Lock`; `qualifies` → `WAL Mode` |

---

## What You Build

**`db.py`** — `GraphDatabase` class:

| Method | What it does |
|---|---|
| `connect(path)` | Open DB, create schema, enable WAL, load config |
| `upsert_node(node)` | Insert or replace node row + sync FTS5 |
| `delete_node(node_id)` | Remove node + cascade edges |
| `upsert_edge(edge)` | Insert or replace edge row |
| `get_node(node_id) → Node` | Fetch by UUID |
| `get_neighbors(node_id) → list[Node]` | Outgoing edges → target nodes |
| `get_backlinks(node_id) → list[Node]` | Incoming edges → source nodes |
| `search(query) → list[Node]` | FTS5 over title + tags + description |
| `load_config()` | Load workspaces + relations from `akanga.yaml` into config tables |

**`indexer.py`** — `VaultIndexer`:

| Method | What it does |
|---|---|
| `index_vault(vault, db)` | Full two-pass scan of vault directory |
| `index_file(path, db)` | Single file upsert — used by file watcher in Phase 4 |

---

## Deliverable

```python
def test_upsert_and_get():
    db = GraphDatabase(tmp_db)
    node = create(title="Test", type="note", vault=tmp_path)
    db.upsert_node(node)
    assert db.get_node(node.id).title == node.title

def test_content_hash_skip(mocker):
    db = GraphDatabase(tmp_db)
    node = create(title="Test", type="note", vault=tmp_path)
    db.upsert_node(node)
    spy = mocker.spy(db, "_write_node")
    db.upsert_node(node)   # same hash — must skip
    spy.assert_not_called()

def test_two_pass_edge_resolution():
    # Node A contradicts Node B. Index A before B.
    # After full index_vault(), edge from A has target_id resolved to B's UUID.
    ...

def test_backlinks():
    # After indexing A contradicts B, get_backlinks(B.id) returns [A]
    ...

def test_fts5_search():
    db = GraphDatabase(tmp_db)
    node = create(title="Fast Thinking", type="note", vault=tmp_path)
    node.tags = ["cognition"]
    db.upsert_node(node)
    results = db.search("cognition")
    assert any(r.id == node.id for r in results)

def test_db_is_expendable(tmp_path):
    vault, db_path = setup_vault_with_nodes(tmp_path)
    indexer.index_vault(vault, GraphDatabase(db_path))
    results_before = GraphDatabase(db_path).search("cognition")
    db_path.unlink()
    indexer.index_vault(vault, GraphDatabase(db_path))
    results_after = GraphDatabase(db_path).search("cognition")
    assert {r.id for r in results_before} == {r.id for r in results_after}
```

Plus 7 vault nodes with typed edges. The `test_db_is_expendable` test is the most
important one — it proves the core architectural promise of this phase.
