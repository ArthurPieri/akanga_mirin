"""Phase 02 — GraphDatabase: the expendable, derived SQLite index.

The DB is NOT the source of truth — every row is reconstructible from
the `.md` files (`akanga index` rebuilds it identically). It exists only
to make reads fast: node lookup by UUID, adjacency-list edge queries,
and FTS5 full-text search over title + tags (never the prose body).

Concurrency model, in two layers:

- WAL mode lets cross-process readers see the last committed snapshot
  while a writer appends — no `SQLITE_BUSY` storms.
- A `threading.Lock` serializes each COMPOUND operation (read-check-write
  sequences like the FTS5 delete/insert dance in `upsert_node`), which
  WAL alone cannot make atomic at the application level.

One connection is shared across threads (`check_same_thread=False`);
the lock guarantees only one thread touches it at a time.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import types
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
CREATE TABLE IF NOT EXISTS sync_queue (
    id TEXT PRIMARY KEY,
    entity_id TEXT NOT NULL,
    new_name TEXT NOT NULL,
    processed INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

# Node fields persisted in the `nodes` table, in column order.
_NODE_FIELDS = ("id", "path", "title", "type", "tags", "content_hash")


def _row_to_node(row: sqlite3.Row) -> types.SimpleNamespace:
    """Convert a `nodes` row to an attribute-access object with tags decoded.

    Downstream callers (Phase 6 server, Phase 8 RAG) use attribute access
    (`node.id`, `node.title`), so a plain dict is not acceptable here.
    """
    node = types.SimpleNamespace(**dict(row))
    node.tags = json.loads(node.tags)
    return node


class GraphDatabase:
    """Thread-safe SQLite wrapper for the Akanga knowledge graph.

    Errors from SQLite (`sqlite3.Error`) PROPAGATE to the caller — the
    indexer or watcher handler decides how to log/retry. Swallowing them
    here would silently hide data loss.
    """

    def __init__(self, db_path: str) -> None:
        """Open the connection, enable WAL + foreign keys, create the schema.

        `executescript` issues an implicit COMMIT before running, which
        conflicts with the connection's own transaction context manager —
        so PRAGMAs and schema run under just the lock, not `with self.conn:`.
        """
        self.db_path = db_path
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        with self._lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript(DB_SCHEMA)

    def close(self) -> None:
        """Close the underlying SQLite connection."""
        self.conn.close()

    def __enter__(self) -> GraphDatabase:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------

    def upsert_node(self, node: Any) -> None:
        """Insert or replace a node row, keeping the FTS5 index in sync.

        Idempotent: upserting the same node twice leaves exactly one row.
        Accepts a Node dataclass or a plain dict.

        FTS5 external-content maintenance must happen in the SAME locked
        transaction as the upsert: the 'delete' command needs the OLD
        title/tags values (an external-content table cannot know which
        tokens to remove otherwise), and INSERT OR REPLACE assigns a NEW
        rowid, so the fresh tokens are inserted against the new rowid.
        """
        def _field(name: str) -> Any:
            return node[name] if isinstance(node, dict) else getattr(node, name)

        values = {name: _field(name) for name in _NODE_FIELDS}
        if not isinstance(values["tags"], str):
            values["tags"] = json.dumps(list(values["tags"]))

        with self._lock, self.conn:
            old = self.conn.execute(
                "SELECT rowid, title, tags FROM nodes WHERE id = ?", (values["id"],)
            ).fetchone()
            self.conn.execute(
                "INSERT OR REPLACE INTO nodes (id, path, title, type, tags, content_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                tuple(values[name] for name in _NODE_FIELDS),
            )
            if old is not None:
                self.conn.execute(
                    "INSERT INTO nodes_fts(nodes_fts, rowid, title, tags) "
                    "VALUES('delete', ?, ?, ?)",
                    (old["rowid"], old["title"], old["tags"]),
                )
            new_rowid = self.conn.execute(
                "SELECT rowid FROM nodes WHERE id = ?", (values["id"],)
            ).fetchone()[0]
            self.conn.execute(
                "INSERT INTO nodes_fts(rowid, title, tags) VALUES(?, ?, ?)",
                (new_rowid, values["title"], values["tags"]),
            )

    def delete_node(self, node_id: str) -> None:
        """Delete a node by UUID, its FTS5 entry, and ALL touching edges.

        Outgoing edges are removed by `ON DELETE CASCADE`; incoming edges
        (where this node is the target) and the FTS5 virtual-table row do
        not participate in CASCADE, so both are cleaned up explicitly.
        Deleting a non-existent id is a silent no-op.
        """
        with self._lock, self.conn:
            old = self.conn.execute(
                "SELECT rowid, title, tags FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
            if old is None:
                return  # nothing to delete
            self.conn.execute(
                "INSERT INTO nodes_fts(nodes_fts, rowid, title, tags) "
                "VALUES('delete', ?, ?, ?)",
                (old["rowid"], old["title"], old["tags"]),
            )
            self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            # CASCADE handles source_id = node_id; do it explicitly as well so
            # the graph stays consistent even on connections without the
            # foreign_keys pragma (e.g. external inspection tools).
            self.conn.execute("DELETE FROM edges WHERE source_id = ?", (node_id,))
            self.conn.execute("DELETE FROM edges WHERE target_id = ?", (node_id,))

    def get_node(self, node_id: str) -> Any | None:
        """Fetch one node by UUID; return None (never raise) when missing."""
        with self._lock:
            row = self.conn.execute(
                "SELECT * FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
        return None if row is None else _row_to_node(row)

    def list_nodes(self, limit: int = 100, offset: int = 0) -> list[Any]:
        """Return a paginated list of all nodes (insertion-rowid order)."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT * FROM nodes ORDER BY rowid LIMIT ? OFFSET ?", (limit, offset)
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def search_fts(self, query: str, limit: int = 20) -> list[Any]:
        """Full-text search over title + tags via FTS5 MATCH.

        SEC-06: each whitespace-separated term is wrapped in FTS5 `"..."`
        literal quotes (after stripping any embedded double quotes) so
        operators like `OR`, `NOT`, `*`, or `title:` are searched as
        literal text instead of being interpreted — and malformed operator
        expressions can no longer raise. The query string itself is bound
        with a `?` placeholder, never interpolated.
        """
        terms = [term.replace('"', "") for term in query.split()]
        quoted = [f'"{term}"' for term in terms if term]
        if not quoted:
            return []  # FTS5 raises OperationalError on an empty MATCH string
        fts_query = " ".join(quoted)

        with self._lock:
            rows = self.conn.execute(
                "SELECT nodes.* FROM nodes "
                "JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid "
                "WHERE nodes_fts MATCH ? "
                "ORDER BY nodes_fts.rank "
                "LIMIT ?",
                (fts_query, limit),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

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
        """Insert a new edge row and return its generated UUID."""
        edge_id = str(uuid4())
        with self._lock, self.conn:
            self.conn.execute(
                "INSERT INTO edges (id, source_id, target_id, relation, relation_id) "
                "VALUES (?, ?, ?, ?, ?)",
                (edge_id, source_id, target_id, relation, relation_id),
            )
        return edge_id

    def get_neighbors(self, node_id: str) -> list[Any]:
        """Return the nodes that `node_id` has outgoing edges pointing TO."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT DISTINCT nodes.* FROM nodes "
                "JOIN edges ON nodes.id = edges.target_id "
                "WHERE edges.source_id = ?",
                (node_id,),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def get_backlinks(self, node_id: str) -> list[Any]:
        """Return the nodes that have outgoing edges pointing TO `node_id`."""
        with self._lock:
            rows = self.conn.execute(
                "SELECT DISTINCT nodes.* FROM nodes "
                "JOIN edges ON nodes.id = edges.source_id "
                "WHERE edges.target_id = ?",
                (node_id,),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def get_edges_from(self, node_id: str) -> list[Any]:
        """Outgoing edges as `(target_node, relation, relation_id)` tuples.

        Unlike `get_neighbors`, the relation label and registry id travel
        with each neighbor — Phase 3 ego graphs and Phase 8 RAG triples
        need them (a bare node list forces `relation=""` downstream and
        guts the 71-type vocabulary). No DISTINCT: two different relations
        between the same pair are two distinct edges.
        """
        with self._lock:
            rows = self.conn.execute(
                "SELECT nodes.*, edges.relation, edges.relation_id "
                "FROM nodes "
                "JOIN edges ON nodes.id = edges.target_id "
                "WHERE edges.source_id = ?",
                (node_id,),
            ).fetchall()
        return [self._row_to_edge_tuple(row) for row in rows]

    def get_edges_to(self, node_id: str) -> list[Any]:
        """Incoming edges as `(source_node, relation, relation_id)` tuples.

        The returned node is the edge's SOURCE; the edge's natural
        direction is `node.id → node_id`. Phase 3 records incoming edges
        in this natural direction with the real relation name instead of
        an unlabeled backlink.
        """
        with self._lock:
            rows = self.conn.execute(
                "SELECT nodes.*, edges.relation, edges.relation_id "
                "FROM nodes "
                "JOIN edges ON nodes.id = edges.source_id "
                "WHERE edges.target_id = ?",
                (node_id,),
            ).fetchall()
        return [self._row_to_edge_tuple(row) for row in rows]

    @staticmethod
    def _row_to_edge_tuple(row: sqlite3.Row) -> tuple[Any, str, str]:
        """Split a joined nodes+edges row into `(node, relation, relation_id)`.

        The node is built from the `nodes.*` columns only; NULL relation
        values are normalised to `""` so callers never branch on None.
        """
        data = dict(row)
        relation = data.pop("relation", None) or ""
        relation_id = data.pop("relation_id", None) or ""
        node = types.SimpleNamespace(**{k: data[k] for k in _NODE_FIELDS})
        node.tags = json.loads(node.tags)
        return (node, relation, relation_id)
