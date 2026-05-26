from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Node:
    """Core Node dataclass representing a single markdown file."""
    id: str
    title: str
    path: str
    body: str
    frontmatter: dict[str, Any] = field(default_factory=dict)


@dataclass
class Edge:
    """Core Edge dataclass representing a relationship between two nodes."""
    source: str
    target: str
    relation: str | None = None
