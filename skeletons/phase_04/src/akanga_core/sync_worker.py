"""SyncWorker — processes pending title/workspace rename propagation jobs.

When a node is renamed its ``title`` changes but all other Markdown files
that reference it by display name still show the old name.  A queue of
pending sync jobs is stored in the database; SyncWorker.drain() processes
those jobs, updates the stale display names on disk, and marks each job
complete.

This module is intentionally minimal — it has no background thread of its
own.  The caller (typically the indexer or a scheduled task) decides when
to call ``drain()``.

Reference implementation: there is no single file — the pattern is drawn
from the overall akanga_core data-flow described in CLAUDE.md.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SyncWorker:
    """Processes pending rename-propagation jobs from the sync queue.

    Usage::

        worker = SyncWorker()
        processed = worker.drain(db, vault=Path("./vault"), limit=50)
    """

    def drain(self, db, vault: Path, limit: int = 50) -> int:
        """WHAT: Process up to *limit* pending sync jobs from the queue.

        WHY: When a node is renamed, edges in other Markdown files still
        show the old ``target`` display name.  The drain worker reads
        those files, patches the stale display names, writes the files
        back atomically, and marks each job complete in the DB.  Without
        this, the graph would accumulate permanently stale edge labels.

        HOW:
        1. Import and call the module-level helper to fetch pending jobs::

               from akanga_core.sync_queue import pending_sync_jobs, mark_processed
               jobs = pending_sync_jobs(db, limit)

           ``pending_sync_jobs`` filters rows where ``processed = 0`` and
           returns them ordered by ``created_at ASC``. Each job dict has:

           - ``id``          — row primary key
           - ``entity_id``   — UUID of the node that was renamed
           - ``new_name``    — the new display name to propagate
           - ``processed``   — always ``0`` for rows returned here
           - ``created_at``  — ISO timestamp set by the column DEFAULT

           There is no ``job_type`` column in the Phase 02 schema — all
           rows in ``sync_queue`` are node-title propagation jobs at this
           phase, so do NOT branch on ``job_type``.

        2. For each job:

           a. Walk the vault with ``os.walk(vault)``, skipping hidden
              directories (any dir component starting with ``'.'``).
           b. For each ``.md`` file found:

              i.  Parse frontmatter with ``parse_node_file(path)``.
              ii. Inspect the parsed edges (frontmatter or body links) for
                  any edge whose ``target_id`` equals ``job["entity_id"]``
                  (the column is ``entity_id`` — there is no ``node_id``
                  column on ``sync_queue``).
              iii.If found, update ``edge["target"] = job["new_name"]``.
              iv. Write the file back atomically with ``write_node_file()``.

        3. After processing each job, mark it complete by calling::

               mark_processed(db, job["id"])

           This issues ``UPDATE sync_queue SET processed = 1 WHERE id = ?``
           under the hood. Do NOT write raw SQL here, and do NOT reference
           a ``processed_at`` column — the Phase 02 schema uses a 0/1
           ``processed`` flag, not a timestamp. The queue table is
           ``sync_queue`` (there is no ``title_sync_queue``).

        4. Return the total count of jobs processed.

        Args:
            db:    An open ``GraphDatabase`` instance.
            vault: Path to the root vault directory.
            limit: Maximum number of jobs to process in one call.
                   Prevents the worker from running indefinitely on a
                   large backlog.

        Returns:
            Number of jobs successfully processed.
        """
        raise NotImplementedError(
            "Import and call the module-level function: "
            "from akanga_core.sync_queue import pending_sync_jobs, mark_processed; "
            "jobs = pending_sync_jobs(db, limit)  — NOT db.pending_sync_jobs(limit). "
            "Iterate jobs, find and update stale edge display names in .md files, "
            "write files back atomically with write_node_file(), "
            "call mark_processed(db, job['id']) for each job (NOT raw SQL), "
            "return count of jobs processed."
        )
