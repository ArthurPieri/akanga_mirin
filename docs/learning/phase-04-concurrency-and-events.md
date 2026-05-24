# Phase 4 — Concurrency and Events

**Core concept:** A running Akanga process has multiple things happening simultaneously
— the file watcher fires when you save a note, the active manager pings URLs on a
schedule, the API handles a request, and the TUI renders. These components run in
different concurrency models and cannot call each other directly. Phase 4 is about
wiring them together safely without deadlocks, missed events, or blocked UIs.

---

## Concepts

### File Watching

Operating systems expose APIs for monitoring filesystem changes: `inotify` on Linux,
`FSEvents` on macOS, `ReadDirectoryChangesW` on Windows. The `watchdog` library
abstracts these into a single Python API. When a file changes, a callback fires — but
"a file changes" can mean dozens of OS events per second during a single save (modify,
close_write, attribute change). The watcher must be selective about what it acts on
and when, or it floods downstream components with redundant work.

> Akanga node: `File Watching`

### Debouncing

Coalescing a burst of rapid events into a single action taken after the burst settles.
When you save a file in nvim, the OS fires 5–10 events within 50 milliseconds. Without
debouncing, the indexer re-indexes the same file 10 times per save, wasting CPU and
triggering 10 git commits. The debounce pattern: on each event, reset a timer to fire
in N ms. Only when the timer actually fires (no new events within N ms) does the
action execute. Akanga uses 500ms — fast enough to feel live, slow enough to coalesce
rapid saves.

> Akanga node: `Debouncing`

### Threads vs asyncio

Two distinct concurrency models in Python. Threads run OS-managed execution contexts
that can run in parallel (limited by the GIL for CPU-bound work, effective for
I/O-bound work). `asyncio` runs coroutines cooperatively in a single thread — a
coroutine yields control explicitly with `await`, letting others run. The file watcher
(watchdog) runs in a daemon thread using blocking OS callbacks. The active manager and
API server run in asyncio. These two models cannot directly call each other — a thread
cannot `await` a coroutine, and a coroutine cannot block on a thread without stalling
the whole loop. A bridge is required.

> Akanga node: `Threads vs asyncio`

### Event Bus (pub/sub)

A publish/subscribe message bus where publishers emit named events without knowing who
listens, and subscribers register handlers for event types they care about. Decouples
components: the file watcher publishes `file_changed` without knowing whether the
indexer, TUI, or git manager will handle it. Each subscriber registers independently.
Subscriber errors are isolated — one failing handler doesn't crash the bus or prevent
other subscribers from running. The event bus is the nervous system of the application.

> Akanga node: `Event Bus`

### `run_coroutine_threadsafe`

The standard Python bridge between a daemon thread and an asyncio event loop.
`asyncio.run_coroutine_threadsafe(coro, loop)` schedules a coroutine onto the asyncio
loop from any thread, returning a `concurrent.futures.Future`. The EventBus uses this
internally: when `publish()` is called from a watchdog daemon thread, async subscribers
are scheduled onto the asyncio loop rather than called directly (which would violate
asyncio's single-thread contract and likely crash).

> Akanga node: `run_coroutine_threadsafe`

### Sync Queue Drain

The mechanism that executes the lazy work enqueued in Phase 1. The drain worker reads
pending jobs from `sync_queue`, processes each (reads the affected file, updates the
stale display-name field, writes atomically), and marks it processed. Three job types:
`node_title` (update `target` field in edges), `workspace_name` (update `name` in
graph entries), `relation_name` (update `relation` in edges). Triggered on TUI open,
specific node opened, explicit sync command, or background schedule. The `limit`
parameter caps work per drain call so startup time stays bounded regardless of queue
depth.

> Akanga node: `Sync Queue Drain`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `File Watching` | note | `uses` → `watchdog`; `enables` → `Auto Re-index`; `has_prerequisite` → `Debouncing` |
| `Debouncing` | note | `solves` → `Event Burst`; `is_applied_in` → `File Watcher`; `is_applied_in` → `Git Auto-Commit` |
| `Threads vs asyncio` | note | `contrasts_with` → `asyncio`; `motivates` → `run_coroutine_threadsafe` |
| `Event Bus` | note | `is_a` → `Pub/Sub Pattern`; `enables` → `Component Decoupling`; `is_applied_in` → `Akanga App` |
| `run_coroutine_threadsafe` | note | `solves` → `Thread-to-asyncio Bridge`; `is_part_of` → `Python asyncio`; `is_applied_in` → `Event Bus` |
| `Sync Queue Drain` | note | `implements` → `Eventual Consistency`; `consumes` → `Background Sync Queue`; `uses` → `Atomic Write` |
| `watchdog` | reference | `implements` → `File Watching`; `is_applied_in` → `Akanga Watcher` |

---

## What You Build

**`watcher.py`** — `VaultWatcher`:

```python
class VaultWatcher:
    def __init__(self, vault: Path, eventbus: EventBus, debounce_ms: int = 500): ...
    def start(self): ...   # launches watchdog observer daemon thread
    def stop(self):  ...   # stops observer, joins thread
```

Rules:
- Ignores hidden directories (`.git/`, `.akanga/`)
- Ignores editor temp files (`.swp`, `.tmp`, `~`-suffixed)
- Debounces per file path — rapid saves to the same file coalesce into one event
- On settled change: publishes `file_changed(path)` to eventbus
- On delete: publishes `file_deleted(path)` to eventbus

**`eventbus.py`** — `EventBus`:

```python
class EventBus:
    def subscribe(self, event: str, handler: Callable): ...
    def unsubscribe(self, event: str, handler: Callable): ...
    def publish(self, event: str, **kwargs): ...
    def set_loop(self, loop: asyncio.AbstractEventLoop): ...
```

- `publish()` called from non-asyncio thread → uses `run_coroutine_threadsafe`
- Subscriber errors are caught and logged, never re-raised
- `unsubscribe()` is safe to call from any thread

Events in Phase 4:

| Event | Publisher | Payload |
|---|---|---|
| `file_changed` | watcher | `path: Path` |
| `file_deleted` | watcher | `path: Path` |
| `node_updated` | indexer (subscriber to file_changed) | `node_id: str` |
| `node_deleted` | indexer (subscriber to file_deleted) | `node_id: str` |

**`sync_worker.py`** — `SyncWorker`:

```python
class SyncWorker:
    def drain(self, db: GraphDatabase, vault: Path, limit: int = 50): ...
```

Per job type:
- `node_title`: find all files where `edges[].target_id == entity_id`, update
  `target` to `new_name`, write atomically
- `workspace_name`: find all files where `graph[].id == entity_id`, update `name`
  to `new_name`, write atomically
- `relation_name`: find all files where `edges[].relation_id == entity_id`, update
  `relation` to `new_name`, write atomically

**`app.py`** — `AkangaApp` startup sequence:

```
1. load_vault_config  → populate DB config tables
2. index_vault        → two-pass; DB fully populated
3. sync_worker.drain  → resolve stale display names
4. watcher.start      → begin watching for changes

on file_changed:
  indexer.index_file(path, db)       → re-index
  git_manager.stage_and_commit()     → debounced 5s (Phase 8)
  eventbus.publish('node_updated')   → TUI refreshes (Phase 5)
```

---

## Deliverable

```python
def test_watcher_fires_on_save(tmp_path):
    events = []
    bus = EventBus()
    bus.subscribe("file_changed", lambda path: events.append(path))
    watcher = VaultWatcher(tmp_path, bus, debounce_ms=50)
    watcher.start()
    (tmp_path / "test.md").write_text("hello")
    time.sleep(0.2)
    watcher.stop()
    assert len(events) == 1

def test_watcher_debounces_rapid_saves(tmp_path):
    events = []
    bus = EventBus()
    bus.subscribe("file_changed", lambda path: events.append(path))
    watcher = VaultWatcher(tmp_path, bus, debounce_ms=200)
    watcher.start()
    for i in range(10):
        (tmp_path / "test.md").write_text(f"save {i}")
    time.sleep(0.5)
    watcher.stop()
    assert len(events) == 1   # 10 saves → 1 event

def test_watcher_ignores_temp_files(tmp_path):
    events = []
    bus = EventBus()
    bus.subscribe("file_changed", lambda path: events.append(path))
    watcher = VaultWatcher(tmp_path, bus, debounce_ms=50)
    watcher.start()
    (tmp_path / ".test.md.swp").write_text("vim temp")
    time.sleep(0.2)
    watcher.stop()
    assert len(events) == 0

def test_subscriber_error_isolation():
    bus = EventBus()
    results = []
    def bad_handler(**kwargs): raise RuntimeError("boom")
    def good_handler(**kwargs): results.append(True)
    bus.subscribe("test", bad_handler)
    bus.subscribe("test", good_handler)
    bus.publish("test")   # must not raise
    assert results == [True]

def test_sync_queue_drain_node_title(tmp_path):
    # Node A has edge to B (target="Old Title", target_id=B.id).
    # B is renamed to "New Title" → job enqueued.
    # After drain(), A's frontmatter reads: target: "New Title".
    ...
```

Plus 7 vault nodes with typed edges. The debounce test proves that rapid saves don't
flood the indexer — the main performance guarantee of this phase.
