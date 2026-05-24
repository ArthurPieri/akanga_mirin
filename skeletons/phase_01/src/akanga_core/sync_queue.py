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
        id          TEXT PRIMARY KEY,
        entity_id   TEXT NOT NULL,
        new_name    TEXT NOT NULL,
        processed   INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

Notes on the schema:
- `processed` is a 0/1 flag (not a timestamp). 0 = pending, 1 = done.
- `created_at` defaults to the current time at INSERT — no need to set it
  explicitly from Python.
- There is no `job_type` column at this phase: all jobs are node-title
  propagations. Workspace-name jobs (Phase 4+) reuse the same shape and
  are distinguished by the caller, not by a column.
"""
from __future__ import annotations

from uuid import uuid4


def enqueue_title_sync(db, node_id: str, new_title: str) -> None:
    """WHAT: Insert a pending sync job into the `sync_queue` table.

    WHY: When a node is renamed, all edges pointing to it have a stale
    `target` display name. Rather than updating every referencing file
    immediately (which blocks the save path and may touch many files),
    we enqueue a job and process it lazily via `SyncWorker.drain()` in
    Phase 4.

    HOW:
    1. Generate a fresh job id: `job_id = str(uuid4())`.
    2. Check idempotency BEFORE inserting. Execute:

           SELECT COUNT(*) FROM sync_queue
           WHERE entity_id = ? AND processed = 0

       Bind `node_id` as the parameter. If the count is > 0, a pending
       job for this entity already exists — return immediately without
       inserting a duplicate.
    3. Otherwise INSERT the new job:

           INSERT INTO sync_queue (id, entity_id, new_name, processed)
           VALUES (?, ?, ?, 0)

       Bind `(job_id, node_id, new_title)`. The `created_at` column is
       populated automatically by the `DEFAULT (datetime('now'))` clause
       in the schema — do not pass it.
    4. Commit the transaction (or rely on the db handle's autocommit if
       it provides one).

    WHY NOT `INSERT OR IGNORE`:
    `INSERT OR IGNORE` only suppresses errors from PRIMARY KEY / UNIQUE
    constraint violations. Each call generates a fresh UUID for `id`, so
    there is never a PRIMARY KEY collision — every call would insert a
    new row, defeating idempotency. The SELECT-then-INSERT pattern above
    is required because the idempotency condition (one pending job per
    `entity_id`) is not expressible as a UNIQUE constraint on this table.
    """
    raise NotImplementedError(
        "Generate job_id = str(uuid4()). "
        "SELECT COUNT(*) FROM sync_queue WHERE entity_id = ? AND processed = 0 — "
        "if > 0, return without inserting. "
        "Otherwise INSERT INTO sync_queue (id, entity_id, new_name, processed) "
        "VALUES (?, ?, ?, 0). created_at is filled by the column DEFAULT. "
        "Do NOT use INSERT OR IGNORE — each call has a fresh UUID so there is no "
        "PRIMARY KEY collision to ignore; idempotency must be enforced by the SELECT."
    )


def pending_sync_jobs(db, limit: int = 50) -> list[dict]:
    """WHAT: Return up to `limit` unprocessed sync jobs from the queue.

    WHY: Called by `SyncWorker.drain()` in Phase 4 to get the batch of
    stale-name propagation jobs to process. The limit prevents unbounded
    work on startup if many renames accumulated while the process was down.

    HOW:
    1. Execute:

           SELECT * FROM sync_queue
           WHERE processed = 0
           ORDER BY created_at ASC
           LIMIT :limit

    2. Convert each row to a plain `dict` (column name → value). The
       returned dicts will contain the keys: `id`, `entity_id`,
       `new_name`, `processed`, `created_at`.
    3. Return the list of dicts. Return an empty list if there are no
       pending jobs.
    """
    raise NotImplementedError(
        "SELECT * FROM sync_queue WHERE processed = 0 ORDER BY created_at ASC "
        "LIMIT limit, then return rows as list[dict]"
    )


def mark_processed(db, job_id: str) -> None:
    """WHAT: Mark a sync job as processed by flipping its `processed` flag to 1.

    WHY: Once `SyncWorker.drain()` has successfully propagated a rename to all
    referencing files, the job must be marked done so that `pending_sync_jobs`
    no longer returns it. Using a 0/1 flag (rather than deletion) preserves an
    audit trail of completed jobs and makes restarts idempotent — if the worker
    crashes mid-drain it can safely re-process already-processed jobs without
    losing data.

    HOW:
    1. Execute:

           UPDATE sync_queue
           SET processed = 1
           WHERE id = ?

       Bind `job_id` as the parameter.
    2. Commit the transaction so the change is visible to other connections.
    """
    raise NotImplementedError(
        "UPDATE sync_queue SET processed = 1 WHERE id = job_id, then commit"
    )
