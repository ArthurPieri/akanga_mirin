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
    id: UUID
    source_id: UUID
    target_id: UUID
    relation: str | None = None


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
