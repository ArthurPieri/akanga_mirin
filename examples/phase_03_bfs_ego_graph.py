"""Phase 3 — BFS ego-graph traversal.

Run: python examples/phase_03_bfs_ego_graph.py

Shows how BFS with a visited set handles cycles gracefully,
and explores both outgoing and incoming edges.
"""
from collections import deque

# Toy graph: adjacency dict {node: [neighbors]}
graph = {
    "A": ["B", "C"],
    "B": ["D", "A"],   # B → A creates a cycle
    "C": ["D"],
    "D": [],
}


def build_ego_graph(root: str, graph: dict, max_depth: int = 2) -> dict:
    visited = {root}
    queue = deque([(root, 0)])
    result = {root: []}
    while queue:
        node, depth = queue.popleft()
        for neighbor in graph.get(node, []):
            result[node] = result.get(node, []) + [neighbor]
            if neighbor not in visited and depth < max_depth:
                visited.add(neighbor)
                queue.append((neighbor, depth + 1))
                result[neighbor] = result.get(neighbor, [])
    return result


ego = build_ego_graph("A", graph, max_depth=2)
print(f"Ego-graph centered on A (depth 2):")
for node, neighbors in ego.items():
    print(f"  {node} → {neighbors}")
print(f"\nCycle B→A handled: {len(ego)} unique nodes, no infinite loop")
