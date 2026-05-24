"""Phase 02 — GraphDatabase skeleton.

Implement the eight methods marked with NotImplementedError below.
The DB_SCHEMA constant is provided for reference — do not modify it.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any
from uuid import uuid4

# ---------------------------------------------------------------------------
# Schema reference (do not modify)
# ---------------------------------------------------------------------------

DB_SCHEMA = """
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
"""

# ---------------------------------------------------------------------------
# GraphDatabase
# ---------------------------------------------------------------------------


class GraphDatabase:
    """Thread-safe SQLite wrapper for the Akanga knowledge graph."""

    def __init__(self, db_path: str) -> None:
        """WHAT: Open a SQLite connection, enable WAL mode, and create the schema.

        WHY: WAL (Write-Ahead Logging) mode allows concurrent readers without
        blocking writers. This is essential because the watcher thread writes
        while the API or TUI reads simultaneously.

        HOW:
        1. Store `db_path` on `self`.
        2. Create a `threading.Lock()` and assign it to `self._lock`.
        3. Call `sqlite3.connect(db_path, check_same_thread=False)` and assign
           the connection to `self.conn`.
        4. Set `self.conn.row_factory = sqlite3.Row` so rows support column
           access by name.
        5. (See step 7 — PRAGMAs and schema are all applied together there.)
        6. (See step 7.)
        7. Run PRAGMAs and schema OUTSIDE the connection context manager:
           a. Acquire just self._lock (not self.conn transaction context):
                with self._lock:
                    self.conn.execute("PRAGMA journal_mode=WAL")
                    self.conn.execute("PRAGMA foreign_keys=ON")
                    self.conn.executescript(DB_SCHEMA)
           Note: executescript() issues an implicit COMMIT before running,
           which conflicts with `with self.conn:`. Run it directly on conn instead.
        """
        raise NotImplementedError(
            "sqlite3.connect with check_same_thread=False; "
            "PRAGMA journal_mode=WAL; PRAGMA foreign_keys=ON; executescript(DB_SCHEMA)"
        )

    def close(self) -> None:
        """Close the underlying SQLite connection.

        Implement this by calling `self.conn.close()`.
        Once `__init__` is done, `self.conn` is the sqlite3.Connection object.
        """
        raise NotImplementedError("self.conn.close()")

    def __enter__(self) -> "GraphDatabase":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def upsert_node(self, node: Any) -> None:
        """WHAT: Insert or replace a node row in the `nodes` table, then sync FTS5.

        WHY: Called on every file index and on every watcher event. Must be
        idempotent — upserting the same node twice should leave exactly one row.

        HOW:
        1. Accept either a Node dataclass instance or a plain dict. Read the
           fields `id`, `path`, `title`, `type`, `tags`, and `content_hash`.
           If `tags` is a list, JSON-encode it with `json.dumps`; if already a
           string, use it as-is.
        2. Inside `with self._lock, self.conn:`, execute:
             INSERT OR REPLACE INTO nodes (id, path, title, type, tags, content_hash)
             VALUES (?, ?, ?, ?, ?, ?)
        3. FTS5 content tables do not auto-update on INSERT OR REPLACE; you
           must maintain them manually:
             a. DELETE FROM nodes_fts WHERE rowid = (SELECT rowid FROM nodes WHERE id = ?)
             b. INSERT INTO nodes_fts(rowid, title, tags) SELECT rowid, title, tags
                FROM nodes WHERE id = ?
           Run both statements in the same transaction as the upsert.

        Hint: if isinstance(node, dict): use node[field]. Otherwise: use getattr(node, field).
        Example: `val = node[field] if isinstance(node, dict) else getattr(node, field)`
        """
        raise NotImplementedError(
            "INSERT OR REPLACE INTO nodes ...; then DELETE old FTS row and INSERT new one "
            "using the node's rowid. Wrap in with self._lock, self.conn:"
        )

    def delete_node(self, node_id: str) -> None:
        """WHAT: Delete a node by UUID and clean up its FTS5 entry.

        WHY: The nodes table has ON DELETE CASCADE for edges, so child edges are
        removed automatically. However, FTS5 virtual tables are NOT regular tables
        — they do not participate in CASCADE, so you must explicitly delete the
        FTS row.

        HOW:
        1. Inside `with self._lock, self.conn:`:
           a. Look up the node's `rowid`:
                SELECT rowid FROM nodes WHERE id = ?
           b. If a row exists, delete its FTS entry:
                DELETE FROM nodes_fts WHERE rowid = ?
           c. Delete the node itself:
                DELETE FROM nodes WHERE id = ?
           (Edges are removed automatically via ON DELETE CASCADE.)
        2. If the node does not exist, do nothing — do not raise.
        """
        raise NotImplementedError(
            "SELECT rowid FROM nodes WHERE id=?; DELETE FROM nodes_fts WHERE rowid=?; "
            "DELETE FROM nodes WHERE id=?. If not found, return silently."
        )

    def get_node(self, node_id: str) -> Any | None:
        """WHAT: Fetch one node by UUID and return it as a Node dataclass (or dict).

        WHY: Core lookup used by the API, TUI, indexer, and graph algorithms.
        Returning None (rather than raising) lets callers handle missing nodes
        without try/except everywhere.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT * FROM nodes WHERE id = ?
        2. Call `.fetchone()`. If the result is None, return None.
        3. Convert the `sqlite3.Row` to a Node (or dict). At minimum the return
           value must expose `.id`, `.title`, `.type`, `.path`, `.tags`,
           and `.content_hash` as attributes.
           Decode `tags` from its JSON string with `json.loads`.

        Tip: you may return a simple `types.SimpleNamespace(**dict(row))` and
        then fix up `tags` — or define a `_row_to_node` helper.
        """
        raise NotImplementedError(
            "SELECT * FROM nodes WHERE id=?; fetchone(); if None return None; "
            "else decode tags with json.loads and return a Node-like object"
        )

    def list_nodes(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """WHAT: Return a paginated list of all nodes.

        WHY: Powers the TUI node list and the API list endpoint. Pagination
        prevents loading thousands of nodes into memory at once.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT * FROM nodes LIMIT ? OFFSET ?
           with `(limit, offset)` as parameters.
        2. Call `.fetchall()` and convert each row to a Node-like object
           (same conversion as in `get_node`).
        3. Return the list.
        """
        raise NotImplementedError(
            "SELECT * FROM nodes LIMIT ? OFFSET ?; fetchall(); convert each row to Node"
        )

    def search_fts(self, query: str, limit: int = 20) -> list[Any]:
        """WHAT: Full-text search using FTS5 MATCH and return matching nodes.

        WHY: FTS5 is orders of magnitude faster than LIKE for substring searches
        across large vaults (thousands of nodes). It supports stemming and ranking.

        HOW:
        0. If `query.strip()` is empty, return [] immediately — FTS5 raises
           OperationalError on an empty MATCH string.
        1. Split `query` on whitespace into individual terms.
        2. Double-quote each term to prevent FTS5 operator injection (SEC-06):
             safe_term = '"' + term.replace('"', '') + '"'
           This turns `cognitive load` into `"cognitive" "load"` — a phrase
           search for both words independently (not as a phrase).
        3. Join the quoted terms with spaces to form the FTS5 query string.
        4. Inside `with self._lock:`, execute:
             SELECT nodes.* FROM nodes
             JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
             WHERE nodes_fts MATCH ?
             ORDER BY rank
             LIMIT ?
           with `(fts_query, limit)` as parameters.
        5. Convert and return rows as Node-like objects.

        CRITICAL: Never interpolate user input directly into the SQL string —
        always use parameterised queries (`?` placeholders).
        """
        raise NotImplementedError(
            "Split query into terms; double-quote each term to prevent FTS5 operator injection; "
            "JOIN nodes ON nodes_fts MATCH ?; ORDER BY rank LIMIT ?"
        )

    # ------------------------------------------------------------------
    # Edge operations
    # ------------------------------------------------------------------

    def upsert_edge(
        self,
        source_id: str,
        target_id: str | None = None,
        relation: str | None = None,
        relation_id: str | None = None,
    ) -> str:
        """WHAT: Insert a new edge row and return its generated UUID.

        WHY: Edges are created by the link extractor (wikilinks → edges) and
        can also be created manually via the API. Returning the id lets callers
        store or log it.

        HOW:
        1. Generate a new UUID with `str(uuid4())` and call it `edge_id`.
        2. Inside `with self._lock, self.conn:`, execute:
             INSERT INTO edges (id, source_id, target_id, relation, relation_id)
             VALUES (?, ?, ?, ?, ?)
        3. Return `edge_id`.

        Note: this method also accepts a single dict as its first argument
        (legacy calling convention used by some tests). If `source_id` is a
        dict, unpack it:
            d = source_id
            source_id = d["source_id"]
            target_id = d.get("target_id")
            relation  = d.get("relation")
            relation_id = d.get("relation_id")
        """
        raise NotImplementedError(
            "Generate edge_id = str(uuid4()); INSERT INTO edges VALUES (?, ?, ?, ?, ?); "
            "return edge_id. Also handle dict-as-first-arg calling convention."
        )

    def get_neighbors(self, node_id: str) -> list[Any]:
        """WHAT: Return all nodes that `node_id` has outgoing edges pointing TO.

        WHY: Used by the ego-graph builder and the TUI neighbors panel to show
        what a node links to.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT DISTINCT nodes.* FROM nodes
             JOIN edges ON nodes.id = edges.target_id
             WHERE edges.source_id = ?
           with `(node_id,)` as parameters.
        2. Convert and return rows as Node-like objects.
        """
        raise NotImplementedError(
            "SELECT nodes.* JOIN edges ON nodes.id = edges.target_id WHERE edges.source_id = ?"
        )

    def get_backlinks(self, node_id: str) -> list[Any]:
        """WHAT: Return all nodes that have outgoing edges pointing TO `node_id`.

        WHY: Backlinks are the reverse of neighbors — they show what other nodes
        reference this one. Essential for understanding the graph's context around
        any given node.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT DISTINCT nodes.* FROM nodes
             JOIN edges ON nodes.id = edges.source_id
             WHERE edges.target_id = ?
           with `(node_id,)` as parameters.
        2. Convert and return rows as Node-like objects.
        """
        raise NotImplementedError(
            "SELECT nodes.* JOIN edges ON nodes.id = edges.source_id WHERE edges.target_id = ?"
        )
