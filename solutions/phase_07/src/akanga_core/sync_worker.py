"""SyncWorker — processes pending title rename propagation jobs.

When a node is renamed its ``title`` changes but all other Markdown files
that reference it by display name still show the old name.  A queue of
pending sync jobs is stored in the database; SyncWorker.drain() processes
those jobs, updates the stale display names on disk, and marks each job
complete.

This module is intentionally minimal — it has no background thread of its
own.  The caller (typically the indexer or a scheduled task) decides when
to call ``drain()``.
"""
from __future__ import annotations

import logging
from pathlib import Path

from .indexer import scan_vault
from .models import Node
from .parser import parse_node_file, write_node_file
from .sync_queue import mark_processed, pending_sync_jobs

logger = logging.getLogger(__name__)


class SyncWorker:
    """Processes pending rename-propagation jobs from the sync queue.

    Usage::

        worker = SyncWorker()
        processed = worker.drain(db, vault=Path("./vault"), limit=50)
    """

    def drain(self, db, vault: Path, limit: int = 50) -> int:
        """Process up to *limit* pending sync jobs from the queue.

        For each job (a node rename recorded by ``enqueue_title_sync``)
        the worker walks the vault, finds every ``.md`` file whose
        frontmatter ``edges:`` list references the renamed node by
        ``target_id``, patches the stale ``target`` display name, and
        writes the file back atomically. The job is then marked complete
        via ``mark_processed`` (``processed = 1`` — the row is kept as an
        audit trail, never deleted).

        CURRENT-TRUTH RULE: the propagated name is re-read from the vault
        at drain time — the file whose frontmatter ``id`` equals the
        job's ``entity_id`` carries the authoritative title. The job's
        ``new_name`` snapshot is only a fallback (entity file missing):
        if the node was renamed AGAIN after the job was enqueued, the
        stale snapshot must not be written over the newer truth.

        ``target_id`` (the stable UUID key) is never touched — only the
        ``target`` display cache is rewritten. All ``sync_queue`` rows
        are node-title propagation jobs at this phase, so there is no
        ``job_type`` to branch on.

        Args:
            db:    An open ``GraphDatabase`` instance (or a raw
                   ``sqlite3.Connection``).
            vault: Path to the root vault directory.
            limit: Maximum number of jobs to process in one call —
                   bounds the work on a large backlog.

        Returns:
            Number of jobs successfully processed.
        """
        # sync_queue speaks raw SQL: unwrap the connection when given a
        # GraphDatabase, but accept a bare sqlite3.Connection too.
        conn = getattr(db, "conn", db)

        processed = 0
        for job in pending_sync_jobs(conn, limit):
            entity_id = job["entity_id"]

            # Walk the vault fresh per job: an earlier job may have just
            # rewritten a file this job also needs to patch.
            parsed: dict[str, Node] = {}
            for path in scan_vault(str(vault)):
                try:
                    parsed[path] = parse_node_file(path)
                except Exception:  # noqa: BLE001 — one bad file must not stall the queue
                    logger.warning("SyncWorker: cannot parse %s", path, exc_info=True)

            # CURRENT truth: the renamed node's own file, found by entity_id.
            current_name = job["new_name"]
            for node in parsed.values():
                if node.id == entity_id and node.title:
                    current_name = node.title
                    break

            # Patch every referencing edge's display cache; never target_id.
            for path, node in parsed.items():
                edges = node.frontmatter.get("edges") or []
                changed = False
                for edge in edges:
                    if (
                        isinstance(edge, dict)
                        and edge.get("target_id") == entity_id
                        and edge.get("target") != current_name
                    ):
                        edge["target"] = current_name
                        changed = True
                if changed:
                    write_node_file(path, node.frontmatter, node.content)

            mark_processed(conn, job["id"])
            processed += 1

        return processed
