# Phase 3 — Graph Algorithms

**Core concept:** This is the phase where you actually write graph code. Every previous
phase built the data — files, edges, DB rows. Phase 3 asks: given a node, what does
its neighborhood look like? The answer requires implementing a real traversal
algorithm, not just querying a table. The ego-graph is the feature that forces you to
write BFS.

---

## Concepts

### Graph Traversal

Systematically visiting nodes in a graph by following edges. Two classic strategies:
Breadth-First Search (BFS) visits all nodes at distance 1 before distance 2 before
distance 3 — it explores in expanding rings. Depth-First Search (DFS) follows one
path as deep as possible before backtracking. For ego-graphs, BFS is the natural
choice: you want all nodes within N hops, and BFS naturally groups them by distance
from the root.

> Akanga node: `Graph Traversal`

### BFS (Breadth-First Search)

A traversal algorithm using a queue. Start with the root node. While the queue is
non-empty: dequeue a node, add its unvisited neighbors to the queue, mark it visited.
BFS guarantees that when you first visit a node, you've found the shortest path to it.
The implementation uses `collections.deque` — append to the right (enqueue), pop from
the left (dequeue). For an ego-graph with max depth N, track the depth of each node
in the queue and stop expanding when depth equals N.

> Akanga node: `BFS`

### Cycle Detection

A graph has a cycle when following edges can bring you back to a node you've already
visited. Akanga explicitly permits cycles (A supports B, B supports A is valid and
meaningful). Without cycle detection, a BFS traversal on a cyclic graph loops forever,
consuming memory until the process crashes. The fix is a `visited` set: before
enqueuing a node, check if its ID is already in `visited`. If yes, skip it. This is
one line that prevents an infinite loop — and the reason you need it is that cycles
are allowed, not forbidden.

> Akanga node: `Cycle Detection`

### Ego-Graph

The subgraph centered on a single node (the "ego"), consisting of the ego node itself
and all nodes reachable within N hops, plus the edges connecting them. In Akanga, it
answers: "what does this node connect to, and what connects to it?" The ego-graph is
the primary navigation mechanism — the way you move through the knowledge graph rather
than scrolling a flat list. At depth 1 you see immediate neighbors; at depth 2 you see
neighbors of neighbors; and so on.

> Akanga node: `Ego-Graph`

### Directed Edge Traversal

In a directed graph, edges have a source and a target. When building an ego-graph, you
must decide which direction to follow. Akanga shows both: outgoing edges (this node
makes a claim about something else — rendered with a solid arrow) and incoming edges
(something else makes a claim about this node — rendered with a dotted arrow). Both
directions are explored in BFS. Each edge in the result carries a `direction` flag so
the TUI and ASCII renderer can distinguish them visually.

> Akanga node: `Directed Edge Traversal`

### Graph Density Ceiling (ASCII)

The ego-graph rendered as ASCII art has a hard practical ceiling of around 12 nodes
regardless of implementation quality. This is a constraint of the rendering medium,
not a bug. Beyond ~12 nodes, ASCII layouts become illegible — labels overlap, arrows
cross unreadably. Knowing this ceiling upfront prevents over-engineering the ASCII
renderer. The ASCII ego-graph is a navigation aid for MVP; richer rendering is a v2
feature requiring a proper canvas.

> Akanga node: `Graph Density Ceiling`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Graph Traversal` | note | `has_prerequisite` → `Directed Graph`; `enables` → `Ego-Graph` |
| `BFS` | note | `is_a` → `Graph Traversal`; `contrasts_with` → `DFS`; `is_applied_in` → `Ego-Graph` |
| `DFS` | note | `is_a` → `Graph Traversal`; `contrasts_with` → `BFS` |
| `Cycle Detection` | note | `solves` → `Infinite Traversal Loop`; `is_applied_in` → `BFS`; `uses` → `Visited Set` |
| `Ego-Graph` | note | `uses` → `BFS`; `is_applied_in` → `Akanga TUI`; `enables` → `Graph Navigation` |
| `Directed Edge Traversal` | note | `qualifies` → `BFS`; `enables` → `Incoming and Outgoing Display` |
| `Graph Density Ceiling` | note | `qualifies` → `ASCII Ego-Graph`; `motivates` → `Canvas Renderer in v2` |

---

## What You Build

Single module: `graph.py`

**Data structures:**

```python
from enum import Enum

class EdgeDirection(Enum):
    OUTGOING = "outgoing"   # root → neighbor (solid arrow in TUI)
    INCOMING = "incoming"   # neighbor → root (dotted arrow in TUI)

@dataclass
class EgoEdge:
    source_id:   str
    target_id:   str
    relation:    str
    relation_id: str
    direction:   EdgeDirection

@dataclass
class EgoGraph:
    root:  Node
    nodes: dict[str, Node]   # UUID → Node (includes root)
    edges: list[EgoEdge]
    depth: int               # max hops requested
```

**The traversal — written out explicitly, because this is the learning:**

```python
def ego_graph(root_id: str, db: GraphDatabase, depth: int = 1) -> EgoGraph:
    queue   = deque([(root_id, 0)])
    visited = {root_id}
    nodes   = {root_id: db.get_node(root_id)}
    edges   = []

    while queue:
        node_id, current_depth = queue.popleft()

        if current_depth >= depth:
            continue   # include the node but don't expand further

        for edge in db.get_edges_from(node_id):
            if edge.target_id and edge.target_id not in visited:
                visited.add(edge.target_id)
                nodes[edge.target_id] = db.get_node(edge.target_id)
                queue.append((edge.target_id, current_depth + 1))
            edges.append(EgoEdge(..., direction=EdgeDirection.OUTGOING))

        for edge in db.get_edges_to(node_id):
            if edge.source_id not in visited:
                visited.add(edge.source_id)
                nodes[edge.source_id] = db.get_node(edge.source_id)
                queue.append((edge.source_id, current_depth + 1))
            edges.append(EgoEdge(..., direction=EdgeDirection.INCOMING))

    return EgoGraph(root=nodes[root_id], nodes=nodes, edges=edges, depth=depth)
```

**ASCII renderer:**

```python
def render_ascii(ego: EgoGraph) -> str:
    """
    Outgoing: root ──[relation]──> neighbor
    Incoming: root <·····[relation]···· neighbor
    Degrades gracefully beyond ~12 nodes (truncates with count).
    """
```

---

## Deliverable

```python
def test_ego_graph_depth_1():
    # A contradicts B, A supports C
    # ego_graph(A, depth=1) → nodes {A,B,C}, 2 outgoing edges
    ...

def test_ego_graph_incoming():
    # A contradicts B
    # ego_graph(B, depth=1) → nodes {A,B}, 1 incoming edge from A
    ...

def test_cycle_does_not_loop():
    # A supports B, B supports A
    # ego_graph(A, depth=3) terminates, returns {A,B}, not infinite
    ...

def test_depth_boundary():
    # A → B → C
    # depth=1 → {A,B};  depth=2 → {A,B,C}
    ...

def test_disconnected_node():
    # D has no edges
    # ego_graph(D, depth=1) → {D}, edges []
    ...

def test_ascii_render_arrows():
    ego = ego_graph(root_id, db, depth=1)
    output = render_ascii(ego)
    assert "──" in output or "<·" in output
```

Plus 7 vault nodes with typed edges. The `test_cycle_does_not_loop` test is the most
important — it proves the visited-set fix works and reflects a deliberate design
choice (cycles permitted, traversal safe).
