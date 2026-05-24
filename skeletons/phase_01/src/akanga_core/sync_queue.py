"""Background sync queue — stores pending title/workspace rename propagation jobs.

WHY THIS MODULE EXISTS:
When a node is renamed, every edge in every other node that points to it has a
stale `target` display-cache field. Updating all those files synchronously on
the save path would be too slow and would block the watcher. Instead we enqueue
a lightweight job record in SQLite and process it lazily in the background.

This module must NOT import from db.py (circular import). It speaks raw SQL
via the `db` handle passed into each function.

Table schema (added to GraphDatabase.DB_SCHEMA in Phase 2 — see skeletons/phase_02/src/akanga_core/db.py):

    CREATE TABLE IF NOT EXISTS sync_queue (
        id           TEXT PRIMARY KEY,
        job_type     TEXT NOT NULL,
        entity_id    TEXT NOT NULL,
        new_name     TEXT NOT NULL,
        enqueued_at  TEXT NOT NULL,
        processed_at TEXT
    );

Job types
---------
"node_title"      — the `target` field in edges that reference `node_id` is stale
"workspace_name"  — the workspace name field in node frontmatter is stale (Phase 4+)
"""
from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4


def enqueue_title_sync(db, node_id: str, new_title: str) -> None:
    """WHAT: Insert a pending sync job into the `sync_queue` table.

    WHY: When a node is renamed, all edges pointing to it have a stale
    `target` display name. Rather than updating every referencing file
    immediately (which blocks the save path and may touch many files),
    we enqueue a job and process it lazily via `SyncWorker.drain()` in
    Phase 4.

    HOW:
    1. Generate a fresh UUID string with `str(uuid4())` as the job `id`.
    2. Set `enqueued_at` to the current UTC timestamp in ISO format:
       `datetime.now(UTC).isoformat()`.
    3. Execute an INSERT with these values:
         id           = new UUID
         job_type     = "node_title"
         entity_id    = node_id
         new_name     = new_title
         enqueued_at  = timestamp
         processed_at = NULL
    4. Use `INSERT OR IGNORE` so that a duplicate job for the same entity_id
       does not raise an error — the first enqueued job is enough.
    5. Commit the transaction (or rely on the db handle's autocommit if it
       provides one).
    """
    raise NotImplementedError(
        "INSERT OR IGNORE a row into sync_queue with job_type='node_title', "
        "entity_id=node_id, new_name=new_title, enqueued_at=now ISO, processed_at=NULL"
    )


def pending_sync_jobs(db, limit: int = 50) -> list[dict]:
    """WHAT: Return up to `limit` unprocessed sync jobs from the queue.

    WHY: Called by `SyncWorker.drain()` in Phase 4 to get the batch of
    stale-name propagation jobs to process. The limit prevents unbounded
    work on startup if many renames accumulated while the process was down.

    HOW:
    1. Execute:
         SELECT * FROM sync_queue
         WHERE processed_at IS NULL
         ORDER BY enqueued_at ASC
         LIMIT :limit
    2. Convert each row to a plain `dict` (column name → value).
    3. Return the list of dicts. Return an empty list if there are no
       pending jobs.
    """
    raise NotImplementedError(
        "SELECT * FROM sync_queue WHERE processed_at IS NULL ORDER BY enqueued_at ASC "
        "LIMIT limit, then return rows as list[dict]"
    )


def mark_processed(db, job_id: str) -> None:
    """WHAT: Mark a sync job as processed by setting its `processed_at` timestamp.

    WHY: Once `SyncWorker.drain()` has successfully propagated a rename to all
    referencing files, the job must be marked done so that `pending_sync_jobs`
    no longer returns it. Using a timestamp (rather than deletion) preserves an
    audit trail of completed jobs and makes restarts idempotent — if the worker
    crashes mid-drain it can safely re-process already-processed jobs without
    losing data.

    HOW:
    1. Compute the current UTC timestamp:
         `datetime.now(UTC).isoformat()`
    2. Execute:
         UPDATE sync_queue
         SET processed_at = <timestamp>
         WHERE id = <job_id>
    3. Commit the transaction so the change is visible to other connections.
    """
    raise NotImplementedError(
        "UPDATE sync_queue SET processed_at = datetime.now(UTC).isoformat() "
        "WHERE id = job_id, then commit"
    )
