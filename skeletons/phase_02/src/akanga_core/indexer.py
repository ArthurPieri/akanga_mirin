"""Phase 02 — Indexer skeleton.

Implement the three functions below.
"""
from __future__ import annotations

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
    """WHAT: Index a single `.md` file — hash-first skip, upsert, re-derive its edges.

    WHY: The file watcher calls this on every `on_modified` / `on_created` event.
    Re-indexing must be IDEMPOTENT: running it twice on an unchanged file must
    change nothing (`scan; scan` leaves the DB identical — there is a test).

    HOW:
    1. Hash FIRST, parse later: call `content_hash(path)` (one file read) and look
       up the existing DB row by vault-relative path. If the stored
       `content_hash` matches, the file is unchanged — return the existing node
       WITHOUT parsing. Parsing before hashing throws away the savings (the
       measured cost of that mistake: re-indexing an unchanged 1,000-node vault
       was only ~15% cheaper than a cold scan).
    2. Only on change: `parse_node_file(path)` to get the `Node`.
       UUID write-back: if the file had a missing/invalid `id`, the parser minted
       a fresh one in memory only — write it back into the frontmatter atomically
       (`write_node_file`) so the identity is STABLE across rescans, then re-hash
       (the write-back changed the bytes).
    3. Store the vault-RELATIVE path on the node, set `node.content_hash`, then
       `db.upsert_node(node)`.
    4. Re-derive THIS node's edges: `DELETE FROM edges WHERE source_id = ?` via
       the db layer, then re-extract frontmatter edges + wikilinks and
       `upsert_edge` each. Deleting first prevents stale edges from surviving an
       edit; the schema's UNIQUE(source_id, target_id, relation) +
       INSERT OR IGNORE prevents duplicates either way.
    5. Return the `Node`.

    Note: do NOT suppress exceptions here — let them propagate so the caller
    (`full_scan_and_index`) can log and count failures.
    """
    raise NotImplementedError(
        "content_hash(path) FIRST; skip if unchanged (lookup by relative path); "
        "else parse_node_file, write minted id back if the file had none, "
        "db.upsert_node, delete-then-rederive this node's edges; return node"
    )


def full_scan_and_index(vault_path: str, db: "GraphDatabase") -> int:
    """WHAT: Two-pass scan of the entire vault — first index all nodes, then extract edges.

    WHY: Edges reference other nodes by UUID. If you extracted edges in a single
    pass, a wikilink in `alpha.md` pointing to `beta.md` might be processed before
    `beta.md` has been indexed — leaving the edge unresolved. Two passes guarantee
    every target node exists before edge resolution begins.

    HOW:
    Pass 1 — Index nodes (changed files only):
    1. Initialise `count = 0`, `errors = 0`, and a set of vault-relative paths seen.
    2. Iterate over `scan_vault(vault_path)`; record each path as seen.
    3. For each path, call `index_file(path, db, vault_path)` inside a try/except.
       On success, increment `count`. On any exception, log a warning and increment
       `errors`. index_file's hash-first skip means unchanged files cost one hash
       and zero writes.

    Pass 2 — Resolve wikilinks for CHANGED nodes:
    4. For each node that index_file actually re-wrote (collect them in pass 1),
       read its body from disk:
           parsed = parse_node_file(disk_path)
           links = extract_wikilinks(parsed.content or "")
       The DB does not store body content — always re-read from disk. Two passes
       guarantee every wikilink target already exists before resolution.
    5. For each wikilink title, `resolve_wikilink(title, db)` → target UUID.
    6. If the target UUID is not None and differs from the source node's id,
       `db.upsert_edge(node.id, target_id, relation="wikilink", relation_id="")`.
       UNIQUE + INSERT OR IGNORE makes re-runs no-ops.

    Pass 3 — Tombstones (the DB is a derived index, finding #1):
    7. For every DB node whose vault-relative path was NOT seen on disk in pass 1,
       call `db.delete_node(node.id)` — a deleted note must not haunt FTS results,
       ego graphs, or RAG context forever.

    Return `count` (the number of successfully indexed nodes).

    Hint: import `parse_node_file` from `.parser` and `extract_wikilinks`,
    `resolve_wikilink` from `.links`.
    """
    raise NotImplementedError(
        "Pass 1: index_file for each scan_vault path (hash-first skip inside); "
        "Pass 2: wikilink resolution for changed nodes only; "
        "Pass 3: delete_node for DB paths missing from disk. Return count."
    )
