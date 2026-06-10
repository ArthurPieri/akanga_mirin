"""BFS ego-graph construction over the knowledge graph.

An ego-graph is the subgraph centred on one root node, expanded breadth-first
to ``max_depth`` hops. Depth 2 is the practical default for Graph RAG:
depth 1 misses multi-hop reasoning, depth 3+ explodes context exponentially.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING

from .models import Node

if TYPE_CHECKING:
    from .db import GraphDatabase


class EdgeDirection(Enum):
    """Whether an edge was discovered leaving or entering the visited node."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"


@dataclass
class EgoEdge:
    """A single directed edge in the ego-graph.

    ``source_id`` and ``target_id`` always preserve the edge's NATURAL
    direction as stored in the database (D4 / BUG-03): an incoming edge is
    never inverted. ``direction`` only records how BFS discovered it.
    """

    source_id: str
    target_id: str
    relation: str
    relation_id: str = ""
    direction: EdgeDirection = EdgeDirection.OUTGOING


@dataclass
class EgoGraph:
    """The subgraph centred on a single root node."""

    root: Node
    nodes: dict[str, Node] = field(default_factory=dict)
    edges: list[EgoEdge] = field(default_factory=list)


def build_ego_graph(
    root_id: str,
    db: GraphDatabase,
    max_depth: int = 2,
) -> EgoGraph:
    """Build a BFS ego-graph around *root_id*.

    Edges are deduplicated on (source, target, relation) — BFS would
    otherwise record the same edge twice, once from each endpoint.

    Raises ValueError if the root node does not exist.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, Node] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def visit_neighbor(node: Node, depth: int) -> None:
        if node.id not in visited:
            visited.add(node.id)
            ego_nodes[node.id] = node
            queue.append((node.id, depth + 1))

    def record_edge(edge_key: tuple[str, str, str], direction: EdgeDirection) -> None:
        if edge_key not in seen_edges:
            seen_edges.add(edge_key)
            source_id, target_id, relation = edge_key
            ego_edges.append(
                EgoEdge(
                    source_id=source_id,
                    target_id=target_id,
                    relation=relation,
                    direction=direction,
                )
            )

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue

        for edge in db.get_outgoing_edges(current_id):
            target = ego_nodes.get(edge.target_id) or db.get_node(edge.target_id)
            if target is None:
                continue  # dangling edge — target was deleted
            visit_neighbor(target, depth)
            record_edge(
                (edge.source_id, edge.target_id, edge.relation), EdgeDirection.OUTGOING
            )

        for edge in db.get_incoming_edges(current_id):
            source = ego_nodes.get(edge.source_id) or db.get_node(edge.source_id)
            if source is None:
                continue
            visit_neighbor(source, depth)
            record_edge(
                (edge.source_id, edge.target_id, edge.relation), EdgeDirection.INCOMING
            )

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)
