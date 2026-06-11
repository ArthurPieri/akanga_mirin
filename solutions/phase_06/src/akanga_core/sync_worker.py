"""SyncWorker — processes pending title rename propagation jobs.

When a node is renamed its ``title`` changes but all other Markdown files
that reference it by display name still show the old name.  A queue of
pending sync jobs is stored in the database; ``SyncWorker.drain()``
processes those jobs, patches the stale display names on disk, and marks
each job complete.

This module is intentionally minimal — it has no background thread of its
own.  The caller (typically the indexer or a scheduled task) decides when
to call ``drain()``.  Lazy propagation is the point: the rename itself
stays fast, and the (potentially large) fan-out of file rewrites happens
off the save path.
"""
from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from typing import Any

from .parser import parse_node_file, write_node_file
from .sync_queue import mark_processed, pending_sync_jobs

logger = logging.getLogger(__name__)


def _connection(db: Any) -> sqlite3.Connection:
    """Accept either a GraphDatabase or a raw sqlite3.Connection.

    The sync_queue helpers speak raw SQL over a Connection; callers hold
    a GraphDatabase. Unwrapping here keeps both entry points working.
    """
    return getattr(db, "conn", db)


def _iter_markdown_files(vault: Path):
    """Yield every `.md` file under `vault`, pruning hidden directories."""
    for root, dirs, files in os.walk(vault):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for filename in files:
            if filename.endswith(".md"):
                yield os.path.join(root, filename)


class SyncWorker:
    """Processes pending rename-propagation jobs from the sync queue.

    Usage::

        worker = SyncWorker()
        processed = worker.drain(db, vault=Path("./vault"), limit=50)
    """

    def drain(self, db: Any, vault: Path, limit: int = 50) -> int:
        """Process up to `limit` pending sync jobs; return how many ran.

        For each job (``entity_id`` = renamed node's UUID, ``new_name`` =
        its new title), every `.md` file in the vault is scanned for
        frontmatter edges whose ``target_id`` matches the entity. Matching
        edges get their stale ``target`` display cache replaced with the
        new name — ``target_id`` is NEVER touched, the UUID is the stable
        key — and the file is rewritten atomically via ``write_node_file``.
        Files whose edges already carry the new name are left untouched.

        Each completed job is flipped to ``processed = 1`` through
        ``mark_processed`` (the row is kept as an audit trail, not
        deleted), so a crash mid-drain re-runs only the unfinished jobs —
        and re-running a finished one is a harmless no-op.
        """
        conn = _connection(db)
        jobs = pending_sync_jobs(conn, limit)

        processed = 0
        for job in jobs:
            self._propagate(Path(vault), job["entity_id"], job["new_name"])
            mark_processed(conn, job["id"])
            processed += 1
        return processed

    @staticmethod
    def _propagate(vault: Path, entity_id: str, new_name: str) -> None:
        """Patch every stale edge pointing at `entity_id` across the vault."""
        for path in _iter_markdown_files(vault):
            try:
                node = parse_node_file(path)
            except Exception:  # noqa: BLE001 — one bad file must not stop the drain
                logger.warning("SyncWorker: cannot parse %s", path, exc_info=True)
                continue

            edges = node.frontmatter.get("edges") or []
            changed = False
            for edge in edges:
                if not isinstance(edge, dict):
                    continue
                if edge.get("target_id") == entity_id and edge.get("target") != new_name:
                    edge["target"] = new_name  # display cache only — never target_id
                    changed = True

            if changed:
                write_node_file(path, node.frontmatter, node.content)
