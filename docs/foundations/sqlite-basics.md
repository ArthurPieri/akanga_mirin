# SQLite Basics

A practical guide for Python developers working with embedded databases in a local-first tool.

---

## What is SQLite?

SQLite is an embedded relational database. "Embedded" means there is no separate server process —
the entire database engine is a library that runs inside your application, and all data lives in a
single file on disk.

This makes it a natural fit for local-first tools like Akanga:

- **Zero configuration.** No install, no service, no port, no credentials.
- **Single file.** The whole database is one `.db` file you can copy, inspect, or delete.
- **Fast for reads.** Local disk access is much faster than a network round-trip to PostgreSQL.
- **ACID transactions.** SQLite is not a toy — it provides real atomicity, consistency, isolation,
  and durability.
- **Widely supported.** The `sqlite3` module ships with Python's standard library. No extra install.

When should you use something else? When you have many concurrent writers (dozens of processes
writing simultaneously), or when your data exceeds what fits on a single machine. For a personal
knowledge graph accessed by one process, SQLite is the right tool.

---

## Basic SQL

If you have not written SQL before, here are the five statements you will use constantly.

### CREATE TABLE

Defines the schema for a table. Run once to set up the database:

```sql
CREATE TABLE IF NOT EXISTS nodes (
    id          TEXT PRIMARY KEY,
    path        TEXT UNIQUE NOT NULL,
    title       TEXT NOT NULL,
    type        TEXT NOT NULL DEFAULT 'note',
    tags        TEXT NOT NULL DEFAULT '[]',
    content_hash TEXT
);
```

`IF NOT EXISTS` makes it safe to run on every startup — no error if the table already exists.

Common column types in SQLite: `TEXT`, `INTEGER`, `REAL`, `BLOB`. SQLite uses dynamic typing, so
these are more like hints than strict constraints.

### INSERT

Adds a new row:

```sql
INSERT INTO nodes (id, path, title, type)
VALUES ('abc-123', 'my-note.md', 'My Note', 'note');
```

### SELECT

Retrieves rows:

```sql
-- All columns, all rows
SELECT * FROM nodes;

-- Specific columns
SELECT id, title, type FROM nodes;

-- With a filter
SELECT * FROM nodes WHERE type = 'active';

-- With ordering and a limit
SELECT * FROM nodes ORDER BY updated_at DESC LIMIT 10;

-- Joining two tables
SELECT n.title, e.relation
FROM nodes n
JOIN edges e ON n.id = e.source_id
WHERE n.id = 'abc-123';
```

### UPDATE

Modifies existing rows:

```sql
UPDATE nodes
SET title = 'Revised Title', updated_at = '2024-01-15T12:00:00'
WHERE id = 'abc-123';
```

### DELETE

Removes rows:

```sql
DELETE FROM nodes WHERE id = 'abc-123';

-- Delete all edges connected to a node (before deleting the node itself)
DELETE FROM edges WHERE source_id = 'abc-123' OR target_id = 'abc-123';
```

---

## `INSERT OR REPLACE` — The Upsert Pattern

Often you want to insert a row if it does not exist, or update it if it does. This is called an
upsert. SQLite supports it natively:

```sql
INSERT OR REPLACE INTO nodes (id, title, type, file_path, content_hash, updated_at)
VALUES (?, ?, ?, ?, ?, ?);
```

`INSERT OR REPLACE` works by checking the `PRIMARY KEY` (and any `UNIQUE` constraints). If a
conflict is found, it deletes the old row and inserts the new one. The result is that the row
always reflects the latest values you provided.

**Why Akanga uses it:** The indexer walks the vault and calls upsert for every `.md` file it finds.
If a node already exists in the database (same `id`), the row is updated with the current metadata
and `content_hash`. If it is new, a fresh row is inserted. One statement handles both cases — no
need for a `SELECT` first to decide whether to `INSERT` or `UPDATE`.

Alternative: `INSERT OR IGNORE` — inserts if the key is new, silently does nothing on conflict.
Useful when you never want to overwrite existing data.

---

## `PRAGMA journal_mode=WAL` — Write-Ahead Logging

SQLite's default journal mode locks the entire database file during a write. This means readers
are blocked while a write is in progress. For a single-threaded CLI tool this is fine. For a
long-running server that handles HTTP requests while a background watcher writes to the database,
it causes contention.

WAL (Write-Ahead Logging) changes the locking model:

- Writers append changes to a separate WAL file instead of modifying the main database in place.
- Readers read directly from the main database file and see a consistent snapshot — they are never
  blocked by a writer.
- Multiple readers can run concurrently with one writer.

Enable it with a `PRAGMA` statement right after opening the connection:

```python
import sqlite3

conn = sqlite3.connect("akanga.db")
conn.execute("PRAGMA journal_mode=WAL")
```

WAL mode persists in the database file — you only need to set it once, but it is safe to set on
every open. It creates two additional files alongside the `.db`: a `.db-wal` (the write-ahead log)
and a `.db-shm` (shared memory index). These are normal — they are checkpointed back into the main
file periodically. Never delete them while the database is open.

**Why Akanga uses WAL:** The FastAPI server and the watchdog file watcher both access the database
concurrently. WAL lets HTTP reads proceed while the watcher indexes changed files.

---

## FTS5 — Full-Text Search

SQLite's FTS5 extension adds full-text search capabilities. It maintains an inverted index over
one or more text columns and supports fast keyword searches with the `MATCH` operator.

### Creating an FTS5 virtual table

```sql
CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
    id UNINDEXED,
    title,
    content,
    content='nodes',     -- shadow the 'nodes' table for triggers
    content_rowid='rowid'
);
```

- `UNINDEXED` columns are stored but not tokenized (useful for IDs you want to retrieve but not
  search).
- `content='nodes'` tells FTS5 this is a "content table" — it reads the actual text from `nodes`
  but maintains its own inverted index. You must keep it in sync manually (via triggers or
  explicit inserts).

### Searching with MATCH

```sql
SELECT id, title
FROM nodes_fts
WHERE nodes_fts MATCH 'knowledge graph'
ORDER BY rank;
```

`MATCH` supports:
- Single terms: `MATCH 'python'`
- Phrase queries: `MATCH '"knowledge graph"'` (double-quoted inside the string)
- Prefix queries: `MATCH 'pyth*'`
- Boolean: `MATCH 'python AND sqlite'`

The built-in `rank` column returns a relevance score (more negative = more relevant when sorted
ascending, or use `ORDER BY rank` which SQLite sorts correctly).

### Keeping FTS5 in sync

FTS5 does not automatically mirror changes to the base table. You must update it explicitly. The
common pattern is to delete the old entry and insert the new one:

```python
cursor.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
cursor.execute(
    "INSERT INTO nodes_fts (id, title, content) VALUES (?, ?, ?)",
    (node_id, title, body_text),
)
```

Akanga's `GraphDatabase` does this inside its `upsert_node` method so the FTS index always
reflects the current vault state.

---

## The `sqlite3` Python Module

Python ships with `sqlite3` in the standard library — no install needed.

### Basic usage

```python
import sqlite3

# Open (or create) a database file
conn = sqlite3.connect("akanga.db")

# Get a cursor to execute statements
cursor = conn.cursor()

# Execute a statement
cursor.execute("SELECT * FROM nodes WHERE type = ?", ("note",))

# Fetch results
row = cursor.fetchone()   # one row as a tuple (or None)
rows = cursor.fetchall()  # all rows as a list of tuples

# Commit changes (required for INSERT/UPDATE/DELETE)
conn.commit()

# Close when done
conn.close()
```

### Context manager

Use `with conn` to auto-commit on success and auto-rollback on exception:

```python
with sqlite3.connect("akanga.db") as conn:
    conn.execute(
        "INSERT INTO nodes (id, title) VALUES (?, ?)",
        ("abc-123", "My Note"),
    )
    # Automatically committed when the block exits cleanly
    # Automatically rolled back if an exception is raised
```

Note: `with conn` manages the transaction, not the connection lifetime. The connection stays open
after the `with` block. Call `conn.close()` explicitly when you are done with it entirely.

---

## `check_same_thread=False`

By default, `sqlite3.connect()` raises an error if you use a connection from a thread other than
the one that created it:

```
ProgrammingError: SQLite objects created in a thread can only be used in that same thread.
```

This guard exists because SQLite connections are not thread-safe by default. To share one
connection across threads, pass `check_same_thread=False`:

```python
conn = sqlite3.connect("akanga.db", check_same_thread=False)
```

**This disables the guard, not the problem.** SQLite can corrupt data if two threads write
simultaneously without coordination. When you set `check_same_thread=False`, you accept
responsibility for thread safety. The correct way to handle it is with a `threading.Lock`.

---

## `threading.Lock` — The Thread-Safety Contract

A `threading.Lock` ensures only one thread executes a critical section at a time. Wrap all
database writes (and any reads that must be consistent with a write) inside the lock:

```python
import sqlite3
import threading

class GraphDatabase:
    def __init__(self, db_path: str):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()

    def upsert_node(self, node_id: str, title: str, node_type: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO nodes (id, title, type) VALUES (?, ?, ?)",
                (node_id, title, node_type),
            )
            self._conn.commit()

    def get_node(self, node_id: str) -> dict | None:
        # Reads don't strictly need the lock with WAL mode,
        # but acquiring it is safe and keeps reasoning simple.
        with self._lock:
            cursor = self._conn.execute(
                "SELECT id, title, type FROM nodes WHERE id = ?",
                (node_id,),
            )
            row = cursor.fetchone()
            return {"id": row[0], "title": row[1], "type": row[2]} if row else None
```

WAL mode allows concurrent readers without locking, but Python's `sqlite3` module shares one
connection object — so all access through that object is still serialized through the lock anyway.
The lock prevents one thread from starting a write while another is mid-read on the same cursor.

---

## Row Factory: Access Columns by Name

By default, `sqlite3` returns rows as plain tuples. Indexing by position (`row[0]`, `row[2]`) is
fragile — add a column and every index shifts. The row factory lets you access columns by name:

```python
import sqlite3

conn = sqlite3.connect("akanga.db")
conn.row_factory = sqlite3.Row   # set this once after opening

cursor = conn.execute("SELECT id, title, type FROM nodes WHERE id = ?", ("abc-123",))
row = cursor.fetchone()

if row:
    print(row["id"])     # "abc-123"
    print(row["title"])  # "My Note"
    print(row["type"])   # "note"

    # Still iterable like a tuple
    print(dict(row))     # {'id': 'abc-123', 'title': 'My Note', 'type': 'note'}
```

`sqlite3.Row` is lightweight — it does not copy the data, it just wraps the raw row with a
name-lookup layer. Akanga's `GraphDatabase` sets this on the connection during `__init__`.

---

## Parameterized Queries — Never Use f-strings in SQL

**Always** use `?` placeholders and pass values as a tuple. **Never** build SQL strings with
f-strings or string concatenation.

```python
# CORRECT — parameterized query
node_id = "abc-123"
cursor.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))

# ALSO CORRECT — multiple parameters
cursor.execute(
    "INSERT INTO nodes (id, title, type) VALUES (?, ?, ?)",
    (node_id, "My Note", "note"),
)

# WRONG — SQL injection vulnerability
# If node_id is "'; DROP TABLE nodes; --", this destroys the database
cursor.execute(f"SELECT * FROM nodes WHERE id = '{node_id}'")   # NEVER DO THIS

# ALSO WRONG — same problem with concatenation
cursor.execute("SELECT * FROM nodes WHERE id = '" + node_id + "'")   # NEVER DO THIS
```

Why it matters: SQL injection is not just a web application problem. Even a local tool can be
attacked if it processes untrusted input (filenames from the filesystem, user-supplied search
queries, node titles from vault files). The `?` placeholder tells the database driver to treat
the value as data, never as SQL syntax. The driver handles escaping automatically.

Named placeholders (`:name` syntax) are also supported and can be clearer for many parameters:

```python
cursor.execute(
    "INSERT INTO nodes (id, title, type) VALUES (:id, :title, :type)",
    {"id": node_id, "title": "My Note", "type": "note"},
)
```

---

## Putting It Together: A Minimal GraphDatabase

Here is a simplified version of the pattern Akanga uses, combining all the concepts above:

```python
import sqlite3
import threading

class GraphDatabase:
    def __init__(self, db_path: str) -> None:
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript("""
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS nodes (
                    id           TEXT PRIMARY KEY,
                    title        TEXT NOT NULL,
                    type         TEXT NOT NULL DEFAULT 'note',
                    file_path    TEXT UNIQUE NOT NULL,
                    content_hash TEXT,
                    updated_at   TEXT
                );

                CREATE TABLE IF NOT EXISTS edges (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_id TEXT NOT NULL,
                    target_id TEXT NOT NULL,
                    relation  TEXT NOT NULL DEFAULT 'wikilink',
                    FOREIGN KEY (source_id) REFERENCES nodes(id),
                    FOREIGN KEY (target_id) REFERENCES nodes(id)
                );

                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                    id UNINDEXED,
                    title,
                    content
                );
            """)
            self._conn.commit()

    def upsert_node(self, id: str, title: str, type: str,
                    file_path: str, content_hash: str, body: str) -> None:
        with self._lock:
            self._conn.execute(
                """INSERT OR REPLACE INTO nodes (id, title, type, file_path, content_hash)
                   VALUES (?, ?, ?, ?, ?)""",
                (id, title, type, file_path, content_hash),
            )
            # Keep FTS in sync
            self._conn.execute("DELETE FROM nodes_fts WHERE id = ?", (id,))
            self._conn.execute(
                "INSERT INTO nodes_fts (id, title, content) VALUES (?, ?, ?)",
                (id, title, body),
            )
            self._conn.commit()

    def search(self, query: str) -> list[dict]:
        with self._lock:
            cursor = self._conn.execute(
                """SELECT n.id, n.title, n.type
                   FROM nodes n
                   JOIN nodes_fts f ON n.id = f.id
                   WHERE nodes_fts MATCH ?
                   ORDER BY rank""",
                (query,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def delete_node(self, node_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM edges WHERE source_id = ? OR target_id = ?",
                               (node_id, node_id))
            self._conn.execute("DELETE FROM nodes_fts WHERE id = ?", (node_id,))
            self._conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            self._conn.commit()

    def close(self) -> None:
        self._conn.close()
```

---

## In This Codebase

- **`src/akanga_core/db.py`** — `GraphDatabase` implements all of the above. WAL mode and
  `threading.Lock` are set up in `__init__`. All public methods acquire `self._lock` before
  touching the connection. `row_factory = sqlite3.Row` is set so callers get name-addressable
  rows. FTS5 sync happens inside `upsert_node` and `delete_node`.

- **WAL + Lock is the thread-safety contract.** The FastAPI server runs in an asyncio event loop
  with a thread pool for blocking DB calls. The watchdog watcher runs in a separate thread.
  Both share one `GraphDatabase` instance. The lock serializes all access; WAL ensures readers
  are never blocked by writers at the SQLite level.

- **Parameterized queries everywhere.** Search queries, node titles, and file paths all come from
  user-controlled data. The codebase never interpolates values into SQL strings.

---

## Quick Reference

| Concept | Code |
|---|---|
| Open database | `sqlite3.connect("file.db", check_same_thread=False)` |
| Enable WAL | `conn.execute("PRAGMA journal_mode=WAL")` |
| Enable name access | `conn.row_factory = sqlite3.Row` |
| Execute statement | `conn.execute("SQL", (param1, param2))` |
| Fetch one row | `cursor.fetchone()` |
| Fetch all rows | `cursor.fetchall()` |
| Commit | `conn.commit()` |
| Upsert | `INSERT OR REPLACE INTO ...` |
| FTS search | `WHERE table MATCH ?` |
| Thread-safe write | `with self._lock: conn.execute(...); conn.commit()` |
| Row to dict | `dict(row)` |
| Close connection | `conn.close()` |
