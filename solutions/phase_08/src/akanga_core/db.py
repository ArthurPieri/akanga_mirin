from __future__ import annotations

import json
import sqlite3
import threading
from typing import Any

from .models import Node


class Database:
    """Thread-safe SQLite wrapper for the Akanga knowledge graph."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self.lock = threading.Lock()
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.setup()

    def setup(self) -> None:
        """Initialize the database schema and enable WAL mode."""
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.executescript("""
                CREATE TABLE IF NOT EXISTS nodes (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    path TEXT NOT NULL UNIQUE,
                    body TEXT,
                    frontmatter TEXT
                );
                CREATE TABLE IF NOT EXISTS edges (
                    source TEXT NOT NULL,
                    target TEXT NOT NULL,
                    relation TEXT,
                    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE
                );
                CREATE VIRTUAL TABLE IF NOT EXISTS nodes_fts USING fts5(
                    title,
                    body,
                    content='nodes',
                    content_rowid='rowid'
                );

                -- Triggers to keep FTS5 index in sync with the nodes table
                CREATE TRIGGER IF NOT EXISTS nodes_ai AFTER INSERT ON nodes BEGIN
                    INSERT INTO nodes_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
                END;
                CREATE TRIGGER IF NOT EXISTS nodes_ad AFTER DELETE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
                END;
                CREATE TRIGGER IF NOT EXISTS nodes_au AFTER UPDATE ON nodes BEGIN
                    INSERT INTO nodes_fts(nodes_fts, rowid, title, body) VALUES('delete', old.rowid, old.title, old.body);
                    INSERT INTO nodes_fts(rowid, title, body) VALUES (new.rowid, new.title, new.body);
                END;
            """)
            self.conn.commit()

    def upsert_node(self, node: Node) -> None:
        """Insert or update a node in the database."""
        with self.lock:
            self.conn.execute("""
                INSERT INTO nodes (id, title, path, body, frontmatter)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title=excluded.title,
                    path=excluded.path,
                    body=excluded.body,
                    frontmatter=excluded.frontmatter
            """, (
                node.id,
                node.title,
                node.path,
                node.body,
                json.dumps(node.frontmatter)
            ))
            self.conn.commit()

    def get_node(self, node_id: str) -> Node | None:
        """Fetch a single node by ID."""
        with self.lock:
            cursor = self.conn.execute("SELECT * FROM nodes WHERE id = ?", (node_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                return Node(
                    id=data["id"],
                    title=data["title"],
                    path=data["path"],
                    body=data["body"],
                    frontmatter=json.loads(data["frontmatter"])
                )
            return None

    def get_all_nodes(self, limit: int = 100, offset: int = 0) -> list[Node]:
        """Fetch all nodes with pagination."""
        with self.lock:
            cursor = self.conn.execute("SELECT * FROM nodes LIMIT ? OFFSET ?", (limit, offset))
            nodes = []
            for row in cursor.fetchall():
                data = dict(row)
                nodes.append(Node(
                    id=data["id"],
                    title=data["title"],
                    path=data["path"],
                    body=data["body"],
                    frontmatter=json.loads(data["frontmatter"])
                ))
            return nodes

    def get_neighbors(self, node_id: str) -> list[Node]:
        """Get outgoing neighbors of a node."""
        with self.lock:
            cursor = self.conn.execute("""
                SELECT nodes.* FROM nodes
                JOIN edges ON nodes.id = edges.target
                WHERE edges.source = ?
            """, (node_id,))
            nodes = []
            for row in cursor.fetchall():
                data = dict(row)
                nodes.append(Node(
                    id=data["id"],
                    title=data["title"],
                    path=data["path"],
                    body=data["body"],
                    frontmatter=json.loads(data["frontmatter"])
                ))
            return nodes

    def get_backlinks(self, node_id: str) -> list[Node]:
        """Get incoming neighbors of a node."""
        with self.lock:
            cursor = self.conn.execute("""
                SELECT nodes.* FROM nodes
                JOIN edges ON nodes.id = edges.source
                WHERE edges.target = ?
            """, (node_id,))
            nodes = []
            for row in cursor.fetchall():
                data = dict(row)
                nodes.append(Node(
                    id=data["id"],
                    title=data["title"],
                    path=data["path"],
                    body=data["body"],
                    frontmatter=json.loads(data["frontmatter"])
                ))
            return nodes

    def delete_node(self, node_id: str) -> None:
        """Delete a node and its associated backlinks."""
        with self.lock:
            # Explicitly delete backlinks as target is not cascaded
            self.conn.execute("DELETE FROM edges WHERE target = ?", (node_id,))
            self.conn.execute("DELETE FROM nodes WHERE id = ?", (node_id,))
            self.conn.commit()

    def close(self) -> None:
        """Close the database connection."""
        self.conn.close()
