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

## Learning Objectives

By the end of this phase, you will be able to:
- Explain why WAL mode is required when multiple threads access the same SQLite DB, and what symptom appears without it
- Implement `upsert_node` with correct FTS5 synchronization and content-hash-based skip logic
- Explain why a `threading.Lock` is needed even when SQLite is in WAL mode, and give a concrete example of a read-check-write race condition
- Describe the two-pass indexing strategy and explain why pass 1 must complete before pass 2 begins
- Distinguish between a derived index and a source of truth and explain the practical consequence for backup and recovery

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] Phase 1A and Phase 1B are complete: I have working `Edge`, `extract_inline_edges`, `merge_edges`, `write_back`, and `sync_queue` implementations
  → Required: complete Phase 1A and 1B deliverable tests first
- [ ] I can write a basic SQL SELECT, INSERT, and INSERT OR REPLACE statement
  → See `docs/foundations/sqlite-basics.md`
- [ ] I understand what a database transaction is and what ACID means
  → See `docs/foundations/sqlite-basics.md`
- [ ] I know what a Python `threading.Lock` is and can write a `with lock:` block
  → See `docs/foundations/python-threading.md`

---

## Quick Start

```bash
make skeleton PHASE=2    # copy the starting code into ./src/
make test PHASE=2        # run the tests (they will fail initially)
make study PHASE=2       # open the tmux study session
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### SQLite

An embedded, serverless, single-file relational database. No daemon process, no
network socket, no configuration — the DB is a single `.akanga.db` file you can copy,
delete, or inspect with any SQLite client. ACID-compliant: every write either fully
completes or fully rolls back. The right choice for a local personal tool: zero
operational overhead, fast for reads up to millions of rows, and the file format is
stable across decades.

> Akanga node: `SQLite`

> → Foundation doc: `docs/foundations/sqlite-basics.md`

### WAL Mode (Write-Ahead Logging)

SQLite's concurrency mode. In the default journal mode, any write locks the entire
DB file — readers block. In WAL mode, writers append to a separate log file while
readers continue reading the last committed snapshot. Readers and writers don't block
each other (except at checkpoint time, when the log is merged back). Akanga needs WAL
because three things access the DB concurrently: the file watcher thread, the asyncio
event loop (active manager, API), and CLI commands. Without WAL, they would deadlock
under normal use.

> Akanga node: `WAL Mode`

> → Foundation doc: `docs/foundations/sqlite-basics.md` (WAL Mode section)

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
`.md` file; every row in `edges` was extracted from wikilinks and frontmatter edge
blocks in those same files; workspace and relation vocabulary data lives only in
`akanga.yaml` (not in the DB at this phase). If the DB is deleted, `akanga index
--vault ./vault` rebuilds it identically. This means the DB is never committed to git,
can be excluded from backups, and can be safely deleted to resolve corruption. The
corollary: never write anything to the DB that doesn't have a corresponding
representation in a file or in `akanga.yaml`.

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
nodes fast, regardless of vault size. In Akanga, FTS5 covers `title` and `tags` only — never the prose body. Body
search is handled by ripgrep at the filesystem level. The DB never stores prose
content. (A `description` column for reference nodes is a candidate for a later
phase — it is not in the Phase 02 schema.)

> Akanga node: `FTS5`

> → Foundation doc: `docs/foundations/sqlite-basics.md` (FTS5 section)

### Thread Safety

Shared mutable state accessed from multiple threads without synchronization produces
data races: corrupted writes, partial reads, crashes. Akanga's DB is shared between
the file watcher thread (sync), the asyncio event loop (active manager, API), and CLI
commands. WAL mode handles concurrent SQLite-level access, but application-level
sequences like "check if node exists → upsert" must be atomic at the application
level. A `threading.Lock` wraps each compound operation so only one thread executes
it at a time.

> Akanga node: `Thread Safety`

> → Foundation doc: `docs/foundations/python-threading.md` (Lock and compound operations section)

---

## The Complete DB Schema

The schema below is the exact `DB_SCHEMA` constant in `skeletons/phase_02/src/akanga_core/db.py`.
Do not add extra tables or columns at this phase.

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id TEXT PRIMARY KEY,
    path TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    type TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT,
    relation TEXT,
    relation_id TEXT,
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    title,
    tags,
    content='nodes',
    content_rowid='rowid'
);
```

> **Note:** The `sync_queue` table is added to DB_SCHEMA in Phase 2 (it was introduced conceptually in Phase 1B). The `active_results` table is added when building the active node manager
> (advanced — not covered in this phase). Fields like `author`, `created_at`, `updated_at`,
> `meta`, `url`, `external_type`, and `description` that you see in node frontmatter are not
> columns in the Phase 02 `nodes` table — they are stored only in the `.md` file itself and
> accessible by re-parsing it.

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `SQLite` | reference | `is_applied_in` → `Akanga DB`; `subtype_of` → `Embedded Database` |
| `WAL Mode` | note | `is_part_of` → `SQLite`; `enables` → `Concurrent DB Access`; `solves` → `Reader-Writer Blocking` |
| `Adjacency List` | note | `subtype_of` → `Graph Representation`; `is_applied_in` → `Akanga Edge Table`; `contrasts_with` → `Adjacency Matrix` |
| `Derived Index` | note | `qualifies` → `Akanga DB`; `contrasts_with` → `Source of Truth`; `enables` → `Safe DB Deletion` |
| `Two-Pass Indexing` | note | `is_applied_in` → `Akanga Indexer`; `solves` → `Unresolved Edge Targets` |
| `FTS5` | note | `is_part_of` → `SQLite`; `is_applied_in` → `Akanga Search`; `contrasts_with` → `ripgrep` |
| `Thread Safety` | note | `is_applied_in` → `GraphDatabase`; `uses` → `threading.Lock`; `qualifies` → `WAL Mode` |

---

## What You Build

**`db.py`** — `GraphDatabase` class:

| Method | What it does |
|---|---|
| `__init__(db_path)` | Open DB, create schema, enable WAL mode (connection is in `__init__`, not a separate `connect`) |
| `close()` | Close the underlying SQLite connection |
| `upsert_node(node)` | Insert or replace node row + sync FTS5 |
| `delete_node(node_id)` | Remove node + cascade edges |
| `upsert_edge(source_id, target_id, relation, relation_id)` | Insert a new edge row, return its UUID |
| `get_node(node_id) → Node` | Fetch by UUID |
| `list_nodes(limit=100, offset=0) → list[Node]` | Paginated list of all nodes |
| `get_neighbors(node_id) → list[Node]` | Outgoing edges → target nodes |
| `get_backlinks(node_id) → list[Node]` | Incoming edges → source nodes |
| `search_fts(query, limit=20) → list[Node]` | FTS5 over title + tags |

**`indexer.py`** — `VaultIndexer`:

| Method | What it does |
|---|---|
| `full_scan_and_index(vault, db)` | Full two-pass scan of vault directory |
| `index_file(path, db)` | Single file upsert — used by file watcher in Phase 4 |

---

## Common Pitfalls

**FTS5 operator injection.** FTS5 MATCH queries accept operators (`AND`, `OR`, `NOT`, `*`) directly in the query string. A user who searches for `fast*` or `cognition OR memory` gets a different query than expected — and a user who types a malformed FTS5 expression triggers a SQLite error. Mitigation: always use parameterized queries (never string-format the term into SQL), AND quote the term using FTS5's `"..."` literal syntax so it is treated as a phrase, not an operator expression. Example: `WHERE nodes_fts MATCH ?` with the parameter `'"cognition"'` (double-quoted inside the FTS5 string).

**Thread safety: read-check-write must be atomic.** WAL mode prevents SQLite-level deadlocks between readers and writers, but it does not prevent application-level races. The sequence "read content_hash → compare → upsert if different" is a compound operation: between the read and the upsert, another thread can write a different hash. Wrap the entire compound in `with self._lock:` — not just the final write.

**Derived index: never store prose body in the DB.** The DB is rebuilt from files on `akanga index`. If you store prose content in the DB, you have two sources of truth that can diverge — and rebuild becomes lossy if the DB row has content that the file doesn't. FTS5 covers `title` and `tags` only. Body search lives at the filesystem level (ripgrep). This is not a performance choice — it is an architectural constraint that keeps the DB expendable.

---

## Deliverable

```python
def test_upsert_and_get():
    db = GraphDatabase(tmp_db)
    node = create(title="Test", type="note", vault=tmp_path)
    db.upsert_node(node)
    assert db.get_node(node.id).title == node.title

def test_content_hash_skip(tmp_path, mocker):
    # Arrange: write a real .md file so the indexer can read and hash it.
    vault = tmp_path / "vault"
    vault.mkdir()
    md_file = vault / "test-node.md"
    md_file.write_text("---\ntitle: Test\ntype: note\n---\nHello.\n")

    db = GraphDatabase(tmp_path / ".akanga.db")

    # First index — must call upsert_node to populate the DB.
    indexer.index_file(str(md_file), db, str(vault))

    # Spy AFTER the first index so we start with a clean call count.
    spy = mocker.spy(db, "upsert_node")

    # Second index of the same file — content hash unchanged, so the indexer
    # must detect the match and return early WITHOUT calling upsert_node.
    indexer.index_file(str(md_file), db, str(vault))

    spy.assert_not_called()

# Note: Implement test_content_hash_skip in your test_indexer.py. The skeleton's
# index_file function should check content_hash before calling upsert_node — see
# the hash-skip step in the index_file HOW section above.

def test_two_pass_edge_resolution():
    # Node A contradicts Node B. Index A before B.
    # After full full_scan_and_index(), edge from A has target_id resolved to B's UUID.
    ...

def test_backlinks():
    # After indexing A contradicts B, get_backlinks(B.id) returns [A]
    ...

def test_fts5_search():
    db = GraphDatabase(tmp_db)
    node = create(title="Fast Thinking", type="note", vault=tmp_path)
    node.tags = ["cognition"]
    db.upsert_node(node)
    results = db.search_fts("cognition")
    assert any(r.id == node.id for r in results)

def test_db_is_expendable(tmp_path):
    vault, db_path = setup_vault_with_nodes(tmp_path)
    indexer.full_scan_and_index(vault, GraphDatabase(db_path))
    results_before = GraphDatabase(db_path).search_fts("cognition")
    db_path.unlink()
    indexer.full_scan_and_index(vault, GraphDatabase(db_path))
    results_after = GraphDatabase(db_path).search_fts("cognition")
    assert {r.id for r in results_before} == {r.id for r in results_after}
```

Plus 7 vault nodes with typed edges. The `test_db_is_expendable` test is the most
important one — it proves the core architectural promise of this phase.

---

## Reflect

> **Solo:** The content hash skip means `upsert_node` is effectively idempotent for unchanged nodes. But the FTS5 virtual table must stay in sync with the `nodes` table. If you skip the upsert on hash match, when does FTS5 get updated? Is there a scenario where a hash match causes FTS5 to fall out of sync with the nodes table, and how would you detect it?

> **Group:** WAL mode and `threading.Lock` both address concurrency — but at different layers. Map out the two layers: what does WAL prevent, and what does `Lock` prevent that WAL does not? Can you construct a concrete scenario (with two specific threads doing specific operations) where WAL alone is insufficient and `Lock` is the only thing preventing corruption?
