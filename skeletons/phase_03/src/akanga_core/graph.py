"""Phase 03 — Graph Algorithms skeleton.

The data-structure classes (EdgeDirection, EgoEdge, EgoGraph) are provided.
Implement the two functions: `build_ego_graph` and `render_ascii`.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from akanga_core.db import GraphDatabase

# ---------------------------------------------------------------------------
# Provided data structures — do not modify
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
        truncated: True if a node budget (`limit`) stopped the traversal early —
                   the answer is partial. False for an unbounded build.
    """
    root: object                  # Node (typed loosely to avoid import cycle)
    nodes: dict[str, object]      # {node_id: Node}
    edges: list[EgoEdge]
    truncated: bool = False


# ---------------------------------------------------------------------------
# Skeleton functions — implement these
# ---------------------------------------------------------------------------


def build_ego_graph(
    root_id: str,
    db: "GraphDatabase",
    max_depth: int = 2,
    limit: int | None = None,
) -> EgoGraph:
    """WHAT: Build the subgraph centred on `root_id` using breadth-first search (BFS).

    WHY: The ego-graph is Akanga's primary navigation mechanism. Instead of
    showing the entire vault graph (which would be overwhelming), it shows the
    local neighbourhood of a node — what it links to, what links to it, and
    optionally what *those* nodes link to. Depth 1 is "immediate neighbours";
    depth 2 is "friends-of-friends". Depth alone does not bound size, though —
    a hub note can reach hundreds at depth 2 — so `limit` is a hard node budget
    (see the Node Budget concept in the phase doc).

    HOW:
    1. Fetch the root node: `root = db.get_node(root_id)`.
       If `root` is None, raise `ValueError(f"Node {root_id!r} not found")`.
    2. Initialise data structures:
         ego_nodes: dict[str, Node] = {root_id: root}
         ego_edges: list[EgoEdge] = []
         seen_edges: set[tuple[str, str, str]] = set()   # (source_id, target_id, relation)
         visited: set[str] = {root_id}
         queue: deque = deque([(root_id, 0)])   # (node_id, current_depth)
       Track `truncated = False`; the budget step (below) flips it.
    3. BFS loop — while queue is not empty:
         a. Dequeue `(current_id, depth)`.
         b. If `depth >= max_depth`, skip (do not expand further).
         Node budget: validate `limit` up front (`limit < 1` → ValueError; the
         root always counts). When you meet a NEW neighbour `n` (`n.id` not in
         visited), only admit it if `limit is None or len(ego_nodes) < limit`;
         otherwise set `truncated = True` and skip BOTH the node AND its edge
         (so every recorded edge still has both endpoints in `ego_nodes`). A
         neighbour already in `visited` is fine — record its edge as usual.
         c. Fetch outgoing edges WITH their relation labels:
              `for n, relation, relation_id in db.get_edges_from(current_id):`
              - If `n.id` not in visited:
                  - Add to visited, ego_nodes, and queue at `depth + 1`.
              - Dedup check (see step 4 note), then append:
                  EgoEdge(source_id=current_id, target_id=n.id,
                          relation=relation, relation_id=relation_id,
                          direction=EdgeDirection.OUTGOING)
         d. Fetch incoming edges WITH their relation labels:
              `for b, relation, relation_id in db.get_edges_to(current_id):`
              - If `b.id` not in visited:
                  - Add to visited, ego_nodes, and queue at `depth + 1`.
              - Dedup check, then append the edge in its NATURAL direction
                (source is the other node, target is the current node — never
                swap them; see the EgoEdge docstring):
                  EgoEdge(source_id=b.id, target_id=current_id,
                          relation=relation, relation_id=relation_id,
                          direction=EdgeDirection.INCOMING)
    4. Edge deduplication (CORE requirement, not an extra): the same logical
       edge IS discovered twice whenever BFS visits both endpoints — once as
       OUTGOING from the source, once as INCOMING at the target. Before
       appending, compute `key = (source_id, target_id, relation)`; if `key`
       is in `seen_edges`, skip it, otherwise add it to `seen_edges` and
       append the EgoEdge. (Keying on relation too preserves two DIFFERENT
       relations between the same pair as two edges.)
    5. Return `EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges,
       truncated=truncated)` — the caller must be told when the budget bit.

    Relation field: `db.get_edges_from` / `db.get_edges_to` (Phase 2) return
    `(node, relation, relation_id)` tuples — pass both values through to the
    EgoEdge. Do NOT hardcode `relation=""`; an unlabeled wikilink edge will
    naturally arrive as `("" , "")` from the DB.
    """
    raise NotImplementedError(
        "1. db.get_node(root_id) — raise ValueError if None. "
        "2. BFS with deque([(root_id, 0)]), a visited set, and a seen_edges set. "
        "3. At each node: db.get_edges_from (OUTGOING) + db.get_edges_to (INCOMING) — "
        "both yield (node, relation, relation_id); keep the natural direction. "
        "4. Add unvisited nodes to queue at depth+1; dedup edges by "
        "(source_id, target_id, relation) before appending. Honour `limit`: "
        "drop a new neighbour AND its edge once len(nodes) would exceed it, and "
        "set truncated=True. 5. Return EgoGraph(root, nodes, edges, truncated)."
    )


def render_ascii(ego: EgoGraph) -> str:
    """WHAT: Render the ego-graph as a human-readable ASCII string.

    WHY: The TUI needs a text-mode graph view for terminals that cannot render
    graphical widgets. A simple ASCII representation is readable up to ~12 nodes
    and is easy to implement without external libraries.

    HOW:
    Simple approach (sufficient for Phase 03):
    1. Start with a header line: `[ROOT] <root.title>`.
    2. Iterate over `ego.edges`.
    3. Render EVERY edge — OUTGOING and INCOMING alike — in its natural
       direction:
         Append: `  <source_title> --[<relation or 'links'>]--> <target_title>`
       EgoEdges already store source/target in the edge's natural (DB)
       direction, so both directions render identically. Never emit a
       reversed `<-` arrow and never invent an inverse relation name —
       `edge.direction` is for UI emphasis only, not for serialization.
    4. If there are no edges, append `  (no connections)`.
    5. Join all lines with newline characters and return.

    The only hard requirement from the tests:
    - The return value must be a non-empty `str`.
    - The root node's `title` must appear somewhere in the output.

    Tip: use `ego.nodes.get(edge.source_id)` and `ego.nodes.get(edge.target_id)`
    to look up node titles. Fall back to the raw UUID string if a node is missing.
    """
    raise NotImplementedError(
        "Build a list of strings starting with '[ROOT] <root.title>'; "
        "for each edge append '<source_title> --[<relation>]--> <target_title>' "
        "(natural direction for both OUTGOING and INCOMING — never '<-'); "
        "join with newlines and return."
    )
