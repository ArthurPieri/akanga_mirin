"""Akanga data model — the ONE Node dataclass.

`Node` is the typed representation of a single `.md` file in the vault.
The shape is monotonic: fields are never renamed or removed in later
phases, so the parser, indexer, DB layer, TUI, and MCP server all share
one contract. Fields a phase does not need yet (e.g. `content_hash`
before the Phase 2 indexer exists) simply stay at their defaults.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single knowledge-graph node backed by one Markdown file.

    `id` is always a UUID *string* (never a uuid.UUID object) and `type`
    is a plain string — "note" | "reference" — compared with literals,
    not an enum.
    """

    id: str
    title: str
    type: str = "note"
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""
    content: str = ""
    path: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
