"""Phase 03 — graph algorithms: the BFS ego-graph and its ASCII renderer.

The ego-graph is Akanga's primary navigation mechanism: instead of the
whole vault graph it shows the LOCAL neighbourhood of one node — what it
links to, what links to it, and (at depth 2) what those nodes link to.

Two invariants carry through to later phases:

- NATURAL DIRECTION: every `EgoEdge` stores `source_id → target_id`
  exactly as the edge exists in the DB `edges` table, regardless of
  whether BFS discovered it walking outward or inward. `direction` only
  records which side the BFS frontier was on (UI emphasis); it is never
  used to flip endpoints, rename relations, or render `<-` arrows.
- DEDUPLICATION: BFS discovers the same logical edge twice whenever it
  visits both endpoints (once OUTGOING from the source, once INCOMING at
  the target), so edges are deduped by `(source_id, target_id, relation)`
  before appending. Keying on relation preserves two DIFFERENT relations
  between the same pair as two distinct edges.
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

    Depth 1 is "immediate neighbours"; depth 2 is "friends-of-friends";
    depth 0 returns the root alone. Both edge directions are explored —
    a node that merely POINTS AT the root is still part of its
    neighbourhood. Cycles terminate naturally because the `visited` set
    prevents any node from being enqueued twice.

    Raises:
        ValueError: when `root_id` does not exist in the database.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, object] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()  # (source_id, target_id, relation)
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def _add_edge(source_id: str, target_id: str, relation: str,
                  relation_id: str, direction: EdgeDirection) -> None:
        """Append the edge in its natural direction unless already recorded."""
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
            continue  # frontier node — do not expand further

        # Outgoing: current → neighbour, already in natural direction.
        for neighbour, relation, relation_id in db.get_edges_from(current_id):
            if neighbour.id not in visited:
                visited.add(neighbour.id)
                ego_nodes[neighbour.id] = neighbour
                queue.append((neighbour.id, depth + 1))
            _add_edge(current_id, neighbour.id, relation, relation_id,
                      EdgeDirection.OUTGOING)

        # Incoming: source → current. The OTHER node is the edge's source —
        # never swapped (natural-direction rule).
        for source, relation, relation_id in db.get_edges_to(current_id):
            if source.id not in visited:
                visited.add(source.id)
                ego_nodes[source.id] = source
                queue.append((source.id, depth + 1))
            _add_edge(source.id, current_id, relation, relation_id,
                      EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)


def render_ascii(ego: EgoGraph) -> str:
    """Render the ego-graph as a human-readable ASCII string.

    Every edge — OUTGOING and INCOMING alike — renders in its natural
    direction as `source --[relation]--> target`; a reversed `<-` arrow
    is never emitted and an inverse relation name is never invented
    (`edge.direction` is for UI emphasis only, not serialization).
    Unlabeled wikilink edges fall back to the literal `links` label, and
    missing node titles fall back to the raw UUID string.
    """
    title = getattr(ego.root, "title", "") or "(untitled)"
    lines = [f"[ROOT] {title}"]

    def _title_of(node_id: str) -> str:
        node = ego.nodes.get(node_id)
        return getattr(node, "title", None) or node_id

    for edge in ego.edges:
        relation = edge.relation or "links"
        lines.append(
            f"  {_title_of(edge.source_id)} --[{relation}]--> {_title_of(edge.target_id)}"
        )

    if not ego.edges:
        lines.append("  (no connections)")

    return "\n".join(lines)
