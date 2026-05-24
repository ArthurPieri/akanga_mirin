# Phase 04 — Concurrency and Events

## Goal

Wire the knowledge graph components together using a thread-safe event bus
and a filesystem watcher that debounces rapid OS events into clean
`file_changed` / `file_deleted` signals.

## What you will build

| File | Purpose |
|---|---|
| `src/akanga_core/eventbus.py` | Thread-safe pub/sub bus; dispatches async handlers via `run_coroutine_threadsafe` |
| `src/akanga_core/watcher.py` | Watchdog-based vault monitor with per-path debounce timers |
| `src/akanga_core/sync_worker.py` | Drain queue of rename-propagation jobs; patch stale edge labels on disk |

## Key concepts

### EventBus
- **Decoupling**: publishers (`VaultWatcher`) never import subscribers (indexer, TUI).
- **Thread safety**: `subscribe`/`unsubscribe` are guarded by `threading.Lock`.
- **Async dispatch**: if a handler is a coroutine function and `set_loop()` was called,
  use `asyncio.run_coroutine_threadsafe()` — never `asyncio.ensure_future()` from a
  non-asyncio thread.
- **Error isolation**: wrap every handler call in `try/except`; log but never re-raise.

### VaultWatcher
- **Debounce**: an editor save triggers 5–10 OS events in ~50 ms.  Use one
  `threading.Timer` per path, resetting it on each new event.
- **Ignore list**: filter `.swp`, `.swo`, `.tmp`, `~` suffixes; any path component
  starting with `.` (hides `.git/`, `.obsidian/`); non-`.md` extensions.
- **Daemon threads**: set `observer.daemon = True` and `timer.daemon = True`
  so they do not block process exit.
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
