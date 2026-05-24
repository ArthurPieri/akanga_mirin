"""Phase 03 — Graph Algorithms skeleton.

The data-structure classes (EdgeDirection, EgoEdge, EgoGraph) are provided.
Implement the two functions: `build_ego_graph` and `render_ascii`.
"""
from __future__ import annotations

from collections import deque
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
    relative to the root node."""
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
# Skeleton functions — implement these
# ---------------------------------------------------------------------------


def build_ego_graph(
    root_id: str,
    db: "GraphDatabase",
    max_depth: int = 2,
) -> EgoGraph:
    """WHAT: Build the subgraph centred on `root_id` using breadth-first search (BFS).

    WHY: The ego-graph is Akanga's primary navigation mechanism. Instead of
    showing the entire vault graph (which would be overwhelming), it shows the
    local neighbourhood of a node — what it links to, what links to it, and
    optionally what *those* nodes link to. Depth 1 is "immediate neighbours";
    depth 2 is "friends-of-friends".

    HOW:
    1. Fetch the root node: `root = db.get_node(root_id)`.
       If `root` is None, raise `ValueError(f"Node {root_id!r} not found")`.
    2. Initialise data structures:
         ego_nodes: dict[str, Node] = {root_id: root}
         ego_edges: list[EgoEdge] = []
         visited: set[str] = {root_id}
         queue: deque = deque([(root_id, 0)])   # (node_id, current_depth)
    3. BFS loop — while queue is not empty:
         a. Dequeue `(current_id, depth)`.
         b. If `depth >= max_depth`, skip (do not expand further).
         c. Fetch outgoing neighbors: `neighbors = db.get_neighbors(current_id)`.
            For each neighbor node `n`:
              - If `n.id` not in visited:
                  - Add to visited, ego_nodes, and queue at `depth + 1`.
              - Always add an EgoEdge:
                  EgoEdge(source_id=current_id, target_id=n.id,
                          relation=<see below>, relation_id="",
                          direction=EdgeDirection.OUTGOING)
         d. Fetch incoming backlinks: `backlinks = db.get_backlinks(current_id)`.
            For each backlink node `b`:
              - If `b.id` not in visited:
                  - Add to visited, ego_nodes, and queue at `depth + 1`.
              - Always add an EgoEdge:
                  EgoEdge(source_id=b.id, target_id=current_id,
                          relation=<see below>, relation_id="",
                          direction=EdgeDirection.INCOMING)
    4. Return `EgoGraph(root=root, nodes=ego_nodes, edges=ego_edges)`.

    Relation field: `db.get_neighbors` / `db.get_backlinks` return Node-like
    objects. You can set `relation=""` or try to look it up from the edges
    table — an empty string is acceptable for Phase 03.

    Edge deduplication: the same logical edge may be added multiple times if
    the BFS visits both endpoints. For Phase 03, duplicates are acceptable.
    Advanced learners may deduplicate by `(source_id, target_id)`.
    """
    raise NotImplementedError(
        "1. db.get_node(root_id) — raise ValueError if None. "
        "2. BFS with deque([(root_id, 0)]) and a visited set. "
        "3. At each node: db.get_neighbors (OUTGOING) + db.get_backlinks (INCOMING). "
        "4. Add unvisited nodes to queue at depth+1; always append EgoEdge. "
        "5. Return EgoGraph(root, nodes_dict, edges_list)."
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
    3. For OUTGOING edges:
         Append: `  <source_title> -[<relation or 'links'>]-> <target_title>`
    4. For INCOMING edges:
         Append: `  <source_title> -[<relation or 'links'>]-> <target_title>`
       (Incoming edges are already stored with source/target in their natural
       direction — just render them the same way.)
    5. If there are no edges, append `  (no connections)`.
    6. Join all lines with newline characters and return.

    The only hard requirement from the tests:
    - The return value must be a non-empty `str`.
    - The root node's `title` must appear somewhere in the output.

    Tip: use `ego.nodes.get(edge.source_id)` and `ego.nodes.get(edge.target_id)`
    to look up node titles. Fall back to the raw UUID string if a node is missing.
    """
    raise NotImplementedError(
        "Build a list of strings starting with '[ROOT] <root.title>'; "
        "for each edge append '<source_title> -[<relation>]-> <target_title>'; "
        "join with newlines and return."
    )
