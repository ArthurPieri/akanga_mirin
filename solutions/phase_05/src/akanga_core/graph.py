"""Phase 03 — BFS ego-graph construction and ASCII rendering.

An ego-graph is the subgraph centred on one root node, expanded
breadth-first to ``max_depth`` hops in BOTH directions (outgoing and
incoming edges). It is Akanga's primary navigation mechanism: instead of
overwhelming the user with the whole vault graph, it shows the local
neighbourhood — depth 1 is "immediate neighbours", depth 2 is
"friends-of-friends".

Natural-direction rule (mandatory): every ``EgoEdge`` stores the edge
exactly as it exists in the DB ``edges`` table, regardless of whether BFS
discovered it leaving or entering the frontier node. ``direction`` is UI
metadata only — it must never flip source/target or invert a relation.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover — import only for type checkers
    from .db import GraphDatabase

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


class EdgeDirection(Enum):
    """Whether an edge is outgoing from or incoming to the ego-graph root."""

    OUTGOING = "outgoing"
    INCOMING = "incoming"


@dataclass
class EgoEdge:
    """A single directed edge in the ego-graph, annotated with its direction
    relative to the BFS frontier.

    NATURAL-DIRECTION RULE (mandatory): ``source_id`` and ``target_id``
    ALWAYS store the edge exactly as it exists in the DB ``edges`` table —
    the natural direction — regardless of whether BFS discovered it as
    outgoing or incoming. ``direction`` only records which side of the edge
    the BFS frontier was on (useful for UI emphasis); it must NEVER be used
    to flip source/target, rename the relation, or render a reversed ``<-``
    arrow. Serialization always reads ``src --[rel]--> tgt`` straight off
    this dataclass (see ``render_ascii`` and Phase 8's RAG triples).

    ``relation`` / ``relation_id`` are populated from the DB via
    ``db.get_edges_from`` / ``db.get_edges_to`` — an empty relation means
    the edge genuinely has no label (plain wikilink), not "lookup skipped".
    """

    source_id: str
    target_id: str
    relation: str
    relation_id: str
    direction: EdgeDirection


@dataclass
class EgoGraph:
    """The subgraph centred on a single root node.

    Attributes:
        root:  The root Node object.
        nodes: UUID → Node mapping for every node in the subgraph
               (including the root).
        edges: All EgoEdge objects in the subgraph.
    """

    root: Any                  # Node (typed loosely to avoid import cycle)
    nodes: dict[str, Any]      # {node_id: Node}
    edges: list[EgoEdge]


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------


def build_ego_graph(
    root_id: str,
    db: GraphDatabase,
    max_depth: int = 2,
) -> EgoGraph:
    """Build the subgraph centred on ``root_id`` using breadth-first search.

    WHY BFS with a ``visited`` set: the vault graph is cyclic (A→B→A is a
    perfectly legal pair of edges), so a naive recursive expansion would
    loop forever. Marking nodes visited as they are ENQUEUED — not when
    they are dequeued — guarantees each node is expanded at most once.

    WHY a ``seen_edges`` set: the same logical edge IS discovered twice
    whenever BFS visits both endpoints — once as OUTGOING from the source
    and once as INCOMING at the target. Deduplicating on
    ``(source_id, target_id, relation)`` keeps exactly one copy while
    still preserving two DIFFERENT relations between the same node pair
    as two distinct edges.

    Args:
        root_id:   UUID string of the centre node.
        db:        An open ``GraphDatabase``.
        max_depth: How many hops to expand (0 = root only).

    Returns:
        The populated ``EgoGraph``.

    Raises:
        ValueError: if ``root_id`` does not exist in the database.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, Any] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def visit(node: Any, depth: int) -> None:
        """Enqueue an undiscovered neighbour one level deeper."""
        if node.id not in visited:
            visited.add(node.id)
            ego_nodes[node.id] = node
            queue.append((node.id, depth + 1))

    def record(key: tuple[str, str, str], relation_id: str, direction: EdgeDirection) -> None:
        """Append the edge in its NATURAL direction unless already seen."""
        if key in seen_edges:
            return
        seen_edges.add(key)
        source_id, target_id, relation = key
        ego_edges.append(
            EgoEdge(
                source_id=source_id,
                target_id=target_id,
                relation=relation,
                relation_id=relation_id,
                direction=direction,
            )
        )

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue  # node is in the graph, but its neighbours are out of range

        # Outgoing: current → neighbour, exactly as stored in the DB.
        for neighbor, relation, relation_id in db.get_edges_from(current_id):
            visit(neighbor, depth)
            record((current_id, neighbor.id, relation), relation_id, EdgeDirection.OUTGOING)

        # Incoming: neighbour → current. The NATURAL direction is preserved —
        # the other node stays the source; only ``direction`` notes that BFS
        # arrived at this edge from its target side.
        for neighbor, relation, relation_id in db.get_edges_to(current_id):
            visit(neighbor, depth)
            record((neighbor.id, current_id, relation), relation_id, EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)


def render_ascii(ego: EgoGraph) -> str:
    """Render the ego-graph as a human-readable ASCII string.

    WHY: the TUI needs a text-mode graph view for terminals that cannot
    render graphical widgets, and it doubles as a debugging tool. Every
    edge — OUTGOING and INCOMING alike — is rendered in its natural
    direction (``src --[rel]--> tgt``); a reversed ``<-`` arrow or an
    invented inverse relation name would violate the natural-direction
    rule that Phase 8's triple serializer depends on.
    """
    def title_of(node_id: str) -> str:
        node = ego.nodes.get(node_id)
        return getattr(node, "title", node_id) if node is not None else node_id

    lines = [f"[ROOT] {ego.root.title}"]
    if not ego.edges:
        lines.append("  (no connections)")
    for edge in ego.edges:
        relation = edge.relation or "links"
        lines.append(
            f"  {title_of(edge.source_id)} --[{relation}]--> {title_of(edge.target_id)}"
        )
    return "\n".join(lines)
