"""
Phase 04 — SyncWorker Tests

Tests for sync_worker.py:
    SyncWorker.drain(db, vault, limit=50) -> int

drain() reads pending rename-propagation jobs from the sync_queue table,
patches stale edge display names in the .md files on disk, writes the files
back atomically, and marks each job processed (doc Deliverable sketch:
test_sync_queue_drain_node_title).
"""
import sqlite3
from pathlib import Path
from textwrap import dedent

import yaml

from tests.phase_04.conftest import _load_db, _load_sync_queue, _load_sync_worker

_ID_A = "aaaa0400-0000-0000-0000-000000000001"
_ID_B = "bbbb0400-0000-0000-0000-000000000002"


def _read_frontmatter(path: Path) -> dict:
    """Parse just the YAML frontmatter of a .md file (no learner code involved)."""
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    assert len(parts) >= 3, f"File {path} has no frontmatter block: {text[:120]!r}"
    return yaml.safe_load(parts[1])


def _enqueue(sync_queue_mod, db, node_id: str, new_title: str) -> None:
    """Enqueue a title-sync job, accepting either a GraphDatabase or its raw conn."""
    try:
        sync_queue_mod.enqueue_title_sync(db, node_id=node_id, new_title=new_title)
    except (AttributeError, TypeError, sqlite3.Error):
        # Some implementations operate on the raw sqlite3.Connection instead.
        sync_queue_mod.enqueue_title_sync(db.conn, node_id=node_id, new_title=new_title)


def test_drain_processes_pending_jobs_and_marks_processed(tmp_vault: Path, tmp_path: Path):
    """drain() must patch stale edge display names on disk AND mark jobs processed.

    Scenario (doc Deliverable): node A has a frontmatter edge to B with
    target='Old Title'. B was renamed to 'New Title' and a job was enqueued.
    After drain(): A's file reads target: 'New Title' and the queue is empty.
    """
    GraphDatabase = _load_db()
    SyncWorker = _load_sync_worker()
    sq = _load_sync_queue()

    # Node A references B by its OLD display name.
    node_a = tmp_vault / "node-a.md"
    node_a.write_text(
        dedent(f"""\
            ---
            id: {_ID_A}
            title: Node A
            type: note
            tags: []
            edges:
              - relation: supports
                relation_id: EP-001
                target: Old Title
                target_id: {_ID_B}
            ---

            Body of A.
            """),
        encoding="utf-8",
    )
    # Node B already carries its NEW title on disk.
    node_b = tmp_vault / "node-b.md"
    node_b.write_text(
        dedent(f"""\
            ---
            id: {_ID_B}
            title: New Title
            type: note
            tags: []
            edges: []
            ---

            Body of B.
            """),
        encoding="utf-8",
    )

    db_path = str(tmp_path / "sync_worker_test.db")
    db = GraphDatabase(db_path)
    try:
        _enqueue(sq, db, node_id=_ID_B, new_title="New Title")

        worker = SyncWorker()
        processed = worker.drain(db, vault=tmp_vault, limit=50)

        assert processed == 1, (
            f"drain() must return the number of jobs processed (expected 1, "
            f"got {processed!r}).\n"
            "Fetch jobs with pending_sync_jobs(db, limit) and count each one "
            "you complete."
        )

        fm = _read_frontmatter(node_a)
        edges = fm.get("edges", [])
        assert edges and edges[0].get("target") == "New Title", (
            f"After drain(), node A's edge target must read 'New Title', "
            f"got: {edges!r}.\n"
            "Match edges by target_id == job['entity_id'], set "
            "edge['target'] = job['new_name'], and write the file back "
            "atomically with write_node_file()."
        )
        assert edges[0].get("target_id") == _ID_B, (
            "drain() must never touch target_id — the UUID is the stable key; "
            f"got: {edges[0]!r}."
        )
    finally:
        db.close()

    # The job must now be marked processed (processed = 1, row NOT deleted).
    conn = sqlite3.connect(db_path)
    pending = conn.execute(
        "SELECT COUNT(*) FROM sync_queue WHERE processed = 0"
    ).fetchone()[0]
    done = conn.execute(
        "SELECT COUNT(*) FROM sync_queue WHERE processed = 1"
    ).fetchone()[0]
    conn.close()
    assert pending == 0, (
        f"{pending} job(s) still pending after drain().\n"
        "Call mark_processed(db, job['id']) for every job you complete."
    )
    assert done == 1, (
        f"Expected exactly 1 processed row, got {done}.\n"
        "mark_processed sets processed = 1 — it does not delete the row."
    )


def test_drain_with_empty_queue_returns_zero(tmp_vault: Path, tmp_path: Path):
    """drain() on an empty queue must return 0 without touching any file."""
    GraphDatabase = _load_db()
    SyncWorker = _load_sync_worker()

    db_path = str(tmp_path / "empty_queue_test.db")
    db = GraphDatabase(db_path)
    try:
        worker = SyncWorker()
        processed = worker.drain(db, vault=tmp_vault, limit=50)
        assert processed == 0, (
            f"drain() with no pending jobs must return 0, got {processed!r}."
        )
    finally:
        db.close()
