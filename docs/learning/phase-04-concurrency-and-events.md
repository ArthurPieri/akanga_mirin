# Phase 4 — Concurrency and Events

**Core concept:** A running Akanga process has multiple things happening simultaneously
— the file watcher fires when you save a note, the active manager pings URLs on a
schedule, the API handles a request, and the TUI renders. These components run in
different concurrency models and cannot call each other directly. Phase 4 is about
wiring them together safely without deadlocks, missed events, or blocked UIs.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Explain why threads and asyncio cannot call each other directly and how `run_coroutine_threadsafe` bridges them
- Implement a debounced file watcher using watchdog that coalesces rapid saves into single events
- Implement a thread-safe pub/sub EventBus with subscriber error isolation
- Wire the watcher, EventBus, and indexer together in an application startup sequence

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the linked foundation doc before proceeding.

- [ ] I understand the difference between threads and async/await → See `docs/foundations/python-threading.md`
- [ ] I know what an asyncio event loop is → See `docs/foundations/asyncio-primer.md`
- [ ] I understand threading.Lock and thread safety → See `docs/foundations/python-threading.md`
- [ ] I know what a timer is and how threading.Timer works → See `docs/foundations/python-threading.md`
- [ ] I've completed Phases 0–3

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

→ Foundation doc: `docs/foundations/python-threading.md`

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

→ Foundation doc: `docs/foundations/asyncio-primer.md`

### Event Bus (pub/sub)

A publish/subscribe message bus where publishers emit named events without knowing who
listens, and subscribers register handlers for event types they care about. Decouples
components: the file watcher publishes `file_changed` without knowing whether the
indexer, TUI, or git manager will handle it. Each subscriber registers independently.
Subscriber errors are isolated — one failing handler doesn't crash the bus or prevent
other subscribers from running. The event bus is the nervous system of the application.

> Akanga node: `Event Bus`

→ Foundation doc: `docs/foundations/design-patterns.md` (Observer pattern section)

### `run_coroutine_threadsafe`

The standard Python bridge between a daemon thread and an asyncio event loop.
`asyncio.run_coroutine_threadsafe(coro, loop)` schedules a coroutine onto the asyncio
loop from any thread, returning a `concurrent.futures.Future`. The EventBus uses this
internally: when `publish()` is called from a watchdog daemon thread, async subscribers
are scheduled onto the asyncio loop rather than called directly (which would violate
asyncio's single-thread contract and likely crash).

> Akanga node: `run_coroutine_threadsafe`

→ Foundation doc: `docs/foundations/asyncio-primer.md`

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
  git_manager.stage_and_commit()     → debounced 5s (Phase 7)
  eventbus.publish('node_updated')   → TUI refreshes (Phase 5)
```

---

## Common Pitfalls

**Calling async from a thread directly:** `await handler()` inside a watchdog callback will fail — watchdog runs in a non-asyncio thread. Use `asyncio.run_coroutine_threadsafe(handler(), loop)` or make the handler sync.

**Global debounce timer instead of per-path:** If you use one timer for all paths, a save to `a.md` resets the timer for `b.md`. Use `dict[path → Timer]` with lock protection.

**Re-raising subscriber exceptions:** If an EventBus subscriber raises and you let it propagate, all subsequent subscribers for that event are skipped. Always `try/except` per handler.

**Forgetting timer.daemon = True:** A non-daemon timer thread keeps the process alive after the main thread exits. Always set `timer.daemon = True` before `timer.start()`.

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

---

## Logging and Debugging

**Estimated time:** 30 minutes. Skip this section and return to it when you first need
to diagnose a problem.

Phase 4 is where Akanga becomes multi-component: the watcher fires from a daemon
thread, the EventBus dispatches to async subscribers, the indexer re-runs on every
file change. When something goes wrong — an event is dropped, a file change does not
propagate, a subscriber raises silently — the only tool you have is logging.

> Full reference: `docs/observability-module.md`. This section covers only the
> Akanga-specific wiring.

### Step 1 — Get a logger in every module

Every source file should declare a module-level logger. Never use `print()`.

```python
# At the top of watcher.py, eventbus.py, indexer.py, app.py
import logging
logger = logging.getLogger(__name__)
# __name__ is "akanga_core.watcher", "akanga_core.eventbus", etc.
# Every log line will carry its source — you always know where it came from.
```

### Step 2 — Configure logging in `cli.py` once, at startup

```python
# In cli.py — called at the start of each @app.command() handler
import logging
import sys

def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
```

Call `configure_logging(verbose)` as the very first line inside each CLI command
handler, before any other imports or setup. All module loggers automatically inherit
from the root logger configured here.

### Step 3 — Add `--verbose` to every CLI command

```python
import typer
from typing import Annotated

VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable DEBUG-level logging."),
]

@app.command()
def serve(
    vault: str = "./vault",
    db: str = "./.akanga.db",
    verbose: VerboseOption = False,
):
    configure_logging(verbose)
    ...
```

Run with `uv run python -m akanga_core.cli serve --verbose` to see every DEBUG log
from every module. Without `--verbose`, only INFO and above appear.

### Step 4 — Wire an EventBus debug subscriber

When events are not propagating as expected, attach a debug subscriber at startup
that logs every event:

```python
# In app.py, inside start_all(), after eventbus is initialized:
if verbose:
    _attach_debug_subscriber(eventbus)

def _attach_debug_subscriber(bus: EventBus) -> None:
    """Attach a logging subscriber to every known event type.
    Only called when --verbose is active — not in production."""
    debug_logger = logging.getLogger("eventbus.debug")
    known_events = ["file_changed", "file_deleted", "node_updated", "node_deleted"]

    def make_handler(name):
        def handler(**kwargs):
            debug_logger.debug("EVENT %s payload=%s", name, kwargs)
        return handler

    for event_name in known_events:
        bus.subscribe(event_name, make_handler(event_name))
```

With `--verbose`, every event that passes through the bus now appears in your logs.
You can immediately see whether a file-change event was published, and whether the
indexer subscriber received it.

### Step 5 — Log subscriber errors explicitly

The EventBus swallows subscriber exceptions to preserve error isolation. Make sure
those swallowed errors are logged:

```python
# In eventbus.py, inside the dispatch loop:
for handler in handlers:
    try:
        handler(**kwargs)
    except Exception:
        logger.exception(
            "Subscriber %s raised on event %s — continuing dispatch",
            handler.__qualname__,
            event,
        )
```

`logger.exception()` logs at ERROR level and automatically appends the full traceback.
This is the single most important logging line in the EventBus — without it, subscriber
crashes are invisible.

### Common Debugging Patterns

**"The TUI is not updating after I save a file."**

With `--verbose`, look for:
1. `EVENT file_changed` — did the watcher fire? If not, check the debounce setting
   and that the file is not hidden.
2. `EVENT node_updated` — did the indexer subscriber handle it? If not, check that
   the indexer is subscribed.
3. A `Subscriber ... raised` ERROR — did the TUI subscriber crash silently?

**"A file change is being indexed 10 times."**

Look for 10 `EVENT file_changed` lines for the same path within 500ms. The debounce
is not working. Check that `VaultWatcher` is using a per-path timer, not a global one.

**"The watcher never fires."**

Add a DEBUG log inside the `on_modified` callback before the debounce logic. If that
log never appears, the OS is not delivering events — check that the vault path exists
and is not a symlink (watchdog on macOS can have issues with symlinked dirs).

### Relation to the Full Observability Module

This section wires logging into Phase 4 specifically. The full observability module
(`docs/observability-module.md`) covers: structured JSON logs, timing decorators for
sync and async functions, SQLite slow-query detection, in-memory metrics, and
structured health endpoints. Return to it when you build the REST API (Phase 6) and
the MCP server (Phase 8) — git specifically is Phase 7.

---

## Reflect

> **Solo:** Draw a timeline diagram showing: a file save event → OS notification → watchdog callback → debounce timer → EventBus publish → indexer subscriber → `node_updated` event. Where do thread boundaries occur?

> **Group:** What would happen if two files changed simultaneously during the debounce window? Would both trigger separate events, or could they interfere? Walk through the per-path timer design together.
