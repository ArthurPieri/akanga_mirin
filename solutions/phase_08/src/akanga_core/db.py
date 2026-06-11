"""SQLite persistence layer for the Akanga knowledge graph.

Schema rules (Phase 2, reaffirmed in Phase 8 / BUG-01):

- The ``nodes`` table stores METADATA ONLY — id, title, type, tags, path,
  content_hash. There is NO body column: node prose lives in the Markdown
  files on disk and is re-read from there at use time (e.g. by
  :func:`akanga_core.rag.build_context`).
- The FTS5 index covers title + tags only, for the same reason.
- SEC-06: user-supplied search terms are quoted before being handed to
  FTS5 so operators (``OR``, ``NEAR``, ``*`` ...) are treated as literals.
"""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Mapping
from typing import Any

from .models import Edge, Node


def _quote_fts_query(query: str) -> str:
    """Return an FTS5 MATCH expression that treats *query* as literal terms.

    SEC-06: FTS5 interprets bare ``*``, ``OR``, ``NEAR``, ``:`` etc. as syntax.
    Wrapping each whitespace-separated term in double quotes (after stripping
    any embedded double quotes) makes every term a literal string token.
    Terms with no alphanumeric characters (e.g. a lone ``*``) would tokenize
    to an empty phrase, so they are dropped rather than quoted.
    """
    terms = [
        term.replace('"', "")
        for term in query.split()
        if any(ch.isalnum() for ch in term)
    ]
    return " ".join(f'"{term}"' for term in terms)


def _row_to_node(row: sqlite3.Row) -> Node:
    """Convert a ``nodes`` table row into a :class:`Node` dataclass."""
    return Node(
        id=row["id"],
        title=row["title"],
        type=row["type"],
        tags=json.loads(row["tags"] or "[]"),
        path=row["path"],
        content_hash=row["content_hash"] or "",
    )


class GraphDatabase:
    """Thread-safe SQLite wrapper for the Akanga knowledge graph."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.setup()

    def setup(self) -> None:
        """Create the schema (idempotent) and enable WAL mode."""
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id           TEXT PRIMARY KEY,
                    title        TEXT NOT NULL,
                    type         TEXT NOT NULL DEFAULT 'note',
                    tags         TEXT NOT NULL DEFAULT '[]',
                    path         TEXT NOT NULL UNIQUE,
                    content_hash TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS edges (
                    source_id   TEXT NOT NULL,
                    target_id   TEXT NOT NULL,
                    relation    TEXT NOT NULL DEFAULT 'links_to',
                    relation_id TEXT NOT NULL DEFAULT '',
                    UNIQUE (source_id, target_id, relation),
                    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
                CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);

                -- FTS over title + tags ONLY. Node prose is never stored in
                -- the database; it is read from disk when needed (BUG-01).
                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                    title,
                    tags,
                    content='nodes',
                    content_rowid='rowid'
                );
                CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
                    INSERT INTO nodes_fts(rowid, title, tags)
                    VALUES (new.rowid, new.title, new.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, rowid, title, tags)
                    VALUES ('delete', old.rowid, old.title, old.tags);
                END;
                CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, rowid, title, tags)
                    VALUES ('delete', old.rowid, old.title, old.tags);
                    INSERT INTO nodes_fts(rowid, title, tags)
                    VALUES (new.rowid, new.title, new.tags);
                END;
            """)
            self.conn.commit()

    # -- nodes --------------------------------------------------------------

    def upsert_node(self, node: Mapping[str, Any] | Node | Any) -> None:
        """Insert or update a node record.

        Accepts a mapping (``{"id": ..., "title": ...}``), a :class:`Node`,
        or any object exposing the node fields as attributes (such as
        :class:`~akanga_core.models.ParsedNote`). Body/prose fields are
        deliberately ignored — prose is never persisted to the database.
        """
        if isinstance(node, Mapping):
            get = node.get
        else:
            def get(key: str, default: Any = None) -> Any:
                return getattr(node, key, default)

        with self.lock:
            self.conn.execute(
                """
                INSERT INTO nodes (id, title, type, tags, path, content_hash)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title        = excluded.title,
                    type         = excluded.type,
                    tags         = excluded.tags,
                    path         = excluded.path,
                    content_hash = excluded.content_hash
                """,
                (
                    get("id"),
                    get("title", ""),
                    get("type", "note") or "note",
                    json.dumps(list(get("tags") or [])),
                    get("path", ""),
                    get("content_hash", "") or "",
                ),
            )
            self.conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        """Fetch a single node by ID, or None if it does not exist."""
        with self.lock:
            row = self.conn.execute(
                "SELECT * FROM nodes WHERE id = ?", (node_id,)
            ).fetchone()
        return _row_to_node(row) if row else None

    def get_all_nodes(self, limit: int = 100, offset: int = 0) -> list[Node]:
        """Fetch nodes with pagination, ordered by title."""
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM nodes ORDER BY title LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def delete_node(self, node_id: str) -> None:
        """Delete a node and all edges that reference it."""
        with self.lock:
            self.conn.execute("DELETE FROM edges WHERE target_id = ?", (node_id,))
            self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            self.conn.commit()

    # -- edges --------------------------------------------------------------

    def upsert_edge(
        self,
        source_id: str,
        target_id: str,
        relation: str = "links_to",
        relation_id: str = "",
    ) -> None:
        """Insert a typed edge; duplicates (same source/target/relation) are ignored."""
        with self.lock:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO edges (source_id, target_id, relation, relation_id)
                VALUES (?, ?, ?, ?)
                """,
                (source_id, target_id, relation, relation_id),
            )
            self.conn.commit()

    def get_outgoing_edges(self, node_id: str) -> list[Edge]:
        """All edges whose source is *node_id*."""
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE source_id = ?", (node_id,)
            ).fetchall()
        return [Edge(r["source_id"], r["target_id"], r["relation"], r["relation_id"])
                for r in rows]

    def get_incoming_edges(self, node_id: str) -> list[Edge]:
        """All edges whose target is *node_id*."""
        with self.lock:
            rows = self.conn.execute(
                "SELECT * FROM edges WHERE target_id = ?", (node_id,)
            ).fetchall()
        return [Edge(r["source_id"], r["target_id"], r["relation"], r["relation_id"])
                for r in rows]

    def get_neighbors(self, node_id: str) -> list[Node]:
        """Outgoing neighbor nodes of *node_id*."""
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT nodes.* FROM nodes
                JOIN edges ON nodes.id = edges.target_id
                WHERE edges.source_id = ?
                """,
                (node_id,),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def get_backlinks(self, node_id: str) -> list[Node]:
        """Incoming neighbor nodes of *node_id*."""
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT nodes.* FROM nodes
                JOIN edges ON nodes.id = edges.source_id
                WHERE edges.target_id = ?
                """,
                (node_id,),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def get_edges_from(self, node_id: str) -> list[tuple[Node, str, str]]:
        """Outgoing edges as ``(target_node, relation, relation_id)`` tuples.

        Unlike :meth:`get_neighbors`, the relation label and registry id
        travel with each neighbor — Phase 3 ego graphs and Graph RAG triples
        need them. No DISTINCT: two relations between the same pair are two
        distinct edges. (Same contract as the phase 02–07 lineage.)
        """
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT nodes.*, edges.relation, edges.relation_id FROM nodes
                JOIN edges ON nodes.id = edges.target_id
                WHERE edges.source_id = ?
                """,
                (node_id,),
            ).fetchall()
        return [
            (_row_to_node(row), row["relation"] or "", row["relation_id"] or "")
            for row in rows
        ]

    def get_edges_to(self, node_id: str) -> list[tuple[Node, str, str]]:
        """Incoming edges as ``(source_node, relation, relation_id)`` tuples.

        The returned node is the edge's SOURCE; the natural direction is
        ``node.id → node_id`` (D4: incoming edges are never inverted).
        """
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT nodes.*, edges.relation, edges.relation_id FROM nodes
                JOIN edges ON nodes.id = edges.source_id
                WHERE edges.target_id = ?
                """,
                (node_id,),
            ).fetchall()
        return [
            (_row_to_node(row), row["relation"] or "", row["relation_id"] or "")
            for row in rows
        ]

    def list_nodes(self, limit: int = 100, offset: int = 0) -> list[Node]:
        """Lineage-API alias for :meth:`get_all_nodes` (phase 02–07 name)."""
        return self.get_all_nodes(limit=limit, offset=offset)

    # -- search ---------------------------------------------------------------

    def search(self, query: str) -> list[Node]:
        """Full-text search over node titles and tags (SEC-06 hardened).

        Empty or whitespace-only queries return an empty list rather than
        erroring — callers (CLI, API, MCP) treat that as "no results".
        """
        safe_query = _quote_fts_query(query)
        if not safe_query:
            return []
        with self.lock:
            rows = self.conn.execute(
                """
                SELECT nodes.* FROM nodes
                JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
                WHERE nodes_fts MATCH ?
                ORDER BY rank
                """,
                (safe_query,),
            ).fetchall()
        return [_row_to_node(row) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()


# Backwards-compatible alias: earlier phases referred to this class as Database.
Database = GraphDatabase
