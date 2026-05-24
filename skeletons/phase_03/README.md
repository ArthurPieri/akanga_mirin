# Phase 3 — Graph Algorithms

Implement the graph traversal and rendering functions in `graph.py`.

All other files (`db.py`, `indexer.py`, `links.py`, `parser.py`, `sync_queue.py`,
`models.py`) are reference markers — copy your Phase 02 solutions into them, or
set `AKANGA_SRC` to your Phase 02 `src/` directory.

## Files to implement

| File | Functions |
|---|---|
| `src/graph.py` | `build_ego_graph`, `render_ascii` |

The data-structure classes (`EdgeDirection`, `EgoEdge`, `EgoGraph`) are provided
in `graph.py` — do not modify them.

Note: `graph.py` lives at the **top level** of `src/` (not inside `akanga_core/`).
This is intentional — it lets the test runner import it as `from graph import ...`
while still using `from akanga_core.db import GraphDatabase` for the DB layer.

## Key concepts

- **Ego-graph** — the subgraph centred on one node, showing its local neighbourhood.
- **BFS (breadth-first search)** — guarantees shortest-path discovery and natural
  depth control via a counter in the queue.
- **Visited set** — prevents infinite loops when the graph contains cycles (e.g. A → B → A).
- **Edge direction** — an edge `A → B` is OUTGOING from A's perspective and INCOMING
  from B's perspective. Both are included in the ego-graph when B is the root.

## Running the tests

```bash
# From this skeleton directory (requires your Phase 02 src/ via AKANGA_SRC)
AKANGA_SRC=./src pytest -v
# Or via the repo Makefile (from the repo root)
AKANGA_SRC=./skeletons/phase_03/src make test PHASE=3
```
