"""SyncWorker — processes pending title rename-propagation jobs.

When a node is renamed its ``title`` changes but every other Markdown
file that references it by display name still shows the old name. A
queue of pending sync jobs is stored in the database (``sync_queue``,
written by ``sync_queue.enqueue_title_sync``); ``SyncWorker.drain()``
processes those jobs, patches the stale display names on disk, and marks
each job complete.

This module is intentionally minimal — it has no background thread of
its own. The caller (typically the indexer, the TUI, or a scheduled
task) decides when to call ``drain()``.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from .parser import parse_node_file, write_node_file
from .sync_queue import mark_processed, pending_sync_jobs

logger = logging.getLogger(__name__)


def _connection(db: Any) -> Any:
    """Return the raw sqlite3 connection for *db*.

    ``sync_queue`` functions speak raw SQL over a ``sqlite3.Connection``;
    callers hand ``drain()`` either a ``GraphDatabase`` (which exposes
    ``.conn``) or the bare connection itself.
    """
    return getattr(db, "conn", db)


class SyncWorker:
    """Processes pending rename-propagation jobs from the sync queue.

    Usage::

        worker = SyncWorker()
        processed = worker.drain(db, vault=Path("./vault"), limit=50)
    """

    def drain(self, db: Any, vault: Path, limit: int = 50) -> int:
        """Process up to *limit* pending sync jobs from the queue.

        WHY: when a node is renamed, edges in other Markdown files still
        show the old ``target`` display name. The drain worker reads those
        files, patches the stale display names (matching on the STABLE
        ``target_id`` UUID — never on the old title string), writes the
        files back atomically, and marks each job complete in the DB.
        Without this, the graph would accumulate permanently stale edge
        labels.

        Every job in the Phase 2 schema is a node-title propagation job —
        there is no ``job_type`` column to branch on.

        Args:
            db:    An open ``GraphDatabase`` (or raw ``sqlite3.Connection``).
            vault: Path to the root vault directory.
            limit: Maximum number of jobs to process in one call; bounds
                   startup work after a large backlog.

        Returns:
            Number of jobs processed.
        """
        conn = _connection(db)
        processed = 0
        for job in pending_sync_jobs(conn, limit):
            self._propagate_title(Path(vault), job["entity_id"], job["new_name"])
            mark_processed(conn, job["id"])  # flips processed=1; never deletes the row
            processed += 1
        return processed

    @staticmethod
    def _propagate_title(vault: Path, entity_id: str, new_name: str) -> None:
        """Patch every frontmatter edge pointing at *entity_id* on disk.

        Walks the vault (pruning hidden directories in-place), parses each
        ``.md`` file, and rewrites it — atomically, via
        ``write_node_file`` — only when an edge actually changed. The
        ``target_id`` UUID is the match key and is never modified; only
        the ``target`` display cache is refreshed.
        """
        for root, dirs, files in os.walk(vault):
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for filename in files:
                if not filename.endswith(".md"):
                    continue
                path = os.path.join(root, filename)
                try:
                    node = parse_node_file(path)
                except Exception:  # noqa: BLE001 — one bad file must not stall the queue
                    logger.warning("SyncWorker: cannot parse %s", path, exc_info=True)
                    continue

                changed = False
                for edge in node.frontmatter.get("edges") or []:
                    if (
                        isinstance(edge, dict)
                        and edge.get("target_id") == entity_id
                        and edge.get("target") != new_name
                    ):
                        edge["target"] = new_name
                        changed = True

                if changed:
                    write_node_file(path, node.frontmatter, node.content)
