"""Vault indexing and full-text search helpers.

Search is metadata-only (title + tags): node prose is never stored in the
database (Phase 2 rule / BUG-01), so FTS cannot and should not match body
text. SEC-06 quoting is handled inside :meth:`GraphDatabase.search`.
"""
from __future__ import annotations

from pathlib import Path

from .db import GraphDatabase
from .links import extract_edges, resolve_path
from .parser import parse_node_file


def search_fts(db: GraphDatabase, query: str) -> list[dict]:
    """Full-text search over node titles and tags.

    Returns plain dicts (id, title, type, tags, path) so results are directly
    JSON-serializable for the API and MCP layers. Empty queries return [].
    """
    return [
        {
            "id": node.id,
            "title": node.title,
            "type": node.type,
            "tags": node.tags,
            "path": node.path,
        }
        for node in db.search(query)
    ]


def index_file(db: GraphDatabase, vault: Path, path: Path) -> str:
    """Parse one Markdown file and upsert its node + outgoing edges.

    Returns the node ID. Prose is parsed for link extraction but never
    persisted — only metadata reaches the database.
    """
    parsed = parse_node_file(path)
    db.upsert_node(parsed)

    for target, relation in extract_edges(parsed.content):
        target_path = resolve_path(vault, path, target)
        if not target_path.exists():
            continue
        target_note = parse_node_file(target_path)
        db.upsert_node(target_note)
        db.upsert_edge(parsed.id, target_note.id, relation=relation)

    return parsed.id


def index_vault(db: GraphDatabase, vault: Path) -> int:
    """Index every Markdown file in the vault. Returns the node count."""
    count = 0
    for md_file in sorted(Path(vault).rglob("*.md")):
        index_file(db, Path(vault), md_file)
        count += 1
    return count
