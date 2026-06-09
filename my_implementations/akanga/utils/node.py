"""
Defines the basic node configuration
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4
from enum import StrEnum
from typing import Any
from datetime import datetime, UTC


class NodeType(StrEnum):
    """
    Types:
    - Note: Regular markdown file that lives on the Vault
    - Virtual: Used to point to things outside the current vault or unsupported formats
    - Active: A node that executes some type of action
    - Diagram : Show a diagram
    """

    note = "note"
    virtual = "virtual"
    # # Future:
    # active = "active"
    # diagram = "diagram"


class VirtualTypes(StrEnum):
    file = "file"
    url = "url"
    afk = "afk"
    person = "person"


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
    # TODO: Add dimensions
    # The ideia is that we could add dimensions where this node would show when seeing it, a way to filter things, needs more tought and discussions

    @staticmethod
    def new(path: str, title: str = "", node_type: NodeType = NodeType.note) -> Node:
        now = datetime.now(UTC)
        return Node(
            id=uuid4(),
            path=path,
            title=title,
            type=node_type,
            tags=[],
            frontmatter={},
            content="",
            created_at=now,
            updated_at=now,
        )


@dataclass
class ActiveConfig:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    interaval: int = 60
    timout: int = 5


@dataclass
class VirtualConfig:
    path: str
    external_type: VirtualTypes = VirtualTypes.url
    description: str = ""
