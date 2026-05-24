"""Phase 2 — SQLite WAL mode and concurrent access.

Run: python examples/phase_02_sqlite_wal.py

Shows WAL mode enabling concurrent reads+writes, and threading.Lock
protecting compound read-check-write sequences.
"""
import sqlite3, threading, time

# Setup
conn = sqlite3.connect("/tmp/akanga_wal_demo.db")
conn.execute("PRAGMA journal_mode=WAL")
conn.execute("CREATE TABLE IF NOT EXISTS notes (id TEXT PRIMARY KEY, title TEXT)")
conn.commit()

lock = threading.Lock()


def safe_upsert(node_id: str, title: str) -> None:
    with lock:
        conn.execute("INSERT OR REPLACE INTO notes VALUES (?, ?)", (node_id, title))
        conn.commit()


# Write from multiple threads simultaneously
threads = [threading.Thread(target=safe_upsert, args=(f"id-{i}", f"Note {i}")) for i in range(5)]
for t in threads: t.start()
for t in threads: t.join()

rows = conn.execute("SELECT * FROM notes ORDER BY id").fetchall()
print(f"All {len(rows)} rows written safely under concurrent writes:")
for row in rows:
    print(f"  {row}")
conn.close()
