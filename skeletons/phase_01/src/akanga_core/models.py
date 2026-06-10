"""Akanga data model — the ONE Node dataclass, plus the frontmatter Edge.

WHAT: `Node` is the typed representation of a single `.md` file in the vault.
`Edge` (new in Phase 1A) is the typed representation of one entry in a
node's frontmatter `edges:` list.

WHY: The Node here is byte-for-byte UNCHANGED from Phase 0 — the Node
contract is monotonic across all phases (0 through 8): fields are never
renamed or removed, so code you wrote in an earlier phase keeps working.
Phase 1A adds exactly one thing: the `Edge` dataclass.

HOW (Node field reference — provided, do not modify):
- id:            UUID as a *string* (e.g. str(uuid4())). Never a uuid.UUID object.
- title:         Human-readable node title from frontmatter (or filename fallback).
- type:          Plain string. Valid values: "note" | "reference".
                 There is NO enum — compare with string literals.
                 "reference" (Phase 1B) points at an external resource via
                 top-level frontmatter fields (url / external_type / description).
- tags:          List of tag strings from frontmatter.
- content_hash:  SHA-256 hex digest of the file. Filled by the Phase 2
                 indexer; stays "" before that.
- content:       Markdown body. Optional — the DB never stores the prose body.
- path:          Absolute or vault-relative path of the backing .md file.
- frontmatter:   The raw YAML frontmatter dict, unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single knowledge-graph node backed by one Markdown file.

    UNCHANGED from Phase 0 (monotonic contract — see the module docstring).
    `type` is a plain string: "note" | "reference".
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

    This is THE edge dataclass from Phase 1A onward — every later phase
    (parser write-back, DB edge rows, ego-graph, RAG triples) is built on
    this shape; it never changes.

    It pairs display-cache fields (`relation`, `target`) with stable IDs
    (`relation_id`, `target_id`) so that renames can be propagated lazily
    via the sync queue rather than blocking the write path.
    """

    relation: str       # human-readable relation name, e.g. "supports"
                        # (display cache — may be stale after vocab edits)
    relation_id: str    # stable ID from the relation vocabulary, e.g.
                        # "EP-001" (= supports), or a UUID for custom
                        # relations; "" until resolved
    target: str         # target node title (display cache — may be stale
                        # after a rename)
    target_id: str      # UUID string of the target node; "" if unresolved
