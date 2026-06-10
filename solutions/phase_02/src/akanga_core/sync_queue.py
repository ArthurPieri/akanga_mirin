"""Background sync queue — pending title/workspace rename propagation jobs.

When a node is renamed, every edge in every other node that points at it
has a stale `target` display-cache field. Updating all those files
synchronously on the save path would block the watcher; instead a
lightweight job row is enqueued in SQLite and drained lazily by the
Phase 4 `SyncWorker`.

This module must NOT import from `db.py` (circular import). It speaks
raw SQL via the `db` handle (a `sqlite3.Connection`) passed into each
function. The `sync_queue` table itself ships in `DB_SCHEMA` (db.py)
from Phase 2 onward:

    CREATE TABLE IF NOT EXISTS sync_queue (
        id          TEXT PRIMARY KEY,
        entity_id   TEXT NOT NULL,
        new_name    TEXT NOT NULL,
        processed   INTEGER NOT NULL DEFAULT 0,   -- 0 = pending, 1 = done
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );
"""
from __future__ import annotations

import sqlite3
from uuid import uuid4


def enqueue_title_sync(db: sqlite3.Connection, node_id: str, new_title: str) -> None:
    """Insert a pending sync job for `node_id`, idempotently.

    Idempotency is enforced with SELECT-then-INSERT — at most one PENDING
    job per entity. `INSERT OR IGNORE` cannot do this: each call mints a
    fresh UUID primary key, so there is never a PK collision to ignore.
    `created_at` is filled by the column DEFAULT — never passed from here.
    """
    pending = db.execute(
        "SELECT COUNT(*) FROM sync_queue WHERE entity_id = ? AND processed = 0",
        (node_id,),
    ).fetchone()[0]
    if pending > 0:
        return  # a pending job for this entity already exists

    db.execute(
        "INSERT INTO sync_queue (id, entity_id, new_name, processed) VALUES (?, ?, ?, 0)",
        (str(uuid4()), node_id, new_title),
    )
    db.commit()


def pending_sync_jobs(db: sqlite3.Connection, limit: int = 50) -> list[dict]:
    """Return up to `limit` unprocessed jobs, oldest first, as plain dicts.

    Called by `SyncWorker.drain()` (Phase 4). The limit bounds startup
    work if many renames accumulated while the process was down. Rows are
    converted via `cursor.description` so this works with or without a
    `row_factory` set on the connection.
    """
    cursor = db.execute(
        "SELECT * FROM sync_queue WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
        (limit,),
    )
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def mark_processed(db: sqlite3.Connection, job_id: str) -> None:
    """Flip a job's `processed` flag to 1 (done) and commit.

    A 0/1 flag (rather than DELETE) preserves an audit trail and keeps
    restarts idempotent — re-processing an already-processed job is safe.
    """
    db.execute("UPDATE sync_queue SET processed = 1 WHERE id = ?", (job_id,))
    db.commit()
