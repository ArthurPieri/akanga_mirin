"""Phase 02 — Indexer skeleton.

Implement the three functions below.
"""
from __future__ import annotations

import os
from collections.abc import Iterator


def scan_vault(vault_path: str) -> Iterator[str]:
    """WHAT: Generator that yields the absolute path of every `.md` file in the vault.

    WHY: Separating traversal logic from indexing logic makes both easier to test
    and reason about. `full_scan_and_index` delegates the "find all files" concern
    here, so it only has to think about what to do with each path.

    HOW:
    1. Call `os.walk(vault_path)`. This yields `(root, dirs, files)` tuples.
    2. For each iteration, filter `dirs` **in-place** to exclude hidden
       directories (names starting with `"."`):
           dirs[:] = [d for d in dirs if not d.startswith(".")]
       This prevents `os.walk` from descending into `.git/`, `.akanga/`, etc.
    3. For each filename in `files` that ends with `".md"`, yield the full path:
           os.path.join(root, filename)

    Note: use `yield` — this is a generator function.
    """
    raise NotImplementedError(
        "os.walk(vault_path); dirs[:] = [d for d in dirs if not d.startswith('.')]; "
        "yield os.path.join(root, fn) for fn in files if fn.endswith('.md')"
    )


def index_file(path: str, db: "GraphDatabase", vault_path: str) -> "Node":
    """WHAT: Parse a single `.md` file and upsert it into the database.

    WHY: The file watcher calls this on every `on_modified` / `on_created` event
    so that the DB stays in sync with the filesystem without a full re-scan.

    HOW:
    1. Call `parse_node_file(path)` (from `parser.py`) to get a `Node` object.
    2. Call `content_hash(path)` (from `parser.py`) to compute the file's SHA-256
       hash. Assign it to `node.content_hash`.
       Hash-skip: call `db.get_node(node.id)` to look up the existing DB record.
       If the stored node's `content_hash` matches the newly computed hash, the file
       has not changed — return the existing node immediately WITHOUT calling
       `upsert_node`. This avoids redundant DB writes on re-index of unchanged files.
    3. Call `db.upsert_node(node)` to persist the node (only reached when content
       has changed or the node does not yet exist in the DB).
    4. Return the `Node`.

    Import `parse_node_file` and `content_hash` from `.parser` at the top of
    this file (or inside the function to avoid circular imports).

    Note: do NOT suppress exceptions here — let them propagate so the caller
    (`full_scan_and_index`) can log and count failures.
    """
    raise NotImplementedError(
        "parse_node_file(path) -> node; content_hash(path) -> node.content_hash; "
        "db.upsert_node(node); return node"
    )


def full_scan_and_index(vault_path: str, db: "GraphDatabase") -> int:
    """WHAT: Two-pass scan of the entire vault — first index all nodes, then extract edges.

    WHY: Edges reference other nodes by UUID. If you extracted edges in a single
    pass, a wikilink in `alpha.md` pointing to `beta.md` might be processed before
    `beta.md` has been indexed — leaving the edge unresolved. Two passes guarantee
    every target node exists before edge resolution begins.

    HOW:
    Pass 1 — Index nodes:
    1. Initialise `count = 0` and `errors = 0`.
    2. Iterate over `scan_vault(vault_path)`.
    3. For each path, call `index_file(path, db, vault_path)` inside a try/except.
       On success, increment `count`. On any exception, log a warning and increment
       `errors`.

    Pass 2 — Extract edges:
    4. Iterate over all nodes returned by `db.list_nodes()` (no limit needed here —
       use a high number or implement a loop, but for simplicity `db.list_nodes(limit=10_000)`
       is fine).
    5. For each node, call `extract_wikilinks(node.content or "")` (from `links.py`).
    6. For each wikilink title, call `resolve_wikilink(title, db)` (from `links.py`)
       to get a target UUID.
    7. If the target UUID is not None and is different from the source node's id,
       call `db.upsert_edge(node.id, target_id, relation="wikilink")`.

    Return `count` (the number of successfully indexed nodes).

    Hint: import `extract_wikilinks` and `resolve_wikilink` from `.links`.
    """
    raise NotImplementedError(
        "Pass 1: for path in scan_vault(vault_path): index_file(...); count edges. "
        "Pass 2: for node in db.list_nodes(): extract_wikilinks -> resolve_wikilink -> upsert_edge. "
        "Return count of indexed nodes."
    )
