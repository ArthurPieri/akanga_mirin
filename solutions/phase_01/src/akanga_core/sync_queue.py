"""Background sync queue — pending title/workspace rename propagation jobs (Phase 1B).

When a node is renamed, every edge in every other node that points to it has a
stale ``target`` display-cache field. Rewriting all those files synchronously
on the save path would block the watcher and touch an unbounded number of
files, so detection and propagation are decoupled: a rename *enqueues* a tiny
job row in SQLite (cheap, on the save path) and a background worker *drains*
the queue lazily (Phase 4's ``SyncWorker``).

This module deliberately does NOT import from ``db.py`` (that would be a
circular import once Phase 2 exists). It speaks raw SQL through whatever
``sqlite3.Connection`` the caller hands in.

Table schema (authoritative — added to ``GraphDatabase.DB_SCHEMA`` in Phase 2)::

    CREATE TABLE IF NOT EXISTS sync_queue (
        id          TEXT PRIMARY KEY,
        entity_id   TEXT NOT NULL,
        new_name    TEXT NOT NULL,
        processed   INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL DEFAULT (datetime('now'))
    );

Schema notes:

- ``processed`` is a 0/1 flag, not a timestamp: 0 = pending, 1 = done. Jobs
  are flipped, never deleted — the completed rows are a free audit trail and
  make a crashed worker's restart idempotent.
- ``created_at`` is filled by the column DEFAULT at INSERT time; Python never
  sets it.
- There is no ``job_type`` column in this phase: every job is a node-title
  propagation. Workspace-name jobs (Phase 4+) reuse the same row shape and
  are distinguished by the caller, not by a column.
"""
from __future__ import annotations

import sqlite3
from typing import Any
from uuid import uuid4

# Kept in sync with GraphDatabase.DB_SCHEMA (Phase 2). Running it here makes
# the module self-sufficient in Phase 1B, before the DB layer exists.
_TABLE_SQL = """\
CREATE TABLE IF NOT EXISTS sync_queue (
    id          TEXT PRIMARY KEY,
    entity_id   TEXT NOT NULL,
    new_name    TEXT NOT NULL,
    processed   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
)
"""


def _ensure_table(db: sqlite3.Connection) -> None:
    """Create the ``sync_queue`` table if it does not exist yet.

    ``CREATE TABLE IF NOT EXISTS`` is a no-op when Phase 2's ``GraphDatabase``
    has already created the table, so calling this on every operation is safe
    and keeps Phase 1B usable standalone.
    """
    db.execute(_TABLE_SQL)


def enqueue_title_sync(db: sqlite3.Connection, node_id: str, new_title: str) -> None:
    """Insert a pending title-propagation job for *node_id*, idempotently.

    Idempotency contract: at most ONE pending (``processed = 0``) job per
    ``entity_id``. A rename that happens while an earlier rename is still
    queued doesn't need a second job — the drain step re-reads the current
    name at processing time, so the newest title always wins.

    The check is a SELECT-then-INSERT rather than ``INSERT OR IGNORE``:
    every call mints a fresh UUID primary key, so there is never a key
    collision for OR IGNORE to suppress. The "one pending job per entity"
    rule is not expressible as a UNIQUE constraint on this table — it has
    to be enforced by the query.

    Commits before returning so the job survives the connection closing
    (the watcher process and the drain worker may not share a connection).
    """
    _ensure_table(db)
    (pending,) = db.execute(
        "SELECT COUNT(*) FROM sync_queue WHERE entity_id = ? AND processed = 0",
        (node_id,),
    ).fetchone()
    if pending:
        return

    db.execute(
        "INSERT INTO sync_queue (id, entity_id, new_name, processed) VALUES (?, ?, ?, 0)",
        (str(uuid4()), node_id, new_title),
    )
    db.commit()


def pending_sync_jobs(db: sqlite3.Connection, limit: int = 50) -> list[dict[str, Any]]:
    """Return up to *limit* unprocessed jobs, oldest first, as plain dicts.

    Called by ``SyncWorker.drain()`` (Phase 4) to fetch its work batch. The
    ``LIMIT`` bounds startup work when many renames accumulated while the
    process was down; ``ORDER BY created_at ASC`` drains in FIFO order.

    Rows come back as ``{"id", "entity_id", "new_name", "processed",
    "created_at"}`` dicts regardless of the connection's ``row_factory`` —
    the column names are read from ``cursor.description`` so a bare
    ``sqlite3.Connection`` works unmodified.
    """
    _ensure_table(db)
    cursor = db.execute(
        "SELECT * FROM sync_queue WHERE processed = 0 ORDER BY created_at ASC LIMIT ?",
        (limit,),
    )
    columns = [description[0] for description in cursor.description]
    return [dict(zip(columns, row, strict=True)) for row in cursor.fetchall()]


def mark_processed(db: sqlite3.Connection, job_id: str) -> None:
    """Flip a job's ``processed`` flag to 1 so the queue stops returning it.

    Flagging (instead of DELETE) keeps an audit trail of completed work and
    makes the worker crash-safe: re-processing an already-processed job is a
    harmless no-op, so the drain loop never has to be transactional across
    file writes. Commits so other connections see the flip immediately.
    """
    _ensure_table(db)
    db.execute("UPDATE sync_queue SET processed = 1 WHERE id = ?", (job_id,))
    db.commit()
