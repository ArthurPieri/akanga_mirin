# Phase 3 — Graph Algorithms

**Core concept:** This is the phase where you actually write graph code. Every previous
phase built the data — files, edges, DB rows. Phase 3 asks: given a node, what does
its neighborhood look like? The answer requires implementing a real traversal
algorithm, not just querying a table. The ego-graph is the feature that forces you to
write BFS.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Explain the structural difference between BFS and DFS and state concretely why BFS is the right choice for ego-graphs
- Implement BFS using `collections.deque` with a depth limit and a visited set for cycle detection
- Explain why cycle detection is mandatory in Akanga specifically (cycles are permitted by design, not forbidden)
- Describe the ego-graph concept: what it includes, what the `direction` flag on `EgoEdge` enables, and why both incoming and outgoing edges are traversed

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] Phase 2 is complete: I have a working `GraphDatabase` with `upsert_node`, `get_neighbors`, `get_backlinks`, and FTS5 search
  → Required: complete Phase 2 deliverable tests first
- [ ] I know what `collections.deque` is and the difference between `append` / `appendleft` and `pop` / `popleft`
  → Prerequisite: core Python `collections` module knowledge
- [ ] I understand what a Python `set` is and can use `in` and `.add()` on it
  → Prerequisite: core Python knowledge
- [ ] I can explain what a directed graph is and the difference between outgoing and incoming edges
  → Covered in Phase 1A — Directed Graph concept

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

> → Foundation doc: `docs/foundations/design-patterns.md` (Graph Traversal section)

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
| `BFS` | note | `subtype_of` → `Graph Traversal`; `contrasts_with` → `DFS`; `is_applied_in` → `Ego-Graph` |
| `DFS` | note | `subtype_of` → `Graph Traversal`; `contrasts_with` → `BFS` |
| `Cycle Detection` | note | `solves` → `Infinite Traversal Loop`; `is_applied_in` → `BFS`; `uses` → `Visited Set` |
| `Ego-Graph` | note | `uses` → `BFS`; `is_applied_in` → `Akanga TUI`; `enables` → `Graph Navigation` |
| `Directed Edge Traversal` | note | `qualifies` → `BFS`; `enables` → `Incoming and Outgoing Display` |
| `Graph Density Ceiling` | note | `qualifies` → `ASCII Ego-Graph` |
| `Canvas Renderer in v2` | note | `motivated_by` → `Graph Density Ceiling` |

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

**The traversal — written out explicitly, because this is the learning (`build_ego_graph`):**

```python
def build_ego_graph(root_id: str, db: GraphDatabase, depth: int = 1) -> EgoGraph:
    queue   = deque([(root_id, 0)])
    visited = {root_id}
    nodes   = {root_id: db.get_node(root_id)}
    edges   = []

    while queue:
        node_id, current_depth = queue.popleft()

        if current_depth >= depth:
            continue   # include the node but don't expand further

        # Note: `get_neighbors` and `get_backlinks` return Node objects, not Edge
        # objects. To get the relation name, you must query the edges table directly
        # or use `ego.edges` after building.
        for neighbor in db.get_neighbors(node_id):
            if neighbor.id and neighbor.id not in visited:
                visited.add(neighbor.id)
                nodes[neighbor.id] = neighbor
                queue.append((neighbor.id, current_depth + 1))
            edges.append(EgoEdge(..., direction=EdgeDirection.OUTGOING))

        for backlink in db.get_backlinks(node_id):
            if backlink.id not in visited:
                visited.add(backlink.id)
                nodes[backlink.id] = backlink
                queue.append((backlink.id, current_depth + 1))
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

## Common Pitfalls

**Missing cycle detection causes an infinite loop.** Akanga explicitly permits cycles (A supports B, B supports A is valid and meaningful). If you forget the `visited` set, BFS will enqueue A → B → A → B → … until memory is exhausted. This is not a theoretical edge case — any two nodes the user connects bidirectionally will trigger it. The fix is one line: check `if node_id not in visited` before enqueuing.

**Forgetting incoming edges in the ego-graph.** The ego-graph is supposed to show "what does this node connect to, and what connects to it." If you only traverse `get_neighbors` (outgoing), you miss all nodes that point *to* the ego node. The ego-graph must traverse both directions in BFS — outgoing via `get_neighbors` and incoming via `get_backlinks` — with the `direction` flag on `EgoEdge` distinguishing them for the renderer.

**Over-engineering the ASCII renderer.** The ASCII ego-graph has a hard practical ceiling of around 12 nodes regardless of implementation quality. Beyond ~12 nodes, labels overlap and arrows cross unreadably — this is a constraint of the rendering medium, not a bug. Do not spend time building a sophisticated layout algorithm. The correct behavior beyond the ceiling is graceful degradation: truncate with a count ("… and 7 more nodes"). Richer rendering is a v2 feature requiring a proper canvas.

---

## Deliverable

```python
def test_ego_graph_depth_1():
    # A contradicts B, A supports C
    # build_ego_graph(A, depth=1) → nodes {A,B,C}, 2 outgoing edges
    ...

def test_ego_graph_incoming():
    # A contradicts B
    # build_ego_graph(B, depth=1) → nodes {A,B}, 1 incoming edge from A
    ...

def test_cycle_does_not_loop():
    # A supports B, B supports A
    # build_ego_graph(A, depth=3) terminates, returns {A,B}, not infinite
    ...

def test_depth_boundary():
    # A → B → C
    # depth=1 → {A,B};  depth=2 → {A,B,C}
    ...

def test_disconnected_node():
    # D has no edges
    # build_ego_graph(D, depth=1) → {D}, edges []
    ...

def test_ascii_render_arrows():
    ego = build_ego_graph(root_id, db, depth=1)
    output = render_ascii(ego)
    assert "──" in output or "<·" in output
```

Plus 7 vault nodes with typed edges. The `test_cycle_does_not_loop` test is the most
important — it proves the visited-set fix works and reflects a deliberate design
choice (cycles permitted, traversal safe).

---

## Reflect

> **Solo:** The traversal tracks `visited` by node ID. But what about edges — could the same edge appear twice in `ego.edges`? Walk through the case where A → B and B → A both exist and depth=2. How many times does the edge A → B appear in the result (after calling `build_ego_graph`), and is that correct behavior for the renderer?

> **Group:** BFS was chosen over DFS because it naturally groups nodes by distance from the root. But the ego-graph result (`EgoGraph.nodes`) is a dict keyed by UUID — distance is not stored. Should distance be included in the result? What would the TUI or ASCII renderer need to do differently if it had distance information, and is that worth the added complexity at this stage?
