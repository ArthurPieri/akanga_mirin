"""Phase 03 — graph algorithms: BFS ego-graphs and ASCII rendering.

The ego-graph is Akanga's primary navigation mechanism: instead of
rendering the entire vault graph (overwhelming past ~50 nodes), it shows
the local neighbourhood of one root node. Depth 1 is "immediate
neighbours"; depth 2 is "friends-of-friends".

Two invariants matter more than the traversal itself:

- NATURAL DIRECTION: an `EgoEdge` always stores `source_id → target_id`
  exactly as the edge exists in the DB, no matter which side BFS was
  standing on when it discovered the edge. `direction` is UI metadata
  only — it never flips the arrow.
- DEDUPLICATION: BFS discovers every internal edge twice (once OUTGOING
  from its source, once INCOMING at its target). Edges are keyed by
  `(source_id, target_id, relation)` so each logical edge appears once,
  while two DIFFERENT relations between the same pair survive as two
  distinct edges.
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
    """Build the subgraph centred on `root_id` via breadth-first search.

    BFS expands BOTH directions from every frontier node — what the node
    points at (`get_edges_from`) and what points at it (`get_edges_to`) —
    because a backlink is just as much "neighbourhood" as a forward link.
    The `visited` set makes cycles (A→B→A) terminate: a node is enqueued
    at most once, so the queue is bounded by the node count.

    Raises:
        ValueError: when `root_id` does not exist in the database —
            silently returning an empty graph would mask typos in UUIDs.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, object] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def _record(edge: EgoEdge) -> None:
        """Append `edge` unless its (source, target, relation) was seen.

        Keying on relation too preserves two DIFFERENT relations between
        the same node pair as two distinct edges.
        """
        key = (edge.source_id, edge.target_id, edge.relation)
        if key not in seen_edges:
            seen_edges.add(key)
            ego_edges.append(edge)

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue  # frontier reached the depth budget — do not expand

        # Outgoing: current --[relation]--> neighbour (natural direction).
        for neighbour, relation, relation_id in db.get_edges_from(current_id):
            if neighbour.id not in visited:
                visited.add(neighbour.id)
                ego_nodes[neighbour.id] = neighbour
                queue.append((neighbour.id, depth + 1))
            _record(
                EgoEdge(
                    source_id=current_id,
                    target_id=neighbour.id,
                    relation=relation,
                    relation_id=relation_id,
                    direction=EdgeDirection.OUTGOING,
                )
            )

        # Incoming: source --[relation]--> current. The OTHER node is the
        # edge's source; never swap the pair to "point away from" current.
        for source, relation, relation_id in db.get_edges_to(current_id):
            if source.id not in visited:
                visited.add(source.id)
                ego_nodes[source.id] = source
                queue.append((source.id, depth + 1))
            _record(
                EgoEdge(
                    source_id=source.id,
                    target_id=current_id,
                    relation=relation,
                    relation_id=relation_id,
                    direction=EdgeDirection.INCOMING,
                )
            )

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)


def render_ascii(ego: EgoGraph) -> str:
    """Render the ego-graph as a human-readable ASCII string.

    Every edge — OUTGOING and INCOMING alike — renders in its natural
    direction as `source --[relation]--> target`; a reversed `<-` arrow
    or an invented inverse relation name would contradict the DB and the
    Phase 8 triple serializer. Unlabeled wikilink edges fall back to the
    generic word "links". Node titles come from `ego.nodes`; an id that
    is somehow missing degrades to the raw UUID instead of crashing.
    """
    def _title(node_id: str) -> str:
        node = ego.nodes.get(node_id)
        return getattr(node, "title", node_id) if node is not None else node_id

    lines = [f"[ROOT] {ego.root.title}"]
    for edge in ego.edges:
        relation = edge.relation or "links"
        lines.append(
            f"  {_title(edge.source_id)} --[{relation}]--> {_title(edge.target_id)}"
        )
    if not ego.edges:
        lines.append("  (no connections)")
    return "\n".join(lines)
