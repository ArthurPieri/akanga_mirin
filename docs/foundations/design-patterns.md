# Design Patterns in Akanga

This document explains the software design patterns used in the Akanga knowledge graph. You will encounter all of these patterns as you work through Phases 0–8. Understanding the pattern before you write the code makes the "why" of each design decision legible.

---

## Why this document exists

Akanga is not just a knowledge graph — it is a worked example of how production Python systems are structured. The patterns below are not academic; every one of them appears verbatim in the codebase, chosen because it solved a real problem.

---

## 1. Observer (Pub/Sub) — EventBus

**What it is:** Objects subscribe to named topics. When an event is published to a topic, all subscribers are notified without the publisher knowing who is listening.

**Where:** `eventbus.py` — `EventBus.publish()`, `EventBus.subscribe()`

**Why Akanga uses it:** The file watcher, the active node manager, the git manager, and the TUI all need to react when a vault file changes. If the watcher called each of these directly, every new feature would require modifying the watcher. With the EventBus, each new consumer subscribes independently; the watcher never changes.

```python
# Publisher — does not know who is listening
self.eventbus.publish("node_updated", {"path": path, "id": str(node.id)})

# Subscriber — registers independently
self.eventbus.subscribe("node_updated", self._active_mgr.on_node_updated)
```

**The thread-safety twist:** Watchdog (the file watcher library) runs callbacks on its own background thread. Async subscribers need to be called from the event loop thread. `run_coroutine_threadsafe()` bridges these two worlds — it submits a coroutine to the running asyncio event loop from a non-async thread. This is why `set_loop()` must be called before the watcher starts.

**Pattern name in GoF:** Observer. Also called Pub/Sub, Event Bus, Signal/Slot.

---

## 2. Debounce — Watcher and Git Manager

**What it is:** When an event fires multiple times in rapid succession, wait for a quiet period before acting. Cancel any pending action when a new event arrives.

**Where:** `watcher.py` — `_EventHandler._debounced()` and `app.py` — `AkangaApp._queue_commit()`

**Why Akanga uses it:** An editor like Neovim writes a file in multiple steps: create temp file, write content, rename to target. Without debouncing, the indexer would be called 3–5 times per save. The debounce coalesces these into one call, 500ms after the last write event.

The git auto-commit debounce is longer (5 seconds) — it coalesces all saves within a burst into one commit rather than creating a commit per keystroke.

```python
def _debounced(self, key: str, fn: Callable, path: str) -> None:
    with self._lock:
        existing = self._timers.pop(key, None)
        if existing:
            existing.cancel()          # cancel the previous pending call
        timer = threading.Timer(self._debounce_sec, fn, args=[path])
        self._timers[key] = timer
        timer.start()
```

**The threading invariant:** `_timers` is shared between the watchdog thread and timer callbacks. The `threading.Lock` ensures only one thread modifies the dict at a time. Forgetting the lock causes the timer to be cancelled after it already fired, or a new timer to be created that is immediately overwritten.

---

## 3. Repository — GraphDatabase

**What it is:** An object that encapsulates all database access behind a clean interface. Callers never write SQL; they call methods with domain terms.

**Where:** `db.py` — `GraphDatabase`

**Why Akanga uses it:** The indexer, server, TUI, and test suite all need to read and write nodes and edges. If each of these wrote raw SQL, a schema change (renaming a column, adding FTS5) would require hunting down every query in the codebase. The Repository pattern puts all SQL in one place; callers are insulated from the schema.

```python
# Callers use domain language
db.upsert_node(node)
db.get_neighbors(node_id, direction="both")
db.full_text_search("asyncio primer", limit=10)

# Not raw SQL scattered across the codebase
# cursor.execute("SELECT * FROM nodes WHERE ...")
```

**The thread-safety invariant:** SQLite connections are not thread-safe by default. `GraphDatabase` uses a `threading.Lock` around every write operation and opens with WAL mode, which allows concurrent reads. This is the correct pattern for a single-process server with multiple threads.

---

## 4. Atomic Write (Write-Replace)

**What it is:** Write new content to a temp file in the same directory as the target, then replace the target with the temp file using an OS-level atomic rename.

**Where:** `parser.py` — `write_node_file()`

**Why Akanga uses it:** If the process crashes mid-write to a Markdown file, a partial write would corrupt the file. `os.replace()` is guaranteed atomic by every POSIX OS — the old file is visible until the rename succeeds, and the new file is visible from that point forward. There is no moment when neither exists.

```python
fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(frontmatter.dumps(post))
    os.replace(tmp, path)     # atomic: old file → new file, no partial state
except BaseException:
    os.unlink(tmp)            # clean up the temp on failure
    raise
```

**The macOS side effect:** On macOS, `os.replace(src, dst)` generates a `FileMovedEvent` in the filesystem event stream (not `FileModifiedEvent`). The watcher's `on_moved` handler must check `dest_path` (the vault file) independently of `src_path` (the temp file) so it triggers re-indexing after every atomic write.

**Why `dir=dir_path`:** Using the same directory as the target ensures the rename is within one filesystem. A cross-filesystem rename is not atomic — it copies then deletes. `tempfile.mkstemp(dir=dir_path)` forces the temp file onto the same volume.

---

## 5. Facade — AkangaApp

**What it is:** A single object that provides a simplified interface to a complex subsystem made up of multiple collaborating objects.

**Where:** `app.py` — `AkangaApp`

**Why Akanga uses it:** The system has six subsystems: database, file watcher, event bus, active node manager, git manager, and indexer. The server and TUI would need to construct and wire all six themselves — including getting the startup order right, threading the eventbus loop before the watcher starts, and tearing down in the correct order on shutdown. `AkangaApp` encapsulates all of this. Callers call `start_all()` and `stop_all()`.

```python
# Caller sees one method
await app.start_all()

# AkangaApp wires everything in the right order
async def start_all(self) -> None:
    self.eventbus.set_loop(asyncio.get_running_loop())  # must be first
    self.start()          # init git → initial index → start watcher
    await self.start_active()  # starts asyncio health-check scheduler
```

**The ordering invariant:** `set_loop()` must be called before `start_watcher()`. If the watcher fires an event before the loop is set, the publish falls back to `asyncio.get_running_loop()` from a non-async thread — which raises `RuntimeError`. The Facade encodes this ordering rule so callers cannot get it wrong.

---

## 6. Dependency Injection — Passing db and eventbus

**What it is:** Instead of a component creating its own dependencies, the dependencies are passed in by the caller.

**Where:** Every manager in the codebase — `ActiveNodeManager(db, eventbus=...)`, `VaultWatcher(vault_path, on_change, on_delete)`, `AkangaApp(vault, db_path, git_sync)`

**Why Akanga uses it:** Unit tests need to substitute a real SQLite database with an in-memory one, or a real EventBus with a mock. If `ActiveNodeManager` created its own `GraphDatabase`, tests could not inject a temporary test database. Passing dependencies in makes components testable in isolation.

```python
# Test can inject a fresh in-memory db
db = GraphDatabase(":memory:")
manager = ActiveNodeManager(db, eventbus=EventBus())

# Production wires real components
app = AkangaApp(vault="./vault", db_path="./.akanga.db")
```

**Contrast with module-level singletons:** A common anti-pattern is `DB = GraphDatabase(settings.DB_PATH)` at module level. Module-level singletons are shared across all tests in a pytest session — one test's writes contaminate the next test's reads. Dependency injection solves this by making every test's dependencies independent.

---

## 7. Strategy — Active Node Action Types

**What it is:** Define a family of interchangeable algorithms (strategies) behind a common interface. The client picks which strategy to use at runtime without knowing how it works.

**Where:** `active.py` — HTTP and TCP health check actions, dispatched on `node.frontmatter["active"]["action"]`

**Why Akanga uses it:** Active nodes can check either an HTTP endpoint or a TCP port. Both produce a result (up/down + timestamp). The active manager does not need to know which kind it is handling — it calls the same `_check()` method and gets back the same result shape. Adding a new action type (e.g., CLI command) means adding a new branch, not rewriting the manager.

---

## 8. Two-Phase Commit (Index then Link)

**What it is:** Split a write operation into two sequential passes: first write all objects, then write all relationships between them.

**Where:** `indexer.py` — `full_scan_and_index()` — first pass indexes all nodes, second pass extracts and resolves edges

**Why Akanga uses it:** When resolving a wikilink `[[B]]` in node A, node B must already be in the database so its UUID can be retrieved. If both passes ran simultaneously, a node that appears early in the scan might link to a node that has not been indexed yet — the link resolution would fail or produce a dangling edge. The two-pass approach guarantees that all nodes exist before any edges are created.

---

## Summary Table

| Pattern | Where in codebase | Problem it solves |
|---|---|---|
| Observer (Pub/Sub) | `eventbus.py` | Decouple file watcher from all its consumers |
| Debounce | `watcher.py`, `app.py` | Coalesce rapid file events into one action |
| Repository | `db.py` | Centralize all SQL; insulate callers from schema |
| Atomic Write | `parser.py` | Crash-safe file writes with no partial state |
| Facade | `app.py` | Hide startup ordering complexity from callers |
| Dependency Injection | All managers | Enable isolated unit tests |
| Strategy | `active.py` | Swap health-check implementations without changing the manager |
| Two-Phase Commit | `indexer.py` | Ensure referenced nodes exist before creating edges |

---

## Further Reading

- GoF Design Patterns (Gang of Four) — Observer, Strategy, Facade chapters
- *Python Concurrency with asyncio* — `run_coroutine_threadsafe` and thread/loop bridging
- SQLite WAL mode documentation — why Repository + WAL enables concurrent reads
- Python `tempfile` module docs — `mkstemp` and why `dir=` matters for atomicity
