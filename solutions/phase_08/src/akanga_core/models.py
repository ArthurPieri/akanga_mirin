"""Core dataclasses for the Akanga knowledge graph.

Architectural rule (Phase 2): the database stores graph METADATA only —
titles, types, tags, paths, content hashes, and edges. Node prose lives in
the Markdown files on disk and is re-read from there whenever it is needed
(BUG-01). `Node` is therefore a metadata record, while `ParsedNote` is the
result of parsing a Markdown file from disk and carries the body content.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A node as stored in the database: metadata only, no prose body."""

    id: str
    title: str
    type: str = "note"
    tags: list[str] = field(default_factory=list)
    path: str = ""
    content_hash: str = ""


@dataclass
class Edge:
    """A directed, typed edge between two nodes."""

    source_id: str
    target_id: str
    relation: str = "links_to"
    relation_id: str = ""


@dataclass
class ParsedNote:
    """A Markdown file parsed from disk: frontmatter metadata plus prose body."""

    id: str
    title: str
    type: str = "note"
    tags: list[str] = field(default_factory=list)
    path: str = ""
    content: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
