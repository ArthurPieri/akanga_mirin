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

           Each job dict has at minimum:

           - ``id``          — row primary key
           - ``job_type``    — e.g. ``"node_title"``
           - ``entity_id``   — UUID of the node that was renamed
           - ``new_name``    — the new display name to propagate

        2. For each job where ``job_type == "node_title"``:

           a. Walk the vault with ``os.walk(vault)``, skipping hidden
              directories (any dir component starting with ``'.'``).
           b. For each ``.md`` file found:

              i.  Parse frontmatter with ``parse_node_file(path)``.
              ii. Inspect the parsed edges (frontmatter or body links) for
                  any edge whose ``target_id`` equals ``job["entity_id"]``
                  (NOT ``job["node_id"]`` — the column is ``entity_id``).
              iii.If found, update ``edge["target"] = job["new_name"]``.
              iv. Write the file back atomically with ``write_node_file()``.

        3. After processing each job, mark it complete by calling::

               mark_processed(db, job["id"])

           Do NOT issue raw SQL against ``title_sync_queue`` — that table
           does not exist; the queue table is ``sync_queue``, and
           ``mark_processed`` encapsulates the correct UPDATE.

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
            "Call db.pending_sync_jobs(limit), iterate jobs, "
            "find and update stale edge display names in .md files, "
            "write files back atomically with write_node_file(), "
            "mark each job processed in the DB, return count"
        )
