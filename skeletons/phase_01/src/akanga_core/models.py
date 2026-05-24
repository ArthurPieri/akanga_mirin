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
    id: UUID
    path: str
    title: str
    type: NodeType
    tags: list[str]
    frontmatter: dict[str, Any]
    content: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def new(path: str, title: str = "", type: NodeType = NodeType.note) -> Node:
        now = datetime.now(UTC)
        return Node(
            id=uuid4(), path=path, title=title, type=type,
            tags=[], frontmatter={}, content="",
            created_at=now, updated_at=now,
        )


@dataclass
class Edge:
    """A directed relationship between two nodes.

    Note: this Edge is different from the one in the reference implementation.
    It stores display-cache fields (`relation`, `target`) alongside stable IDs
    (`relation_id`, `target_id`) so that renames can be propagated lazily via
    the sync queue rather than blocking the write path.
    """
    relation: str       # human-readable relation name (display cache, may be stale after vocab edits)
    relation_id: str    # stable ID from the relation vocabulary (e.g. "EP-002") or a UUID for custom relations
    target: str         # target node title (display cache, may be stale after a rename)
    target_id: str      # UUID of the target node; empty string if the link is unresolved


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
