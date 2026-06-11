"""Phase 02 — the indexer: files in, derived index out.

The `.md` files are the source of truth; the DB is an expendable index.
`full_scan_and_index` proves it: delete the `.db` file at any time, run
the scan again, and the identical graph comes back — nodes from the
files, edges re-derived from wikilinks and frontmatter edge blocks.

Two-pass design: edges reference target nodes by UUID, so every node
must be in the `nodes` table BEFORE any edge can be resolved. Pass 1
indexes all nodes; pass 2 resolves and upserts all edges against the
then-complete node registry. A single-pass indexer would silently drop
any edge whose target file simply sorted later in the walk.
"""
from __future__ import annotations

import logging
import os
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

from .links import extract_wikilinks, resolve_wikilink
from .parser import content_hash, parse_node_file

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


def index_file(path: str, db: GraphDatabase, vault_path: str) -> Node | Any:
    """Parse one `.md` file and upsert it into the DB; return the node.

    `node.path` is stored RELATIVE to the vault root, so the index stays
    valid if the vault directory is moved or mounted elsewhere.

    Hash-skip: when the stored `content_hash` already matches the file's
    current SHA-256, the file is unchanged and the existing record is
    returned WITHOUT an upsert — a no-op editor save never costs a write.

    Exceptions (missing file, malformed YAML) propagate to the caller —
    `full_scan_and_index` logs and counts them.
    """
    node = parse_node_file(path)
    node.content_hash = content_hash(path)
    node.path = os.path.relpath(os.path.abspath(path), os.path.abspath(vault_path))

    existing = db.get_node(node.id)
    if existing is not None and existing.content_hash == node.content_hash:
        return existing  # unchanged — skip the redundant DB write

    db.upsert_node(node)
    return node


def full_scan_and_index(vault_path: str, db: GraphDatabase) -> int:
    """Two-pass scan: index every node, then resolve and upsert every edge.

    Pass 1 walks the vault and upserts all nodes (failures are logged and
    counted, never fatal). Pass 2 re-reads each indexed node's body from
    disk — the DB never stores prose, so wikilinks only exist in the
    files — and turns both `[[Title]]` wikilinks and frontmatter `edges:`
    entries into resolved edge rows. Returns the number of nodes indexed.
    """
    count = 0
    errors = 0

    # ---- Pass 1: nodes -------------------------------------------------
    for path in scan_vault(vault_path):
        try:
            index_file(path, db, vault_path)
            count += 1
        except Exception:  # noqa: BLE001 — one bad file must not abort the scan
            logger.warning("Failed to index %s", path, exc_info=True)
            errors += 1
    if errors:
        logger.warning("Full scan: %d file(s) failed to index", errors)

    # ---- Pass 2: edges (every target now exists in the registry) -------
    for node in db.list_nodes(limit=10_000):
        # node.path is vault-relative (see index_file); rebuild the disk path.
        disk_path = (
            node.path if os.path.isabs(node.path) else os.path.join(vault_path, node.path)
        )
        try:
            parsed = parse_node_file(disk_path)
        except Exception:  # noqa: BLE001 — file vanished/changed between passes
            logger.warning("Pass 2: cannot re-read %s", disk_path, exc_info=True)
            continue

        # Wikilinks in the body → untyped "wikilink" edges.
        for title in extract_wikilinks(parsed.content or ""):
            target_id = resolve_wikilink(title, db)
            if target_id is not None and target_id != node.id:
                db.upsert_edge(node.id, target_id, relation="wikilink")

        # Frontmatter `edges:` entries → typed edges. A stored target_id
        # wins; otherwise the display-cache title is resolved like a wikilink.
        for raw in parsed.frontmatter.get("edges") or []:
            if not isinstance(raw, dict):
                continue
            target_id = raw.get("target_id") or resolve_wikilink(raw.get("target", ""), db)
            if target_id and target_id != node.id:
                db.upsert_edge(
                    node.id,
                    target_id,
                    raw.get("relation") or "",
                    raw.get("relation_id") or "",
                )

    return count
