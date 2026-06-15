"""Phase 02 — the indexer: files in, derived index out.

The `.md` files are the source of truth; the DB is an expendable index.
`full_scan_and_index` proves it: delete the `.db` file at any time, run
the scan again, and the identical graph comes back — nodes from the
files, edges re-derived from wikilinks and frontmatter edge blocks.

IDEMPOTENCE CONTRACT: `scan; scan` produces an identical DB. Three
mechanisms enforce it (the index used to be append-only, duplicating
every edge on every re-scan):

- Hash-first skip: a file's SHA-256 is computed BEFORE parsing and
  compared against the row stored at the same vault-relative path. An
  unchanged file costs one read — zero parses, zero writes.
- Delete-then-rederive: a changed file's outgoing edges are wiped
  (`db.delete_edges_from`) and rebuilt from the current body, so stale
  links die and re-derived links cannot accumulate (the schema's
  `UNIQUE(source_id, target_id, relation)` backstops this).
- Tombstones: after pass 1, every DB node whose file no longer exists
  on disk is deleted — file deletions reconcile instead of haunting
  search and RAG results forever.

IDENTITY STABILITY: a file with a missing or invalid `id` gets the
freshly minted UUID written BACK into its frontmatter (atomically)
before the upsert. Without the write-back every scan re-mints a new id,
orphaning the node's edges each time — an Obsidian vault imported with
no ids would never converge.

Two-pass design, changed files only: edges reference target nodes by
UUID, so every node must be in the `nodes` table BEFORE any edge can be
resolved — pass 1 upserts the changed nodes, pass 2 re-derives edges for
exactly those nodes. Rederive-all trigger: when a scan ADDS or REMOVES
any file, link resolution can change for unchanged sources too (a
wikilink whose target only now exists, or just vanished), so pass 2
re-derives EVERY node's edges instead of only the changed ones. The
per-file path (`index_file`, the watcher's path) still re-derives only
the changed node and defers cross-file resolution to the next full scan.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any
from uuid import UUID

from .links import extract_wikilinks, resolve_wikilink
from .parser import _fm_get, content_hash, parse_node_file, write_back, write_node_file

if TYPE_CHECKING:  # pragma: no cover — import only for type checkers
    from .db import GraphDatabase
    from .models import Node

logger = logging.getLogger(__name__)


def scan_vault(vault_path: str) -> Iterator[str]:
    """Yield the path of every indexable `.md` file under `vault_path`.

    Hidden directories (`.git/`, `.akanga/`, ...) are pruned in-place so
    `os.walk` never descends into them; non-`.md` files are skipped.
    Separating traversal from indexing keeps both halves testable.
    """
    for root, dirs, files in os.walk(vault_path):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.endswith(".md"):
                yield os.path.join(root, filename)


def _vault_relative(path: str, vault_path: str) -> str:
    """Normalise `path` to the vault-relative form stored in the DB.

    ONE spelling per file: `node.path` is always stored relative to the
    vault root, so the index survives the vault being moved or mounted
    elsewhere — and so the hash-first lookup finds the same row no
    matter how the caller spelled the path.
    """
    return os.path.relpath(os.path.abspath(path), os.path.abspath(vault_path))


def _node_disk_path(stored_path: str, vault_path: str) -> str:
    """Resolve a stored node path back to an absolute on-disk path.

    Stored paths are normally vault-relative (see `_vault_relative`),
    but rows written by other layers (e.g. the Phase 6 API) may be
    absolute — both spellings must resolve.
    """
    if os.path.isabs(stored_path):
        return stored_path
    return os.path.join(vault_path, stored_path)


def _persist_minted_id(node: Node | Any, path: str) -> bool:
    """Write a freshly minted UUID back into the file's frontmatter.

    `parse_node_file` silently replaces a missing/invalid `id` with a
    new uuid4 — but it is PURE and never touches the file, so without
    this write-back the next scan would mint a DIFFERENT id and orphan
    every edge pointing at this node. The write is atomic
    (`write_node_file`: temp file + fsync + `os.replace`).

    Returns True when the file was rewritten — the caller must re-hash.
    """
    raw_id = node.frontmatter.get("id")
    try:
        UUID(str(raw_id))
        return False  # the id on disk is already valid — nothing to do
    except ValueError:
        pass
    frontmatter = dict(node.frontmatter)
    frontmatter["id"] = node.id  # the uuid parse_node_file just minted
    write_node_file(path, frontmatter, node.content)
    node.frontmatter = frontmatter
    return True


def _index_node(
    path: str, db: GraphDatabase, vault_path: str
) -> tuple[Any, Any | None, bool]:
    """Index one file's NODE row; return `(node, parsed_or_None, is_new)`.

    `parsed` is None when nothing was written: either the content hash
    matched (unchanged file) or a duplicate-id conflict was refused.
    When `parsed` is a Node the caller still owes the edge re-derive
    (`_reindex_edges`) — kept separate so `full_scan_and_index` can
    defer edges until every changed node exists (the two-pass rule).

    `is_new` is True only when this path had NO row before — the signal
    `full_scan_and_index` uses to fire the rederive-all trigger (a new
    file can resolve wikilinks in unchanged files).
    """
    rel_path = _vault_relative(path, vault_path)
    file_hash = content_hash(path)  # ONE read; no parse on the fast path

    existing = db.get_node_by_path(rel_path)
    if existing is not None and existing.content_hash == file_hash:
        return existing, None, False  # unchanged — zero parses, zero writes

    # CHANGED file: fold inline `[[Target | relation]]` captures into the
    # frontmatter `edges:` block BEFORE parsing. `write_back` is atomic
    # and idempotent (a no-op when there is nothing to fold) — without
    # this call the Phase 1A fold is dead code at runtime and typed
    # inline edges reach the DB as bare wikilinks. The fold may change
    # the bytes, so re-hash afterwards. Boundary: unchanged files keep
    # the skip above, so an old never-folded file folds on its next real
    # edit (or when `rm *.db` forces a full re-index).
    write_back(path)
    file_hash = content_hash(path)

    node = parse_node_file(path)
    if _persist_minted_id(node, path):
        file_hash = content_hash(path)  # the write-back changed the bytes

    # Duplicate-id guard (disk-aware half; the DB half only warns). A
    # sync-conflict copy ("note (conflicted copy).md") carries the same
    # frontmatter id as the original. While the already-indexed file
    # still exists, keep it and refuse the newcomer — otherwise node
    # identity flaps between files on every scan. If the old path is
    # gone from disk, this is an ordinary move and the upsert proceeds.
    current = db.get_node(node.id)
    if current is not None:
        current_disk = os.path.abspath(_node_disk_path(current.path, vault_path))
        if current_disk != os.path.abspath(path) and os.path.exists(current_disk):
            logger.warning(
                "Duplicate node id %s: %r is already indexed and still on disk; "
                "refusing to index %r (sync-conflict copy suspected). "
                "Policy: the first-indexed file wins while both exist.",
                node.id,
                current.path,
                rel_path,
            )
            return current, None, False

    node.path = rel_path
    node.content_hash = file_hash
    db.upsert_node(node)
    return node, node, existing is None


def _reindex_edges(parsed: Node | Any, db: GraphDatabase) -> None:
    """Replace a node's outgoing edges with ones derived from its body.

    Delete-then-rederive is what makes re-indexing idempotent at the
    edge level: stale links from the previous version die here, and the
    re-derived links land on the schema's UNIQUE constraint instead of
    duplicating. Incoming edges belong to OTHER files — never touched.
    """
    db.delete_edges_from(parsed.id)

    # Wikilinks in the body → untyped "wikilink" edges. An unresolved
    # wikilink never silently evaporates — it logs a warning (N3).
    for title in extract_wikilinks(parsed.content or ""):
        target_id = resolve_wikilink(title, db)
        if target_id is not None and target_id != parsed.id:
            db.upsert_edge(parsed.id, target_id, relation="wikilink")
        elif target_id is None:
            logger.warning(
                "Unresolved wikilink [[%s]] in node %s — no edge created "
                "(target not indexed)",
                title,
                parsed.id,
            )

    # Frontmatter `edges:` entries → typed edges. A stored target_id wins;
    # otherwise the display-cache title is resolved like a wikilink. Keys are
    # read tolerantly (underscore OR hyphen, N11) via `_fm_get`.
    for raw in parsed.frontmatter.get("edges") or []:
        if not isinstance(raw, dict):
            continue
        target_title = _fm_get(raw, "target")
        target_id = _fm_get(raw, "target_id") or resolve_wikilink(target_title, db)
        if target_id and target_id != parsed.id:
            db.upsert_edge(
                parsed.id,
                target_id,
                _fm_get(raw, "relation"),
                _fm_get(raw, "relation_id"),
            )
        elif not target_id:
            logger.warning(
                "Unresolvable edge target %r (relation %r) in node %s — "
                "entry kept in file, no edge created",
                target_title,
                _fm_get(raw, "relation"),
                parsed.id,
            )


def index_file(path: str, db: GraphDatabase, vault_path: str) -> Node | Any:
    """Index one `.md` file — node row AND outgoing edges; return the node.

    Hash-first skip: the file's SHA-256 is computed before anything else
    and compared against the row stored at the same vault-relative path;
    on a match the existing record is returned WITHOUT parsing — a no-op
    editor save costs one file read, total.

    On change, in order: inline `[[Target | relation]]` captures are
    folded into the frontmatter `edges:` block (`write_back` — atomic,
    idempotent) and the file re-hashed, so typed prose edges become typed
    DB edges instead of dying as dead frontmatter; a missing/invalid id
    is minted and written back to the file (stable identity — see
    `_persist_minted_id`); the node row is upserted; and its outgoing
    edges are deleted and re-derived from the current body. Fold
    boundary: an old never-folded file is still skipped while its hash
    matches — it folds on its next real edit (or after `rm *.db`).
    A wikilink whose target is not indexed yet resolves on the next
    `full_scan_and_index` (its pass 2 sees the full registry).

    Exceptions (missing file, malformed YAML) propagate to the caller —
    `full_scan_and_index` logs and counts them.
    """
    node, parsed, _is_new = _index_node(path, db, vault_path)
    if parsed is not None:
        _reindex_edges(parsed, db)
    return node


def full_scan_and_index(vault_path: str, db: GraphDatabase) -> int:
    """Idempotent two-pass scan; return the number of files processed.

    Pass 1 walks the vault and upserts every CHANGED node (hash-first;
    failures are logged and counted, never fatal). The tombstone pass
    then deletes DB nodes whose files vanished from disk. Pass 2
    re-derives edges for exactly the changed nodes — by then every
    possible target exists in the registry, which is why edge derivation
    cannot run inside pass 1 (a single-pass indexer silently drops any
    edge whose target file sorts later in the walk).

    Contract: `scan; scan` leaves the DB identical — an unchanged vault
    costs one hash per file and zero writes.
    """
    count = 0
    errors = 0
    new_files = False
    changed: list[Any] = []

    # ---- Pass 1: nodes (changed files only) ----------------------------
    for path in scan_vault(vault_path):
        try:
            _, parsed, is_new = _index_node(path, db, vault_path)
            if parsed is not None:
                changed.append(parsed)
            new_files = new_files or is_new
            count += 1
        except Exception:  # noqa: BLE001 — one bad file must not abort the scan
            logger.warning("Failed to index %s", path, exc_info=True)
            errors += 1
    if errors:
        logger.warning("Full scan: %d file(s) failed to index", errors)

    # ---- Tombstones: deletions must reconcile ---------------------------
    # A node whose file is gone leaves the index entirely — row, FTS
    # entry, and edges in BOTH directions via delete_node. Otherwise
    # deleted notes haunt search results and RAG context forever.
    removed = 0
    for node in db.list_nodes(limit=10_000):
        if not os.path.exists(_node_disk_path(node.path, vault_path)):
            logger.info("Tombstone: %s (%s) no longer on disk — removing", node.path, node.id)
            db.delete_node(node.id)
            removed += 1

    # ---- Pass 2: edges (registry is now complete) -----------------------
    # Rederive-all trigger: adding or removing any file can change link
    # resolution for UNCHANGED sources, so re-derive every node's edges.
    # Otherwise the changed-only path is enough and far cheaper.
    rederive_all = new_files or removed > 0
    if rederive_all:
        by_id = {p.id: p for p in changed}
        for node in db.list_nodes(limit=10_000):
            try:
                parsed = by_id.get(node.id)
                if parsed is None:
                    parsed = parse_node_file(_node_disk_path(node.path, vault_path))
                    parsed.id = node.id  # the stored id is canonical
                _reindex_edges(parsed, db)
            except Exception:  # noqa: BLE001 — one bad node must not abort the scan
                logger.warning("Edge re-derive failed for node %s", node.id, exc_info=True)
    else:
        for parsed in changed:
            try:
                _reindex_edges(parsed, db)
            except Exception:  # noqa: BLE001 — one bad node must not abort the scan
                logger.warning("Edge re-derive failed for node %s", parsed.id, exc_info=True)

    return count
