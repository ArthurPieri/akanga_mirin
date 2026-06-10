"""Phase 02 — GraphDatabase skeleton.

Implement every method marked with NotImplementedError below.
The DB_SCHEMA constant is provided for reference — do not modify it.
"""
from __future__ import annotations

from typing import Any

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
CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    new_name TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
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
           Hint: `val = node[field] if isinstance(node, dict) else getattr(node, field)`
        2. Inside `with self._lock, self.conn:`, fetch the old row BEFORE the
           upsert. The OLD title and tags values are required for the FTS5
           'delete' command in step 4 (external-content FTS5 cannot determine
           which tokens to remove without them):
             old = conn.execute("SELECT rowid, title, tags FROM nodes WHERE id = ?", (node_id,)).fetchone()
        3. Run the upsert:
             INSERT OR REPLACE INTO nodes (id, path, title, type, tags, content_hash)
             VALUES (?, ?, ?, ?, ?, ?)
        4. FTS5 external-content maintenance (MUST run inside the same with self._lock, self.conn: block):
           a. Before upsert — fetch old row (id AND content for FTS 'delete'):
                old = conn.execute("SELECT rowid, title, tags FROM nodes WHERE id = ?", (node_id,)).fetchone()
           b. Run the INSERT OR REPLACE on nodes (step 3)
           c. If old row existed — remove old FTS tokens using 'delete' command:
                conn.execute(
                    "INSERT INTO nodes_fts(nodes_fts, rowid, title, tags) VALUES('delete', ?, ?, ?)",
                    (old["rowid"], old["title"], old["tags"])
                )
           d. Fetch the new rowid (it changed because INSERT OR REPLACE assigned a new one):
                new_rowid = conn.execute("SELECT rowid FROM nodes WHERE id = ?", (node_id,)).fetchone()[0]
           e. Insert new FTS tokens:
                conn.execute(
                    "INSERT INTO nodes_fts(rowid, title, tags) VALUES(?, ?, ?)",
                    (new_rowid, title, tags_json)
                )
           Note: 'delete' requires ORIGINAL content values. Using the wrong values corrupts the index.
           All steps a–e must be inside the same with self._lock, self.conn: transaction.
        """
        raise NotImplementedError(
            "SELECT old rowid+title+tags; INSERT OR REPLACE INTO nodes ...; "
            "if old existed, FTS5 'delete' command with OLD title/tags; "
            "then INSERT new FTS row with new rowid. Wrap in with self._lock, self.conn:"
        )

    def delete_node(self, node_id: str) -> None:
        """WHAT: Delete a node by UUID and clean up its FTS5 entry.

        WHY: The nodes table has ON DELETE CASCADE for edges, so child edges are
        removed automatically. However, FTS5 virtual tables are NOT regular tables
        — they do not participate in CASCADE, so you must explicitly delete the
        FTS row.

        HOW:
        1. Inside with self._lock, self.conn::
           a. Fetch the row (need rowid AND content for FTS 'delete'):
                old = conn.execute("SELECT rowid, title, tags FROM nodes WHERE id = ?", (node_id,)).fetchone()
           b. If old row does not exist, return silently (nothing to delete).
           c. Remove FTS tokens using 'delete' command:
                conn.execute(
                    "INSERT INTO nodes_fts(nodes_fts, rowid, title, tags) VALUES('delete', ?, ?, ?)",
                    (old["rowid"], old["title"], old["tags"])
                )
           d. Delete the node row (CASCADE removes outgoing edges — edges where source_id = node_id):
                conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
           e. WARNING: Edges where target_id = node_id (backlinks) are NOT cascade-deleted.
              Explicitly clean them up:
                conn.execute("DELETE FROM edges WHERE target_id = ?", (node_id,))
        """
        raise NotImplementedError(
            "SELECT rowid+title+tags FROM nodes WHERE id=?; if missing return; "
            "FTS5 'delete' command with OLD title/tags; DELETE FROM nodes WHERE id=?; "
            "DELETE FROM edges WHERE target_id=? to clean backlinks."
        )

    def get_node(self, node_id: str) -> Any | None:
        """WHAT: Fetch one node by UUID and return it as a SimpleNamespace.

        WHY: Core lookup used by the API, TUI, indexer, and graph algorithms.
        Returning None (rather than raising) lets callers handle missing nodes
        without try/except everywhere.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT * FROM nodes WHERE id = ?
        2. Call `.fetchone()`. If the result is None, return None.
        3. Convert the `sqlite3.Row` to a SimpleNamespace with tags decoded:
             ns = types.SimpleNamespace(**dict(row))
             ns.tags = json.loads(ns.tags)
             return ns

        Tip: use `types.SimpleNamespace(**dict(row))` and decode tags with
        `json.loads`. This gives attribute access (node.id, node.title, etc.)
        which all downstream callers (Phase 06 server, Phase 08 RAG) use.
        Do NOT return a plain dict — callers use attribute access.
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
        2. Double-quote each term to prevent FTS5 operator injection (SEC-06).
           FTS5 operators like `NEAR` or `NOT` can be injected if user input
           is not escaped. Wrapping each term in double quotes ensures they
           are treated as literal text:
             safe_term = '"' + term.replace('"', '') + '"'
           This turns `cognitive load` into `"cognitive" "load"`.
        3. Join the quoted terms with spaces to form the FTS5 query string.
        4. Inside `with self._lock:`, execute:
             SELECT nodes.* FROM nodes
             JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
             WHERE nodes_fts MATCH ?
             ORDER BY nodes_fts.rank
             LIMIT ?
           with `(fts_query, limit)` as parameters.
           Note: qualify `rank` as `nodes_fts.rank` — the FTS5 rank column is
           ambiguous in some SQLite versions when used in a JOIN, and an
           unqualified `rank` may not sort by relevance.
        5. Convert and return rows as Node-like objects.

        CRITICAL: Never interpolate user input directly into the SQL string —
        always use parameterised queries (`?` placeholders).
        """
        raise NotImplementedError(
            "Split query into terms; explicitly wrap each term in double-quotes to prevent "
            "FTS5 operator injection; JOIN nodes ON nodes_fts MATCH ?; "
            "ORDER BY nodes_fts.rank LIMIT ?"
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

        Callers always pass the positional/keyword arguments shown in the
        signature — there is no dict-based calling convention.
        """
        raise NotImplementedError(
            "Generate edge_id = str(uuid4()); INSERT INTO edges VALUES (?, ?, ?, ?, ?); "
            "return edge_id."
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

    def get_edges_from(self, node_id: str) -> list[Any]:
        """WHAT: Return all outgoing edges of `node_id` as
        `(target_node, relation, relation_id)` tuples.

        WHY: `get_neighbors` returns only the neighbor *nodes* — the relation
        label is lost. That loss is what forced earlier designs to build
        ego-graphs with `relation=""`, which degraded every Phase 8 RAG triple
        to a meaningless `relates_to`. This method keeps the edge's relation
        name and stable vocabulary ID attached to each neighbor, so Phase 3's
        `build_ego_graph` (and ultimately the LLM context in Phase 8) gets the
        full 71-type relation vocabulary for free.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT nodes.*, edges.relation, edges.relation_id
             FROM nodes
             JOIN edges ON nodes.id = edges.target_id
             WHERE edges.source_id = ?
           with `(node_id,)` as parameters.
           (No DISTINCT — two different relations between the same pair are
           two distinct edges and must both be returned.)
        2. For each row, build the target node exactly as in `get_node`
           (SimpleNamespace, tags decoded with `json.loads`) from the
           `nodes.*` columns, and pull `relation` / `relation_id` from the
           edge columns. Normalise NULL to `""`:
             relation = row["relation"] or ""
             relation_id = row["relation_id"] or ""
        3. Return `[(node, relation, relation_id), ...]` — a list of 3-tuples.

        Returns:
            list of (Node-like, relation: str, relation_id: str) tuples for
            every edge where `node_id` is the source.
        """
        raise NotImplementedError(
            "SELECT nodes.*, edges.relation, edges.relation_id FROM nodes "
            "JOIN edges ON nodes.id = edges.target_id WHERE edges.source_id = ?; "
            "return [(node, relation or '', relation_id or ''), ...]"
        )

    def get_edges_to(self, node_id: str) -> list[Any]:
        """WHAT: Return all incoming edges of `node_id` as
        `(source_node, relation, relation_id)` tuples.

        WHY: The incoming counterpart of `get_edges_from` — backlinks with
        their relation labels intact. Phase 3's ego-graph builder needs this
        to record incoming edges in their NATURAL direction (source → target
        as stored in the DB) with the real relation name, instead of an
        unlabeled backlink.

        HOW:
        1. Inside `with self._lock:`, execute:
             SELECT nodes.*, edges.relation, edges.relation_id
             FROM nodes
             JOIN edges ON nodes.id = edges.source_id
             WHERE edges.target_id = ?
           with `(node_id,)` as parameters.
           (No DISTINCT — see get_edges_from.)
        2. Build each source node as in `get_node`; normalise NULL
           relation/relation_id to `""` (same as get_edges_from step 2).
        3. Return `[(node, relation, relation_id), ...]` — a list of 3-tuples.
           Note: the returned node is the edge's SOURCE; `node_id` is the
           target. The edge's natural direction is `node.id → node_id`.

        Returns:
            list of (Node-like, relation: str, relation_id: str) tuples for
            every edge where `node_id` is the target.
        """
        raise NotImplementedError(
            "SELECT nodes.*, edges.relation, edges.relation_id FROM nodes "
            "JOIN edges ON nodes.id = edges.source_id WHERE edges.target_id = ?; "
            "return [(node, relation or '', relation_id or ''), ...]"
        )
