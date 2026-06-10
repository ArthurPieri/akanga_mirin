"""Akanga data model — the ONE Node dataclass, plus the frontmatter Edge.

IDENTICAL to skeletons/phase_01/src/akanga_core/models.py — Phase 02 adds
NOTHING to the data model. The Node contract is monotonic across all phases
(0 through 8): your Phase 0/1 parser keeps working unchanged. Phase 02's
indexer simply starts filling the `content_hash` field that has existed
(defaulting to "") since Phase 0.

HOW (Node field reference — provided, do not modify):
- id:            UUID as a *string* (e.g. str(uuid4())). Never a uuid.UUID object.
- title:         Human-readable node title from frontmatter (or filename fallback).
- type:          Plain string. Valid values: "note" | "reference".
                 There is NO enum — compare with string literals.
- tags:          List of tag strings from frontmatter.
- content_hash:  SHA-256 hex digest of the file — computed by the Phase 2
                 indexer and stored in the DB so the watcher can skip
                 unchanged files without re-parsing them.
- content:       Markdown body. Optional — the indexer feeds title/tags to
                 FTS5 but never persists the prose body in the nodes table
                 (file-first architecture).
- path:          Absolute or vault-relative path of the backing .md file.
- frontmatter:   The raw YAML frontmatter dict, unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single knowledge-graph node backed by one Markdown file.

    UNCHANGED from Phases 0 and 1 (monotonic contract — see the module
    docstring). `type` is a plain string: "note" | "reference".
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

    UNCHANGED from Phase 1A — this is THE edge dataclass for all phases.
    The DB `edges` table (see db.py DB_SCHEMA) persists the same fields,
    keyed by `source_id`; rows are returned as plain rows/tuples, not as a
    separate dataclass.
    """

    relation: str       # human-readable relation name, e.g. "supports"
                        # (display cache — may be stale after vocab edits)
    relation_id: str    # stable ID from the relation vocabulary, e.g.
                        # "EP-001" (= supports), or a UUID for custom
                        # relations; "" until resolved
    target: str         # target node title (display cache — may be stale
                        # after a rename)
    target_id: str      # UUID string of the target node; "" if unresolved
