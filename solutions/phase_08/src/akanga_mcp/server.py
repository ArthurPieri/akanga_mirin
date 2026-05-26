from __future__ import annotations
import os
from pathlib import Path
from mcp.server.fastmcp import FastMCP
from akanga_core.db import Database
from akanga_core.indexer import search_fts
from akanga_core.rag import build_context

# Initialize FastMCP server
mcp = FastMCP("Akanga Mirin")

# Global state for DB and Vault
db = None
vault_path = None

def init_server(vault: str | Path, db_path: str | Path):
    """Initialize the server with vault and database paths."""
    global db, vault_path
    vault_path = Path(vault)
    db = Database(str(db_path))

@mcp.tool()
def search_nodes(query: str) -> list[dict]:
    """Search for nodes using full-text search."""
    if db is None:
        return []
    return search_fts(db, query)

@mcp.tool()
def get_graph_context(node_id: str) -> str:
    """Build a graph-based context for a node for LLM consumption."""
    if db is None or vault_path is None:
        return "Error: Server not initialized"
    return build_context(node_id, db=db, vault=vault_path)

if __name__ == "__main__":
    v_path = os.getenv("AKANGA_VAULT_PATH")
    d_path = os.getenv("AKANGA_DB_PATH")
    if v_path and d_path:
        init_server(v_path, d_path)
    mcp.run(host="127.0.0.1")
