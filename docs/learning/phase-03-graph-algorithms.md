# Phase 3 — Graph Algorithms

**Estimated time:** 2–3 hours + ~1h vault/reflect

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
- Describe the ego-graph concept: what it includes, why both incoming and outgoing edges are traversed, and why the `direction` flag on `EgoEdge` is presentation metadata — not a change to how the edge is stored

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] Phase 2 is complete: I have a working `GraphDatabase` with `upsert_node`, `get_edges_from`, `get_edges_to`, and FTS5 search
  → Required: complete Phase 2 deliverable tests first
- [ ] I know what `collections.deque` is and the difference between `append` / `appendleft` and `pop` / `popleft`
  → Prerequisite: core Python `collections` module knowledge
- [ ] I understand what a Python `set` is and can use `in` and `.add()` on it
  → Prerequisite: core Python knowledge
- [ ] I can explain what a directed graph is and the difference between outgoing and incoming edges
  → Covered in Phase 1A — Directed Graph concept

---

## Quick Start

```bash
make skeleton PHASE=3    # copy the starting code into ./src/
make test PHASE=3        # run the tests (they will fail initially)
make study PHASE=3       # open the tmux study session
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

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
must decide which direction to follow. Akanga explores both in BFS: outgoing edges
(this node makes a claim about something else) and incoming edges (something else
makes a claim about this node).

**The natural-direction rule.** An `EgoEdge` *always* stores the edge in its natural
direction: `source_id` is the node that makes the claim, `target_id` is the node it
points at — regardless of which side of the edge the root sits on. Rendering is
therefore uniform in both cases: `source --[relation]--> target`. The `direction`
flag records only how the edge relates to the root (`OUTGOING` = root is the source,
`INCOMING` = root is the target) so the TUI can group edges under "Edges" vs
"Backlinks" headings. It is **presentation metadata** — it never flips the stored
source/target and never changes how the triple is serialized.

Every `EgoEdge` also carries the **real** `relation` and `relation_id` from the edges
table — Phase 2's `get_edges_from(node_id)` / `get_edges_to(node_id)` return full edge
rows, so the relation comes for free during traversal. Do not settle for `relation=""`.

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
```

(No `depth` field — the requested depth is an argument to `build_ego_graph`, not part
of the result. The skeleton and tests agree on this shape.)

**The traversal — written out explicitly, because this is the learning (`build_ego_graph`):**

```python
def build_ego_graph(root_id: str, db: GraphDatabase, max_depth: int = 2) -> EgoGraph:
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    queue      = deque([(root_id, 0)])
    visited    = {root_id}
    nodes      = {root_id: root}
    edges      = []
    seen_edges = set()   # dedup key: (source_id, target_id, relation)

    def add_edge(source_id, target_id, relation, relation_id, direction):
        key = (source_id, target_id, relation)
        if key in seen_edges:
            return       # BFS reaches both endpoints — add each logical edge once
        seen_edges.add(key)
        edges.append(EgoEdge(source_id=source_id, target_id=target_id,
                             relation=relation, relation_id=relation_id,
                             direction=direction))

    while queue:
        node_id, current_depth = queue.popleft()

        if current_depth >= max_depth:
            continue   # include the node but don't expand further

        # Outgoing — get_edges_from returns real edge rows, so relation and
        # relation_id come for free (Phase 2 API).
        for edge in db.get_edges_from(node_id):
            if edge.target_id not in visited:
                visited.add(edge.target_id)
                nodes[edge.target_id] = db.get_node(edge.target_id)
                queue.append((edge.target_id, current_depth + 1))
            add_edge(edge.source_id, edge.target_id, edge.relation,
                     edge.relation_id, EdgeDirection.OUTGOING)

        # Incoming — same natural direction (source → target); only the
        # direction flag differs.
        for edge in db.get_edges_to(node_id):
            if edge.source_id not in visited:
                visited.add(edge.source_id)
                nodes[edge.source_id] = db.get_node(edge.source_id)
                queue.append((edge.source_id, current_depth + 1))
            add_edge(edge.source_id, edge.target_id, edge.relation,
                     edge.relation_id, EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=nodes, edges=edges)
```

Edge deduplication is a **core deliverable**, not an advanced extra: when BFS visits
both endpoints of an edge, the same logical edge is encountered twice. Deduplicate by
`(source_id, target_id, relation)` — the relation belongs in the key because two nodes
may legitimately be connected by more than one relation type.

> **Why relations are required here (forward reference):** Phase 8 serializes these
> edges as `src --[rel]--> tgt` triples for an LLM. If you take the shortcut of
> `relation=""`, every triple degrades to a generic `relates_to` and the entire
> 72-type relation vocabulary never reaches the model. The relation you store in
> Phase 3 is the relation the LLM sees in Phase 8.

**ASCII renderer:**

```python
def render_ascii(ego: EgoGraph) -> str:
    """
    Header:     [ROOT] <root.title>
    Each edge:    <source_title> -[<relation or 'links'>]-> <target_title>
    No edges:     (no connections)
    Degrades gracefully beyond ~12 nodes (truncates with count).
    """
```

Both directions render identically — edges are already stored in natural direction,
so there is no separate "incoming" arrow style. The format is `-[relation]->`, the
same serialization Phase 8 will use.

---

## Common Pitfalls

**Missing cycle detection causes an infinite loop.** Akanga explicitly permits cycles (A supports B, B supports A is valid and meaningful). If you forget the `visited` set, BFS will enqueue A → B → A → B → … until memory is exhausted. This is not a theoretical edge case — any two nodes the user connects bidirectionally will trigger it. The fix is one line: check `if node_id not in visited` before enqueuing.

**Forgetting incoming edges in the ego-graph.** The ego-graph is supposed to show "what does this node connect to, and what connects to it." If you only traverse `get_edges_from` (outgoing), you miss all nodes that point *to* the ego node. The ego-graph must traverse both directions in BFS — outgoing via `get_edges_from` and incoming via `get_edges_to` — with the `direction` flag on `EgoEdge` recording each edge's relationship to the root. Remember: the flag is presentation metadata; the stored `source_id`/`target_id` stay in natural direction either way.

**Skipping edge deduplication.** When both endpoints of an edge are inside the ego-graph, BFS encounters the edge twice — once expanding each endpoint. Without a `seen_edges` set keyed by `(source_id, target_id, relation)`, the renderer shows every connection twice and the tests fail on duplicate signatures. Deduplicate as you append, not afterward.

**Over-engineering the ASCII renderer.** The ASCII ego-graph has a hard practical ceiling of around 12 nodes regardless of implementation quality. Beyond ~12 nodes, labels overlap and arrows cross unreadably — this is a constraint of the rendering medium, not a bug. Do not spend time building a sophisticated layout algorithm. The correct behavior beyond the ceiling is graceful degradation: truncate with a count ("… and 7 more nodes"). Richer rendering is a v2 feature requiring a proper canvas.

---

## Deliverable

The complete test suite is in `tests/phase_03/test_graph.py` — 12 tests in three groups:

**Depth semantics (`TestBuildEgoGraphDepth`):**

- `test_build_ego_graph_depth_1` — in chain A→B→C, `max_depth=1` from A includes A and B, not C
- `test_build_ego_graph_depth_2` — `max_depth=2` from A includes all of A, B, C
- `test_ego_graph_max_depth_zero` — `max_depth=0` returns only the root (raising `ValueError` is also accepted)

**Structure (`TestBuildEgoGraphStructure`):**

- `test_build_ego_graph_includes_root` — root is always in `ego.nodes`, and `ego.root` is that same object
- `test_build_ego_graph_cycle_handling` — cycle A→B→A at `max_depth=3` terminates
- `test_circular_graph_resolution` — bidirectional A⇄B at `max_depth=5`: exactly 2 nodes, and **no duplicate edge signatures** — this is where the dedup deliverable is enforced
- `test_build_ego_graph_both_directions` — A→B (outgoing) and C→A (incoming) both appear at `max_depth=1` from A
- `test_build_ego_graph_edge_directions` — `EgoEdge.direction` is `OUTGOING` for root→X, `INCOMING` for X→root, while source/target stay natural
- `test_build_ego_graph_empty_graph` — a node with no edges yields one node, zero edges
- `test_build_ego_graph_nonexistent_root` — unknown `root_id` raises (never silently returns `None`)

**Rendering (`TestRenderAscii`):**

- `test_render_ascii_returns_string` — non-empty `str`, no crash
- `test_render_ascii_contains_node_title` — the root's title appears in the output

All tests call `build_ego_graph(root_id, db, max_depth=N)` — the keyword is
`max_depth`, matching the skeleton signature. The cycle tests are the most important:
they prove the visited-set fix works and reflect a deliberate design choice (cycles
permitted, traversal safe).

Plus 8 vault nodes with typed edges.

---

## See It Work — 15 Minutes

Tests prove the algorithm; this proves the *feature*. Once `make test PHASE=3` is
green, point your code at your own vault — the one you've been building since Phase 0 —
and render the ego-graph of a real node in your terminal:

```bash
uv run python - <<'EOF'
from pathlib import Path
from akanga_core.db import GraphDatabase
from akanga_core.indexer import full_scan_and_index
from akanga_core.graph import build_ego_graph, render_ascii

db = GraphDatabase("./.akanga.db")
full_scan_and_index(Path("./vault"), db)

# Pick the node you created for this phase
root = next(n for n in db.list_nodes(limit=1000) if n.title == "BFS")
print(render_ascii(build_ego_graph(root.id, db, max_depth=2)))
db.close()
EOF
```

You should see the `BFS` node connected to `Graph Traversal`, `DFS`, `Ego-Graph`,
and whatever else you linked — with the **real relation names** (`subtype_of`,
`contrasts_with`, `is_applied_in`) in the arrows. If every arrow says `links` or is
blank, your edges aren't carrying relations: go back to `get_edges_from`/`get_edges_to`.
Swap the title for any other node in your vault and explore. This is the navigation
mechanism the TUI builds on in Phase 5.

---

## Reflect

> **Solo:** The traversal tracks `visited` by node ID and `seen_edges` by `(source_id, target_id, relation)`. Walk through the case where A → B and B → A both exist and `max_depth=2`: how many times does BFS *encounter* the edge A → B, and why does the dedup key include `relation` rather than just `(source_id, target_id)`? What real vault situation would the simpler key silently destroy?

> **Group:** BFS was chosen over DFS because it naturally groups nodes by distance from the root. But the ego-graph result (`EgoGraph.nodes`) is a dict keyed by UUID — distance is not stored. Should distance be included in the result? What would the TUI or ASCII renderer need to do differently if it had distance information, and is that worth the added complexity at this stage?
