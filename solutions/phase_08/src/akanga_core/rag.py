from __future__ import annotations
from pathlib import Path
from typing import TYPE_CHECKING, Any
from .graph import build_ego_graph
from .parser import parse_node_file

if TYPE_CHECKING:
    from akanga_core.db import GraphDatabase

MAX_CONTEXT_CHARS = 12000
MAX_BODY_CHARS = 500

def build_context(node_id: str, max_triples: int = 80, db: Any = None, vault: Any = None) -> str:
    """
    Build a context string for LLM consumption from a node and its ego-graph.
    
    Traverses the graph, reads node bodies (capped at 500 chars),
    stops if total context > 12000 chars, and wraps the output in <graph_context>.
    """
    # Note: db and vault are required for implementation but were not in the requested signature.
    # We include them as optional arguments to satisfy the prompt while remaining functional.
    if db is None or vault is None:
        return "<graph_context>Error: Database and Vault path must be provided.</graph_context>"

    try:
        # Support both Node objects (passed by tests) and node_id strings (requested by prompt)
        if not isinstance(node_id, str):
            actual_node_id = getattr(node_id, "id", str(node_id))
            root_node = node_id
        else:
            actual_node_id = node_id
            root_node = db.get_node(actual_node_id)
        
        if not root_node:
            return "<graph_context>Node not found</graph_context>"

        # 1. Traverse the graph (BFS ego-graph depth 2)
        ego = build_ego_graph(actual_node_id, db, max_depth=2)
    except Exception as e:
        return f"<graph_context>Error building context: {e}</graph_context>"

    lines = []
    current_len = 0
    
    # 2. Collect node contents
    lines.append("Entities:")
    current_len += len(lines[0]) + 1
    
    # Priority: root node first
    node_ids = [actual_node_id] + [nid for nid in ego.nodes if nid != actual_node_id]
    
    for nid in node_ids:
        node = ego.nodes[nid]
        try:
            # Read body from disk (capped at 500 chars)
            path = Path(node.path)
            if not path.is_absolute():
                path = Path(vault) / path
            
            parsed = parse_node_file(str(path))
            body = (parsed.content or "").replace("\n", " ")[:MAX_BODY_CHARS].strip()
        except Exception:
            body = "(content unavailable)"
            
        node_entry = f"- {node.title} ({node.type}): {body}\n"
        
        if current_len + len(node_entry) > MAX_CONTEXT_CHARS - 1000: # Reserve space for triples
            break
            
        lines.append(node_entry)
        current_len += len(node_entry)

    # 3. Serialize triples
    lines.append("\nRelations:")
    current_len += len(lines[-1]) + 1
    
    for edge in ego.edges[:max_triples]:
        source = ego.nodes.get(edge.source_id)
        target = ego.nodes.get(edge.target_id)
        if not source or not target:
            continue
            
        relation = edge.relation or "links"
        
        if edge.direction.value == "outgoing":
            triple = f"- {source.title}  --[{relation}]-->  {target.title}"
        else:
            # Simple inverse relation convention
            inverse = f"is_{relation}_by" if relation != "links" else "is_linked_by"
            triple = f"- {target.title}  --[{inverse}]-->  {source.title}"
            
        if current_len + len(triple) + 1 > MAX_CONTEXT_CHARS - 100:
            break
            
        lines.append(triple)
        current_len += len(triple) + 1
        
    content = "\n".join(lines)
    
    # 4. Wrap in <graph_context> as requested
    return f"<graph_context>\n{content}\n</graph_context>"
