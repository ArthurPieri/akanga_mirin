"""akanga_core — knowledge graph engine (Phase 8 reference solution).

Only lightweight modules are imported eagerly. Heavier integrations
(AkangaApp, the FastAPI server, the watcher) pull in optional runtime
dependencies and should be imported from their submodules directly.
"""
from .db import GraphDatabase
from .graph import EgoGraph, build_ego_graph
from .indexer import index_vault, search_fts
from .models import Edge, Node, ParsedNote
from .parser import atomic_write, parse_node_file, write_node_file
from .rag import MAX_CONTEXT_CHARS, build_context

__all__ = [
    "MAX_CONTEXT_CHARS",
    "Edge",
    "EgoGraph",
    "GraphDatabase",
    "Node",
    "ParsedNote",
    "atomic_write",
    "build_context",
    "build_ego_graph",
    "index_vault",
    "parse_node_file",
    "search_fts",
    "write_node_file",
]
