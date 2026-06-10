"""Phase 3 — BFS ego-graph traversal.

Run: python examples/phase_03_bfs_ego_graph.py

Shows how BFS with a visited set handles cycles gracefully,
and explores both outgoing and incoming edges — mirroring the real
build_ego_graph(root_id, db, max_depth=2), which walks both
get_edges_from() and get_edges_to() at every hop.
Edges are always recorded in their natural direction: src --[rel]--> tgt.
"""
from collections import deque

# Toy graph: adjacency dict {node: [outgoing neighbors]}
graph = {
    "A": ["B", "C"],
    "B": ["D", "A"],   # B → A creates a cycle
    "C": ["D"],
    "D": [],
    "E": ["A"],        # E → A: only reachable from A via the INCOMING direction
}


def build_ego_graph(root_id: str, graph: dict, max_depth: int = 2) -> tuple[set, set]:
    # Reverse adjacency so we can follow incoming edges too (get_edges_to)
    reverse: dict[str, list[str]] = {}
    for src, targets in graph.items():
        for tgt in targets:
            reverse.setdefault(tgt, []).append(src)

    visited = {root_id}
    queue = deque([(root_id, 0)])
    edges: set[tuple[str, str]] = set()
    while queue:
        node, depth = queue.popleft()
        # Outgoing edges (get_edges_from): node --> neighbor
        for neighbor in graph.get(node, []):
            edges.add((node, neighbor))
            if neighbor not in visited and depth < max_depth:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
        # Incoming edges (get_edges_to): source --> node, kept in natural direction
        for source in reverse.get(node, []):
            edges.add((source, node))
            if source not in visited and depth < max_depth:
                visited.add(source)
                queue.append((source, depth + 1))
    return visited, edges


nodes, edges = build_ego_graph("A", graph, max_depth=2)
print("Ego-graph centered on A (max_depth=2):")
print(f"  Nodes: {sorted(nodes)}")
for src, tgt in sorted(edges):
    print(f"  {src} --[link]--> {tgt}")
print(f"\nCycle B→A handled: {len(nodes)} unique nodes, no infinite loop")
assert "E" in nodes, "Incoming edge E→A must pull E into the ego-graph"
assert ("E", "A") in edges, "Incoming edges keep their natural direction (E --> A)"
print("Incoming edge E→A included, natural direction preserved")
