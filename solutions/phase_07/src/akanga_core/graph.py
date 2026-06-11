"""Phase 03 — graph algorithms: the ego-graph and its ASCII rendering.

The ego-graph is Akanga's primary navigation mechanism: instead of the
whole vault graph (overwhelming past ~50 nodes), it shows the local
neighbourhood of one node — what it links to, what links to it, and
optionally what *those* nodes link to. Depth 1 is "immediate
neighbours"; depth 2 is "friends-of-friends".

NATURAL-DIRECTION RULE (mandatory): every `EgoEdge` stores the edge
exactly as it exists in the DB `edges` table, regardless of whether BFS
discovered it walking forwards (outgoing) or backwards (incoming). The
`direction` field only records which side of the edge the BFS frontier
was on — UI emphasis, never serialization.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from akanga_core.db import GraphDatabase

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
    relative to the root node.

    NATURAL-DIRECTION RULE (mandatory): `source_id` and `target_id` ALWAYS
    store the edge exactly as it exists in the DB `edges` table — the
    natural direction — regardless of whether BFS discovered it as outgoing
    or incoming. `direction` only records which side of the edge the BFS
    frontier was on (useful for UI emphasis); it must NEVER be used to flip
    source/target, rename the relation, or render a reversed `<-` arrow.
    Serialization always reads `src --[rel]--> tgt` straight off this
    dataclass (see render_ascii and Phase 8's rag._serialize_triples).

    `relation` / `relation_id` are populated from the DB via
    `db.get_edges_from` / `db.get_edges_to` — an empty relation means the
    edge genuinely has no label (plain wikilink), not "lookup skipped".
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
        nodes: UUID → Node mapping for every node in the subgraph (including root).
        edges: All EgoEdge objects in the subgraph.
    """
    root: object                  # Node (typed loosely to avoid import cycle)
    nodes: dict[str, object]      # {node_id: Node}
    edges: list[EgoEdge]


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------


def build_ego_graph(
    root_id: str,
    db: "GraphDatabase",
    max_depth: int = 2,
) -> EgoGraph:
    """Build the subgraph centred on `root_id` using breadth-first search.

    BFS explores both edge directions at every frontier node — outgoing
    (`db.get_edges_from`) AND incoming (`db.get_edges_to`) — because a
    node's neighbourhood includes what points AT it, not just what it
    points at. A `visited` set makes cycles (A→B, B→A) terminate, and a
    `seen_edges` set deduplicates the edge each cycle is discovered
    through twice (once OUTGOING from the source, once INCOMING at the
    target). The dedup key includes the relation, so two DIFFERENT
    relations between the same pair survive as two edges.

    `max_depth` bounds expansion: a node dequeued at `depth >= max_depth`
    contributes no further neighbours, so `max_depth=0` returns only the
    root and `max_depth=1` its immediate neighbours.

    Raises:
        ValueError: if `root_id` does not exist in the database.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, object] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def _visit(node: object, depth: int) -> None:
        """Add a newly discovered neighbour to the frontier."""
        visited.add(node.id)
        ego_nodes[node.id] = node
        queue.append((node.id, depth + 1))

    def _record(
        source_id: str,
        target_id: str,
        relation: str,
        relation_id: str,
        direction: EdgeDirection,
    ) -> None:
        """Append the edge in its natural direction unless already seen."""
        key = (source_id, target_id, relation)
        if key in seen_edges:
            return
        seen_edges.add(key)
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
            continue  # frontier node at the boundary — do not expand further

        # Outgoing: current --[relation]--> neighbour (natural direction).
        for node, relation, relation_id in db.get_edges_from(current_id):
            if node.id not in visited:
                _visit(node, depth)
            _record(current_id, node.id, relation, relation_id, EdgeDirection.OUTGOING)

        # Incoming: neighbour --[relation]--> current. The edge is stored
        # source-first exactly as the DB has it — never swapped.
        for node, relation, relation_id in db.get_edges_to(current_id):
            if node.id not in visited:
                _visit(node, depth)
            _record(node.id, current_id, relation, relation_id, EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)


def render_ascii(ego: EgoGraph) -> str:
    """Render the ego-graph as a human-readable ASCII string.

    One header line for the root, then one line per edge in the edge's
    NATURAL direction — OUTGOING and INCOMING render identically because
    EgoEdge already stores source/target as the DB has them. No reversed
    `<-` arrows, no invented inverse relation names. Unlabeled edges
    (plain wikilinks) fall back to the literal word "links".

    Readable up to roughly a dozen nodes; the TUI uses a Tree widget for
    anything richer — this renderer is a debugging tool, not a UI.
    """
    def _title(node_id: str) -> str:
        node = ego.nodes.get(node_id)
        return getattr(node, "title", node_id) if node is not None else node_id

    lines = [f"[ROOT] {ego.root.title}"]
    if not ego.edges:
        lines.append("  (no connections)")
    for edge in ego.edges:
        relation = edge.relation or "links"
        lines.append(
            f"  {_title(edge.source_id)} --[{relation}]--> {_title(edge.target_id)}"
        )
    return "\n".join(lines)
