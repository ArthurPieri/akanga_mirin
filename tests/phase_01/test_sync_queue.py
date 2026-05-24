"""Phase 01 tests — Sync queue (Phase 1B).

Tests the learner's sync_queue module, which must live at AKANGA_SRC/sync_queue.py
(or AKANGA_SRC/akanga_core/sync_queue.py).  The module must export:

    enqueue_title_sync(db, node_id, new_title) -> None
    pending_sync_jobs(db) -> list[dict]
    mark_processed(db, job_id) -> None

The sync_queue table schema (authoritative from Phase 02 DB_SCHEMA):
    id           TEXT PRIMARY KEY
    entity_id    TEXT NOT NULL
    new_name     TEXT NOT NULL
    processed    INTEGER NOT NULL DEFAULT 0  (0 = pending, 1 = done)
    created_at   TEXT NOT NULL DEFAULT (datetime('now'))

All tests receive a ``tmp_db`` fixture (a sqlite3.Connection with the table
pre-created) from conftest.py.  A separate ``tmp_path``-based test verifies
persistence across connection re-opens.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from tests.phase_01.conftest import _load_sync_queue


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_enqueue_creates_row(tmp_db):
    """enqueue_title_sync inserts exactly one row into sync_queue."""
    m = _load_sync_queue()

    m.enqueue_title_sync(tmp_db, node_id="node-001", new_title="New Title")

    rows = tmp_db.execute("SELECT * FROM sync_queue").fetchall()
    assert len(rows) == 1, (
        f"Expected 1 row in sync_queue after enqueue_title_sync, got {len(rows)}."
    )


def test_enqueue_is_idempotent(tmp_db):
    """Calling enqueue_title_sync twice with the same node_id creates only one pending row."""
    m = _load_sync_queue()

    m.enqueue_title_sync(tmp_db, node_id="node-001", new_title="Title A")
    m.enqueue_title_sync(tmp_db, node_id="node-001", new_title="Title A")

    rows = tmp_db.execute(
        "SELECT * FROM sync_queue WHERE entity_id = ? AND processed = 0",
        ("node-001",),
    ).fetchall()
    assert len(rows) == 1, (
        f"Expected only 1 pending row for the same node_id, got {len(rows)}.\n"
        "enqueue_title_sync must be idempotent: do not insert a duplicate pending job."
    )


def test_pending_jobs_returns_unprocessed(tmp_db):
    """pending_sync_jobs returns only rows where processed = 0."""
    m = _load_sync_queue()

    m.enqueue_title_sync(tmp_db, node_id="node-001", new_title="Alpha")
    m.enqueue_title_sync(tmp_db, node_id="node-002", new_title="Beta")

    # Manually mark node-002 as processed so we have one pending and one done.
    tmp_db.execute(
        "UPDATE sync_queue SET processed = 1 WHERE entity_id = ?",
        ("node-002",),
    )
    tmp_db.commit()

    pending = m.pending_sync_jobs(tmp_db)
    assert len(pending) == 1, (
        f"Expected 1 pending job, got {len(pending)}.\n"
        "pending_sync_jobs must filter out rows where processed = 1."
    )


def test_mark_processed_sets_flag(tmp_db):
    """mark_processed sets processed to 1."""
    m = _load_sync_queue()

    m.enqueue_title_sync(tmp_db, node_id="node-001", new_title="Alpha")

    # Retrieve the job id so we can mark it processed.
    row = tmp_db.execute("SELECT id FROM sync_queue WHERE entity_id = ?", ("node-001",)).fetchone()
    assert row is not None, "Precondition: enqueue_title_sync must have inserted a row."
    job_id = row[0]

    m.mark_processed(tmp_db, job_id)

    updated = tmp_db.execute(
        "SELECT processed FROM sync_queue WHERE id = ?", (job_id,)
    ).fetchone()
    assert updated is not None and updated[0] == 1, (
        f"Expected processed=1 after mark_processed, got: {updated}.\n"
        "mark_processed must UPDATE sync_queue SET processed = 1 WHERE id = ?."
    )


def test_sync_queue_survives_restart(tmp_path: Path):
    """Jobs enqueued in one DB session are visible after reopening the DB."""
    m = _load_sync_queue()

    db_file = str(tmp_path / "restart.db")

    # Session 1: open, create table, enqueue a job, close.
    conn1 = sqlite3.connect(db_file)
    conn1.execute("""
        CREATE TABLE IF NOT EXISTS sync_queue (
            id TEXT PRIMARY KEY,
            entity_id TEXT NOT NULL,
            new_name TEXT NOT NULL,
            processed INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn1.commit()
    m.enqueue_title_sync(conn1, node_id="node-persist", new_title="Persisted")
    conn1.close()

    # Session 2: reopen and verify the job is still there.
    conn2 = sqlite3.connect(db_file)
    rows = conn2.execute(
        "SELECT * FROM sync_queue WHERE entity_id = ?", ("node-persist",)
    ).fetchall()
    conn2.close()

    assert len(rows) == 1, (
        f"Expected the enqueued job to persist after reopening the DB, but found {len(rows)} rows.\n"
        "Make sure enqueue_title_sync commits the transaction."
    )
