"""Akanga data model — the ONE Node dataclass, plus the frontmatter Edge.

`Node` is the typed representation of a single `.md` file in the vault.
The shape is monotonic: fields are never renamed or removed in later
phases, so the parser, indexer, DB layer, TUI, and MCP server all share
one contract. Fields a phase does not need yet simply stay at their
defaults. Phase 2 adds NOTHING to the model — the indexer merely starts
filling the `content_hash` field that has existed since Phase 0.

`Edge` (added in Phase 1A) is the typed representation of one entry in a
node's frontmatter `edges:` list. The DB `edges` table persists the same
fields keyed by `source_id`.
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


@dataclass
class Edge:
    """A directed relationship stored in a node's frontmatter `edges:` list.

    Pairs display-cache fields (`relation`, `target`) with stable IDs
    (`relation_id`, `target_id`) so that renames can be propagated lazily
    via the sync queue rather than blocking the write path.
    """

    relation: str       # human-readable relation name, e.g. "supports"
                        # (display cache — may be stale after vocab edits)
    relation_id: str    # stable ID from the relation vocabulary, e.g.
                        # "EP-001"; "" until resolved
    target: str         # target node title (display cache — may be stale
                        # after a rename)
    target_id: str      # UUID string of the target node; "" if unresolved
