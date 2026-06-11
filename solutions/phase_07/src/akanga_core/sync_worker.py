"""SyncWorker — processes pending title rename propagation jobs.

When a node is renamed its ``title`` changes but every other Markdown
file that references it by display name still shows the old name. A
queue of pending sync jobs is stored in the database (see
``sync_queue.py``); ``SyncWorker.drain()`` processes those jobs, patches
the stale display names on disk, and marks each job complete.

Drain re-reads CURRENT truth: it patches files as they exist on disk at
drain time, never from a cached snapshot — files may have changed (or
vanished) between enqueue and drain, and the `.md` files are the source
of truth.

This module is intentionally minimal — it has no background thread of
its own. The caller (typically the indexer or a scheduled task) decides
when to call ``drain()``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

from .parser import parse_node_file, write_node_file
from .sync_queue import mark_processed, pending_sync_jobs

if TYPE_CHECKING:
    from .db import GraphDatabase

logger = logging.getLogger(__name__)


class SyncWorker:
    """Processes pending rename-propagation jobs from the sync queue.

    Usage::

        worker = SyncWorker()
        processed = worker.drain(db, vault=Path("./vault"), limit=50)
    """

    def drain(self, db: "GraphDatabase", vault: Path, limit: int = 50) -> int:
        """Process up to *limit* pending sync jobs from the queue.

        For each job (``entity_id`` = renamed node's UUID, ``new_name`` =
        its new title) the whole vault is walked and every frontmatter
        edge whose ``target_id`` matches the entity gets its stale
        ``target`` display cache patched to the new name. ``target_id``
        is NEVER touched — the UUID is the stable key; only the display
        cache is propagated.

        Files are written back atomically via ``write_node_file`` and the
        job is flipped to ``processed = 1`` (the row stays — audit trail,
        idempotent restarts). The ``limit`` bounds startup work if many
        renames accumulated while the process was down.

        Returns:
            Number of jobs processed in this call.
        """
        # sync_queue functions speak raw SQL over a sqlite3.Connection;
        # accept either a GraphDatabase (use its .conn) or a bare connection.
        conn = getattr(db, "conn", db)

        processed = 0
        for job in pending_sync_jobs(conn, limit):
            try:
                self._propagate_title(vault, job["entity_id"], job["new_name"])
            except Exception:  # noqa: BLE001 — one bad job must not poison the queue
                logger.warning("Sync job %s failed", job["id"], exc_info=True)
                continue
            mark_processed(conn, job["id"])
            processed += 1
        return processed

    @staticmethod
    def _propagate_title(vault: Path, entity_id: str, new_name: str) -> None:
        """Patch stale edge display names for one renamed node, on disk.

        Walks the vault (pruning hidden directories), re-parses each
        `.md` file at drain time, and rewrites only the files that
        actually reference `entity_id` with an outdated `target` — a file
        already showing the new name is never rewritten (idempotent).
        """
        for root, dirs, files in os.walk(vault):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(root, filename)
                try:
                    node = parse_node_file(path)
                except Exception:  # noqa: BLE001 — skip unparseable files, keep draining
                    logger.warning("Cannot parse %s during drain", path, exc_info=True)
                    continue

                edges = node.frontmatter.get("edges") or []
                changed = False
                for edge in edges:
                    if (
                        isinstance(edge, dict)
                        and edge.get("target_id") == entity_id
                        and edge.get("target") != new_name
                    ):
                        edge["target"] = new_name
                        changed = True

                if changed:
                    write_node_file(path, node.frontmatter, node.content)
