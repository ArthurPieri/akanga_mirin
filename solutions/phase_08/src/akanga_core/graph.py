from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from akanga_core.db import GraphDatabase

class EdgeDirection(Enum):
    """Whether an edge is outgoing from or incoming to the ego-graph root."""
    OUTGOING = "outgoing"
    INCOMING = "incoming"

@dataclass
class EgoEdge:
    """A single directed edge in the ego-graph."""
    source_id: str
    target_id: str
    relation: str
    relation_id: str
    direction: EdgeDirection

@dataclass
class EgoGraph:
    """The subgraph centred on a single root node."""
    root: Any
    nodes: dict[str, Any]
    edges: list[EgoEdge]

def build_ego_graph(
    root_id: str,
    db: "GraphDatabase",
    max_depth: int = 2,
) -> EgoGraph:
    """
    Build a BFS ego-graph from a starting node, avoiding infinite loops with a visited set.
    """
    root = db.get_node(root_id)
    if not root:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes = {root_id: root}
    ego_edges = []
    visited = {root_id}
    queue = deque([(root_id, 0)])

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        # Outgoing neighbors
        neighbors = db.get_neighbors(current_id)
        for n in neighbors:
            # Cycle detection/Avoid infinite loops: only queue unvisited nodes
            if n.id not in visited:
                visited.add(n.id)
                ego_nodes[n.id] = n
                queue.append((n.id, depth + 1))
            
            # Record the edge
            ego_edges.append(EgoEdge(
                source_id=current_id,
                target_id=n.id,
                relation="", # Simple implementation
                relation_id="",
                direction=EdgeDirection.OUTGOING
            ))

        # Incoming backlinks
        backlinks = db.get_backlinks(current_id)
        for b in backlinks:
            if b.id not in visited:
                visited.add(b.id)
                ego_nodes[b.id] = b
                queue.append((b.id, depth + 1))
            
            # Record the edge
            ego_edges.append(EgoEdge(
                source_id=b.id,
                target_id=current_id,
                relation="",
                relation_id="",
                direction=EdgeDirection.INCOMING
            ))

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)
