# Phase 04 — Concurrency and Events

## Goal

Wire the knowledge graph components together using a thread-safe event bus
and a filesystem watcher that debounces rapid OS events into clean
`file_changed` / `file_deleted` signals.

## What you will build

| File | Purpose |
|---|---|
| `src/akanga_core/eventbus.py` | Thread-safe pub/sub bus; dispatches async handlers via `run_coroutine_threadsafe`; buffers async dispatches that arrive before `set_loop()` |
| `src/akanga_core/watcher.py` | Watchdog-based vault monitor; per-path debounce fired by a single worker thread |
| `src/akanga_core/sync_worker.py` | Drain queue of rename-propagation jobs; patch stale edge labels on disk |

The remaining `akanga_core` files (`parser.py`, `models.py`, `db.py`,
`indexer.py`, `links.py`, `sync_queue.py`) are carry-forward markers — copy
your Phase 01/02 solutions into them, or set `AKANGA_SRC` to your cumulative
`src/` directory. Each marker lists the functions this phase expects.

## Key concepts

### EventBus
- **Decoupling**: publishers (`VaultWatcher`) never import subscribers (indexer, TUI).
- **Thread safety**: `subscribe`/`unsubscribe` are guarded by `threading.Lock`.
- **Async dispatch**: coroutine handlers are scheduled ONLY via
  `asyncio.run_coroutine_threadsafe()` — never `asyncio.ensure_future()` (or a
  direct call) from a non-asyncio thread.
- **Startup buffering (BUG-04)**: `publish()` before `set_loop()` buffers async
  dispatches into a deque; `set_loop()` drains it. The direct-call fallback
  exists only for sync handlers.
- **Error isolation**: wrap every handler call in `try/except`; log but never
  re-raise. Attach a done-callback to every `run_coroutine_threadsafe` Future
  that logs its exception — un-retrieved Futures swallow errors silently.

### VaultWatcher
- **Debounce**: an editor save triggers 5–10 OS events in ~50 ms.  Record a
  fire-time per path in `_pending`; ONE background worker thread
  (`_worker_loop`) polls and fires expired entries.  Never create a
  `threading.Timer` per path — bulk operations (git checkout) would exhaust
  threads.
- **Ignore list**: filter `.swp`, `.swo`, `.tmp`, `~` suffixes; any path component
  starting with `.` (hides `.git/`, `.obsidian/`); non-`.md` extensions.
- **Daemon threads**: set `observer.daemon = True` and run the worker thread
  with `daemon=True` so they do not block process exit; `stop()` must still
  set `_stop_event` and `join()` the worker.
- **on_moved**: treat as delete-old + create-new.

### SyncWorker
- Processes jobs from a `title_sync_queue` table written by the indexer
  when a node title changes.
- Walks the vault on each `drain()` call — designed for low-frequency use.
- Atomic file writes: read → modify in memory → `write_node_file()`.

## Running the tests

```bash
PYTHONPATH=src pytest tests/phase_04/ -v
```

## Suggested order

1. Implement `EventBus` (no external dependencies).
2. Implement `VaultWatcher` — test by printing events.
3. Wire them together: watcher publishes → eventbus → indexer subscribes.
4. Implement `SyncWorker.drain()` last (requires a working DB and parser).
