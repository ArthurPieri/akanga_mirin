"""Phase 03 — Graph algorithms: BFS ego-graph construction + ASCII rendering.

The ego-graph is Akanga's primary navigation mechanism: instead of the
whole vault graph, show the local neighbourhood of one node — what it
links to, what links to it, and (at depth 2) what *those* nodes touch.

Two invariants matter throughout this module:

- NATURAL DIRECTION: every `EgoEdge` stores `source_id → target_id`
  exactly as the edge exists in the DB `edges` table, no matter whether
  BFS discovered it walking forwards (outgoing) or backwards (incoming).
  `direction` is presentation metadata only.
- REAL RELATIONS: edges carry the relation label and registry id pulled
  from `db.get_edges_from` / `db.get_edges_to`. Phase 8 serializes these
  edges as `src -[rel]-> tgt` triples for an LLM — a hardcoded
  `relation=""` here would gut the 72-type vocabulary downstream.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — import only for type checkers
    from akanga_core.db import GraphDatabase, NodeRecord

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

    Nodes are `db.NodeRecord` instances — the DB's six-field read model
    (id/path/title/type/tags/content_hash), NOT `models.Node`: the graph
    is built from index rows, so there is no `.content` here. The import
    lives under `TYPE_CHECKING` (annotation-only; db.py is not needed at
    runtime in this module).

    Attributes:
        root:  The root NodeRecord.
        nodes: UUID → NodeRecord mapping for every node in the subgraph
               (including root).
        edges: All EgoEdge objects in the subgraph.
    """
    root: NodeRecord
    nodes: dict[str, NodeRecord]
    edges: list[EgoEdge]


# ---------------------------------------------------------------------------
# Algorithms
# ---------------------------------------------------------------------------


def build_ego_graph(
    root_id: str,
    db: GraphDatabase,
    max_depth: int = 2,
) -> EgoGraph:
    """WHAT: Build the subgraph centred on `root_id` using breadth-first search.

    WHY: Depth 1 is "immediate neighbours"; depth 2 is "friends-of-friends".
    The visited set is checked AT ENQUEUE TIME — the moment a neighbour is
    first seen — so each node enters the queue exactly once even in cyclic
    graphs (cycles are legal data in Akanga: A supports B, B supports A).

    HOW (the three load-bearing decisions):

    - Depth boundary: a node dequeued at `depth >= max_depth` is INCLUDED
      in `nodes` (it was added when first seen) but is NOT expanded — its
      own edges stay outside the ego-graph. `max_depth=0` therefore yields
      just the root with no edges.
    - Both directions: each expanded node contributes its outgoing edges
      (`db.get_edges_from`) AND its incoming edges (`db.get_edges_to`).
      Without the incoming half, nothing that merely points AT the root
      would ever appear. Incoming edges keep their natural direction —
      source is the other node — with `direction=INCOMING` as metadata.
    - Edge deduplication (CORE requirement): when BFS visits both
      endpoints of an edge it encounters the same row twice — once as
      OUTGOING from the source, once as INCOMING at the target. The
      `seen_edges` set keyed by `(source_id, target_id, relation)` drops
      the second sighting. Relation belongs in the key: two DIFFERENT
      relations between the same pair are two real edges, both kept.

    Raises:
        ValueError: if `root_id` does not exist in the database.
    """
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    ego_nodes: dict[str, NodeRecord] = {root_id: root}
    ego_edges: list[EgoEdge] = []
    seen_edges: set[tuple[str, str, str]] = set()
    visited: set[str] = {root_id}
    queue: deque[tuple[str, int]] = deque([(root_id, 0)])

    def _record(source_id: str, target_id: str, relation: str, relation_id: str,
                direction: EdgeDirection) -> None:
        """Append the edge in natural direction unless it was already seen."""
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
            continue  # boundary node: included above, never expanded

        # Outgoing: current → neighbour, already in natural direction.
        for node, relation, relation_id in db.get_edges_from(current_id):
            if node.id not in visited:
                visited.add(node.id)
                ego_nodes[node.id] = node
                queue.append((node.id, depth + 1))
            _record(current_id, node.id, relation, relation_id, EdgeDirection.OUTGOING)

        # Incoming: neighbour → current. The OTHER node is the source —
        # natural direction is preserved, never swapped.
        for node, relation, relation_id in db.get_edges_to(current_id):
            if node.id not in visited:
                visited.add(node.id)
                ego_nodes[node.id] = node
                queue.append((node.id, depth + 1))
            _record(node.id, current_id, relation, relation_id, EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)


def render_ascii(ego: EgoGraph) -> str:
    """WHAT: Render the ego-graph as a human-readable ASCII string.

    WHY: The TUI needs a text-mode graph view for terminals that cannot
    render graphical widgets. A flat edge list is readable up to ~12 nodes
    — a ceiling of the medium, not of the implementation — so no layout
    algorithm is attempted.

    HOW: One header line, then one line per edge in NATURAL direction:

        [ROOT] <root.title>
          <source_title> -[<relation or 'links'>]-> <target_title>

    Both OUTGOING and INCOMING edges render identically because EgoEdge
    already stores source/target as asserted in the DB — there is no
    reversed `<-` arrow style and no invented inverse relation. This is
    the same `-[rel]->` serialization Phase 8 hands to the LLM. Unlabeled
    edges fall back to the generic 'links'; titles fall back to the raw
    UUID when a node is somehow absent from `ego.nodes`. With no edges at
    all, the body is the single line `  (no connections)`.
    """
    def _title(node_id: str) -> str:
        node = ego.nodes.get(node_id)
        return getattr(node, "title", node_id) if node is not None else node_id

    lines = [f"[ROOT] {ego.root.title}"]
    if not ego.edges:
        lines.append("  (no connections)")
    else:
        for edge in ego.edges:
            relation = edge.relation or "links"
            lines.append(
                f"  {_title(edge.source_id)} -[{relation}]-> {_title(edge.target_id)}"
            )
    return "\n".join(lines)
