"""Akanga data model — the ONE Node dataclass, plus the frontmatter Edge.

`Node` is the typed representation of a single `.md` file in the vault.
`Edge` (new in Phase 1A) is the typed representation of one entry in a
node's frontmatter `edges:` list.

The Node here is byte-for-byte UNCHANGED from Phase 0 — the Node contract is
monotonic across all phases (0 through 8): fields are never renamed or
removed, so code written in an earlier phase keeps working. Phase 1A adds
exactly one thing: the `Edge` dataclass.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single knowledge-graph node backed by one Markdown file.

    UNCHANGED from Phase 0 (monotonic contract — see the module docstring).

    Field reference:

    - ``id``: UUID as a *string* (``str(uuid4())``). Never a ``uuid.UUID``
      object — strings survive YAML round-trips and SQLite columns unchanged.
    - ``title``: human-readable title from frontmatter (filename fallback).
    - ``type``: plain string, ``"note"`` or ``"reference"``. There is NO
      enum — compare with string literals. Reference nodes (Phase 1B) point
      at an external resource via top-level frontmatter fields
      (``url`` / ``external_type`` / ``description``), reachable through
      ``frontmatter``.
    - ``tags``: list of tag strings from frontmatter.
    - ``content_hash``: SHA-256 hex digest of the file. Filled by the
      Phase 2 indexer; stays ``""`` before that.
    - ``content``: Markdown body. The DB never stores the prose body —
      the parser is the only component that reads it.
    - ``path``: path of the backing ``.md`` file.
    - ``frontmatter``: the raw YAML frontmatter dict, unmodified.
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
    """A directed relationship stored in a node's frontmatter ``edges:`` list.

    This is THE edge dataclass from Phase 1A onward — every later phase
    (parser write-back, DB edge rows, ego-graph, RAG triples) builds on this
    shape; it never changes.

    It pairs display-cache fields (``relation``, ``target``) with stable IDs
    (``relation_id``, ``target_id``). The dual-key pattern means a rename
    only invalidates the cheap display cache: the authoritative IDs stay
    valid, so rename propagation can be deferred to the background sync
    queue instead of blocking the write path.
    """

    relation: str
    """Human-readable relation name, e.g. ``"supports"``.

    Display cache — may be stale after vocabulary edits.
    """

    relation_id: str
    """Stable ID from the relation vocabulary, e.g. ``"EP-001"``.

    A UUID for custom relations; ``""`` until resolved.
    """

    target: str
    """Target node title. Display cache — may be stale after a rename."""

    target_id: str
    """UUID string of the target node; ``""`` if unresolved."""
