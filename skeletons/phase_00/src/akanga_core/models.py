"""Akanga data model — the ONE Node dataclass.

WHAT: `Node` is the typed representation of a single `.md` file in the vault.

WHY: Every phase of the learning path (0 through 8) uses THIS exact Node
shape — it is monotonic: fields are never renamed or removed in later
phases, so your parser, indexer, DB layer, TUI, and MCP server all share
one contract. Fields that a phase does not need yet (e.g. `content_hash`
before the Phase 2 indexer exists) simply stay at their defaults.

HOW (field reference — provided, do not modify):
- id:            UUID as a *string* (e.g. str(uuid4())). Never a uuid.UUID object.
- title:         Human-readable node title from frontmatter (or filename fallback).
- type:          Plain string. Valid values: "note" | "reference".
                 There is NO enum — compare with string literals.
                 "note" is the default; "reference" (Phase 1B) points at an
                 external resource via top-level frontmatter fields
                 (url / external_type / description).
- tags:          List of tag strings from frontmatter.
- content_hash:  SHA-256 hex digest of the file. Filled by the Phase 2
                 indexer; stays "" before that.
- content:       Markdown body. Optional — the DB never stores the prose
                 body (file-first architecture); it is read from disk when
                 needed.
- path:          Absolute or vault-relative path of the backing .md file.
- frontmatter:   The raw YAML frontmatter dict, unmodified.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """A single knowledge-graph node backed by one Markdown file.

    This shape is identical in every phase (monotonic contract — see the
    module docstring). `type` is a plain string: "note" | "reference".
    """

    id: str
    title: str
    type: str = "note"
    tags: list[str] = field(default_factory=list)
    content_hash: str = ""
    content: str = ""
    path: str = ""
    frontmatter: dict[str, Any] = field(default_factory=dict)
