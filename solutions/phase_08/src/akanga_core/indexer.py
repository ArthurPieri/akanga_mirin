from __future__ import annotations

from .db import Database


def search_fts(db: Database, query: str) -> list[dict]:
    """Search for nodes using FTS5 and return results ordered by rank."""
    if not query.strip():
        return []

    # SEC-06: Wrap terms in double quotes to prevent FTS5 operator injection
    # This ensures that query strings like "NEAR" or "AND" are treated as literal text.
    terms = query.split()
    safe_query = " ".join(f'"{t.replace("\"", "")}"' for t in terms)

    with db.lock:
        cursor = db.conn.execute("""
            SELECT nodes.* FROM nodes
            JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
            WHERE nodes_fts MATCH ?
            ORDER BY rank
        """, (safe_query,))
        return [dict(row) for row in cursor.fetchall()]
