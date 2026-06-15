# Phase 2 — Storage and Indexing

**Estimated time: 3–4h + ~1h vault/reflect**

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
- Explain why WAL mode is required when multiple threads and processes access the same SQLite DB, and what symptom (`SQLITE_BUSY`) appears without it
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
event loop (active manager, API), and CLI commands. Without WAL, a reader that hits
the DB mid-write gets an `SQLITE_BUSY` error (`database is locked`) — not a deadlock,
but a hard failure the caller would have to catch and retry. WAL's real payoff is
**cross-process readers during writes**: a CLI command in another process can read
the last committed snapshot while the watcher writes. Within a single process,
WAL is not the whole story — compound operations are serialized by a
`threading.Lock` (see Thread Safety below).

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

The compound is the unit of protection, not the statement: "read `content_hash` →
compare → upsert if different" is one logical operation — between the read and the
upsert, another thread can write a different hash. Wrap the **entire** compound in
`with self._lock:`, not just the final write. WAL stops readers and writers from
blocking each other; it does nothing about a race your own code creates between two
of its own queries.

> Akanga node: `Thread Safety`

> → Foundation doc: `docs/foundations/python-threading.md` (Lock and compound operations section)

---

!!! warning "Security: Parameterized Queries — Never Do This"

    Every query in `db.py` must use parameterized queries. This is the single most
    important security rule in any database layer, and it is also the rule beginners
    most commonly get wrong by accident, not by intent.

    **The vulnerable pattern (never write this — illustrative example):**

    ```python
    # WRONG — string formatting opens a SQL injection vector
    def search(self, query: str) -> list[Node]:
        cursor = self.conn.execute(
            f"SELECT * FROM nodes_fts WHERE nodes_fts MATCH '{query}'"
        )
        return [self._row_to_node(row) for row in cursor.fetchall()]
    ```

    If `query` is `' OR 1=1 --`, this executes as:

    ```sql
    SELECT * FROM nodes_fts WHERE nodes_fts MATCH '' OR 1=1 --'
    ```

    which bypasses the search entirely and returns every row. Against a personal
    knowledge graph this is not a network attack — but the same mistake in any
    boundary-facing code (API query parameters, filenames, tag filters) produces a
    real vulnerability. The habit must be built here.

    **The safe pattern (always do this — illustrative example; the real method is `search_fts`):**

    ```python
    # CORRECT — ? placeholder, value passed as a tuple
    def search(self, query: str) -> list[Node]:
        cursor = self.conn.execute(
            "SELECT * FROM nodes_fts WHERE nodes_fts MATCH ?",
            (query,)          # <-- the comma makes this a tuple, not a string
        )
        return [self._row_to_node(row) for row in cursor.fetchall()]
    ```

    The SQLite driver sends the query string and the values to the database engine
    separately. The engine never concatenates them — it cannot misinterpret the value
    as SQL syntax regardless of what it contains.

    **Three real examples from Akanga's own queries:**

    ```python
    # Node lookup by UUID
    cursor = self.conn.execute(
        "SELECT * FROM nodes WHERE id = ?",
        (node_id,)
    )

    # Tag filter (pass a LIKE pattern, not raw input)
    tag_pattern = f"%{tag}%"
    cursor = self.conn.execute(
        "SELECT * FROM nodes WHERE tags LIKE ?",
        (tag_pattern,)
    )

    # Edge lookup
    cursor = self.conn.execute(
        "SELECT * FROM edges WHERE source_id = ? AND relation_id = ?",
        (source_id, relation_id)
    )
    ```

    **Why this also prevents logic errors (beyond security):**

    A misplaced comma or quote in a hand-formatted query string produces a syntax error
    at runtime — difficult to trace in a test failure. Parameterized queries move
    all value binding to the driver, which means the query string is a constant that
    can be read and reviewed at a glance. Linters and static analysis tools can catch
    typos in constant SQL strings; they cannot catch errors in f-strings that assemble
    SQL dynamically.

    **Common pitfall:** forgetting the trailing comma when passing a single value:
    `(node_id)` is just `node_id` in Python — a string, not a tuple. The driver
    will try to iterate it character by character and raise an error or silently
    bind the wrong value. Always write `(node_id,)`.

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
    UNIQUE (source_id, target_id, relation),
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    title,
    tags,
    content='nodes',
    content_rowid='rowid'
);
CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    new_name TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
```

!!! note "Schema boundaries"

    The `sync_queue` table was introduced conceptually in Phase 1B (where your
    functions ran against a hand-created table); here it becomes part of `DB_SCHEMA`, so
    every `GraphDatabase` carries it. The `active_results` table is added when building
    the active node manager (advanced — not covered in this phase). Fields like `author`,
    `created_at`, `updated_at`, `meta`, `url`, `external_type`, and `description` that
    you see in node frontmatter are not columns in the Phase 02 `nodes` table — they are
    stored only in the `.md` file itself and accessible by re-parsing it.

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
| `upsert_edge(source_id, target_id, relation, relation_id)` | Insert a new edge row, return its UUID — four positional arguments |
| `get_node(node_id) → Node` | Fetch by UUID |
| `list_nodes(limit=100, offset=0) → list[Node]` | Paginated list of all nodes |
| `get_neighbors(node_id) → list[Node]` | Outgoing edges → target nodes |
| `get_backlinks(node_id) → list[Node]` | Incoming edges → source nodes |
| `get_edges_from(node_id) → list[tuple[Node, str, str]]` | Outgoing edges as `(target_node, relation, relation_id)` triples |
| `get_edges_to(node_id) → list[tuple[Node, str, str]]` | Incoming edges as `(source_node, relation, relation_id)` triples |
| `search_fts(query, limit=20) → list[Node]` | FTS5 over title + tags |

Why both pairs? `get_neighbors`/`get_backlinks` return bare nodes — enough to
answer "what is connected to X?". But Phase 3's ego-graph builder must *label*
every edge it renders ("A —contradicts→ B"), and a bare node list has thrown that
information away. `get_edges_from`/`get_edges_to` return the relation alongside
each node so Phase 3 never has to re-query the `edges` table.

**`indexer.py`** — module-level functions (no class):

| Function | What it does |
|---|---|
| `scan_vault(vault_path) → Iterator[str]` | Yield every indexable `.md` path; skips hidden directories (e.g. `.git/`) and non-`.md` files |
| `index_file(path, db, vault_path) → Node` | Parse + upsert one file — used by the file watcher in Phase 4; skips the upsert when the stored `content_hash` is unchanged |
| `full_scan_and_index(vault_path, db) → int` | Full two-pass scan: pass 1 upserts all nodes, pass 2 resolves and upserts all edges; returns the count of nodes indexed |

---

## Common Pitfalls

**FTS5 operator injection.** FTS5 MATCH queries accept operators (`AND`, `OR`, `NOT`, `*`) directly in the query string. A user who searches for `fast*` or `cognition OR memory` gets a different query than expected — and a user who types a malformed FTS5 expression triggers a SQLite error. Mitigation: always use parameterized queries (never string-format the term into SQL), AND quote the term using FTS5's `"..."` literal syntax so it is treated as a phrase, not an operator expression. Example: `WHERE nodes_fts MATCH ?` with the parameter `'"cognition"'` (double-quoted inside the FTS5 string).

**Thread safety: lock the whole compound.** See the Thread Safety concept above — the read-check-write sequence is the unit `with self._lock:` must wrap, not the final write alone.

**Derived index: never store prose body in the DB.** The DB is rebuilt from files on `akanga index`. If you store prose content in the DB, you have two sources of truth that can diverge — and rebuild becomes lossy if the DB row has content that the file doesn't. FTS5 covers `title` and `tags` only. Body search lives at the filesystem level (ripgrep). This is not a performance choice — it is an architectural constraint that keeps the DB expendable.

---

## Deliverable

Passing the Phase 2 suite: `make test PHASE=2` runs `tests/phase_02/`. These are
the tests, by name:

**`test_db.py` — GraphDatabase:**

- `test_upsert_and_get_node` — upsert then `get_node` returns matching `id`, `title`, `type`
- `test_upsert_is_idempotent` — upserting the same node twice leaves exactly one row
- `test_upsert_updates_existing` — upserting a changed title overwrites the old one
- `test_delete_node` — after delete, `get_node` returns `None`
- `test_list_nodes` / `test_list_nodes_limit_offset` — listing and pagination
- `test_search_fts_basic` — a node titled "Cognitive Load" matches the query `cognitive`
- `test_search_fts_no_operator_injection` — operator-like input (`* OR title:*`) must not raise (SEC-06: quote the term)
- `test_search_fts_operator_treated_as_literal` — SEC-06 semantics: a query containing `OR` matches it as a literal word, not as the FTS5 operator
- `test_search_fts_embedded_double_quote_does_not_raise` — SEC-06 semantics: a term containing `"` survives the double-quote wrapping without a syntax error
- `test_upsert_edge_and_get_neighbors` — after edge A→B, `get_neighbors(A.id)` includes B
- `test_get_backlinks` — after edge A→B, `get_backlinks(B.id)` includes A
- `test_get_edges_from` — outgoing edges come back as `(target_node, relation, relation_id)` triples
- `test_get_edges_to` — incoming edges come back as `(source_node, relation, relation_id)` triples
- `test_delete_node_removes_edges` — deleting the source cascades to its outgoing edges
- `test_wal_mode` — `PRAGMA journal_mode` is `wal` after `__init__`
- `test_get_node_not_found` / `test_delete_nonexistent_node` — missing ids return `None` / no-op, never raise
- `test_write_failure_propagates_sqlite_error` — reads still work on a read-only DB file; writes raise `sqlite3.Error`

**`test_indexer.py` — indexer:**

- `test_index_single_file` — `index_file` parses one `.md` and upserts the node
- `test_full_scan_indexes_all_files` — every `.md` in the vault lands in the DB
- `test_full_scan_skips_hidden_dirs` — files under `.git/` etc. are not indexed
- `test_full_scan_skips_non_md_files` — a stray `.txt` is silently skipped
- `test_full_scan_returns_count` — the scan returns the number of nodes indexed
- `test_reindex_updates_node` — re-indexing a changed file updates the DB row
- `test_two_pass_edge_resolution` — A links to B, A is indexed *before* B exists in the DB; after `full_scan_and_index`, the edge's `target_id` is resolved to B's UUID
- `test_db_is_expendable` — index a vault, delete the `.db` file, re-index: search results are identical
- `test_rescan_unchanged_vault_is_noop` — re-scanning an unchanged vault adds no rows (the re-index idempotency contract: scan; scan; count unchanged)
- `test_rescan_after_editing_one_file_changes_only_that_nodes_edges` — an edit re-resolves only the edited node's edges, never its neighbors'
- `test_rescan_after_deleting_file_tombstones_node` — a deleted file's node leaves the index on the next full scan
- `test_minted_uuid_is_written_back_and_stable_across_rescans` — a no-`id` file gets a UUID minted *and written back to frontmatter* at index time, so re-scans never re-mint
- `test_inline_typed_edge_folds_on_index` — a typed inline edge (`[[Target | relation]]`) in a changed file is folded into frontmatter by `write_back` during indexing, so it reaches the DB typed
- `test_index_missing_file_raises` — indexing a nonexistent path raises

**`test_links.py` — wikilinks:**

- `test_extract_wikilinks_basic` / `test_extract_wikilinks_none` — `[[Title]]` extraction
- `test_extract_wikilinks_skips_inline_edges` — `[[Target | relation]]` never yields the raw piped string
- `test_resolve_wikilink_found` / `test_resolve_wikilink_case_insensitive` / `test_resolve_wikilink_not_found` — title → UUID resolution against the DB

The two most important tests are `test_db_is_expendable` — it proves the core
architectural promise of this phase — and `test_two_pass_edge_resolution` — it
proves your indexer actually builds the graph, not just a node list. Illustrative
sketch of the first (the real suite is `tests/phase_02/`):

```python
def test_db_is_expendable(tmp_path):
    vault, db_path = setup_vault_with_nodes(tmp_path)
    indexer.full_scan_and_index(str(vault), GraphDatabase(str(db_path)))
    results_before = GraphDatabase(str(db_path)).search_fts("cognition")
    db_path.unlink()
    indexer.full_scan_and_index(str(vault), GraphDatabase(str(db_path)))
    results_after = GraphDatabase(str(db_path)).search_fts("cognition")
    assert {r.id for r in results_before} == {r.id for r in results_after}
```

**Optional self-written test:** the content-hash skip in `index_file` (return
early without calling `upsert_node` when the stored hash matches) is not covered
by the shipped suite. Write `test_content_hash_skip` yourself with
`mocker.spy(db, "upsert_node")`: index the same unchanged file twice and assert
the spy is not called on the second pass.

Plus 7 vault nodes with typed edges.

---

## Reflect

> **Break it on purpose:** Delete the `threading.Lock` from your `Database`.
> Predict which test fails. Run the suite. **None do.** Explain why — what would
> a test have to *do* to catch a missing lock? Then construct the concrete
> two-thread scenario (two specific threads, two specific operations) where the
> missing Lock corrupts data even with WAL on, and write that limit of the test
> suite into your `Thread Safety` vault node. Restore the Lock.

> **Solo:** The content hash skip means `upsert_node` is effectively idempotent for unchanged nodes. But the FTS5 virtual table must stay in sync with the `nodes` table. If you skip the upsert on hash match, when does FTS5 get updated? Is there a scenario where a hash match causes FTS5 to fall out of sync with the nodes table, and how would you detect it?

> **Group:** WAL mode and `threading.Lock` both address concurrency — but at different layers. Map out the two layers: what does WAL prevent, and what does `Lock` prevent that WAL does not? Can you construct a concrete scenario (with two specific threads doing specific operations) where WAL alone is insufficient and `Lock` is the only thing preventing corruption?

---

> **Fast path:** Phase 6 (REST API) depends only on phases 0–2 — if you want a
> usable API before committing to the TUI, do 0 → 1 → 2 → 6 and come back for
> 3–5 afterwards. Nothing in phases 3–5 is a prerequisite for a working server.
