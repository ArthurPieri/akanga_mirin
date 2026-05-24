from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4


class NodeType(StrEnum):
    note = "note"
    active = "active"
    active_service = "active-service"
    diagram = "diagram"
    virtual = "virtual"


@dataclass
class Node:
    """Phase 02 Node — lighter than Phase 01.

    `content_hash` is computed by the indexer and stored in the DB so the
    watcher can skip unchanged files without re-parsing them.

    `content` is optional here: the indexer stores content in FTS5 but does
    not persist it in the main nodes table.
    """
    id: str             # UUID string
    path: str
    title: str
    type: str           # one of NodeType values
    tags: list[str]
    content_hash: str

    # Optional fields — may or may not be present depending on context
    content: str = ""


@dataclass
class Edge:
    """A directed relationship between two nodes stored in the DB.

    Phase 02 edges come from [[wikilink]] extraction or are created manually
    via db.upsert_edge().
    """
    id: str             # UUID string
    source_id: str      # UUID of the source node
    target_id: str      # UUID of the target node
    relation: str | None = None
    relation_id: str | None = None


@dataclass
class ActiveConfig:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    interval: int = 60
    timeout: int = 5


@dataclass
class VirtualConfig:
    url: str
    external_type: str = "url"
    description: str = ""
