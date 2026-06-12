# Phase 4 — Concurrency and Events

**Estimated time:** 3–4 hours + ~1h vault/reflect

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
- [ ] I know how to run a loop in a background thread and stop it cleanly with a `threading.Event` → See `docs/foundations/python-threading.md`
- [ ] I've completed Phases 0, 1A, 1B, 2, and 3

---

## Quick Start

```bash
make skeleton PHASE=4    # copy the starting code into ./src/
make test PHASE=4        # run the tests (they will fail initially)
make study PHASE=4       # open the tmux study session
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### File Watching

Operating systems expose APIs for monitoring filesystem changes: `inotify` on Linux,
`FSEvents` on macOS, `ReadDirectoryChangesW` on Windows. The `watchdog` library
abstracts these into a single Python API. When a file changes, a callback fires — but
"a file changes" can mean dozens of OS events per second during a single save (modify,
close_write, attribute change). The watcher must be selective about what it acts on
and when, or it floods downstream components with redundant work.

> Akanga node: `File Watching`

> → Foundation doc: `docs/foundations/python-threading.md`

### Debouncing

Coalescing a burst of rapid events into a single action taken after the burst settles.
When you save a file in nvim, the OS fires 5–10 events within 50 milliseconds. Without
debouncing, the indexer re-indexes the same file 10 times per save, wasting CPU and
triggering 10 git commits. The debounce pattern: on each event, push the path's
*deadline* forward by N ms; only when the deadline passes with no new events does the
action execute. In Akanga this is one dictionary (`path → deadline`) polled by a
single worker thread — not one timer per path. Akanga uses 500ms — fast enough to
feel live, slow enough to coalesce rapid saves.

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

> → Foundation doc: `docs/foundations/asyncio-primer.md`

### Event Bus (pub/sub)

A publish/subscribe message bus where publishers emit named events without knowing who
listens, and subscribers register handlers for event types they care about. Decouples
components: the file watcher publishes `file_changed` without knowing whether the
indexer, TUI, or git manager will handle it. Each subscriber registers independently.
Subscriber errors are isolated — one failing handler doesn't crash the bus or prevent
other subscribers from running. The event bus is the nervous system of the application.

Two details make Akanga's bus robust rather than racy:

1. **Startup buffering.** If `publish()` is called for an async subscriber *before*
   `set_loop()` has registered the asyncio loop, the dispatch is not dropped and the
   handler is not called directly from the wrong thread (the startup-dispatch race).
   Instead the pending dispatch is appended to a `collections.deque` buffer;
   `set_loop()` drains that buffer onto the newly registered loop. Events published
   during startup are delayed, never lost.
2. **Async error visibility.** `run_coroutine_threadsafe` returns a
   `concurrent.futures.Future`. If nobody ever looks at that Future, exceptions raised
   inside async handlers vanish silently. The bus attaches a done-callback that logs
   `future.exception()` — the async half of the error-isolation invariant.

> Akanga node: `Event Bus`

> → Foundation doc: `docs/foundations/design-patterns.md` (Observer pattern section)

### `run_coroutine_threadsafe`

The standard Python bridge between a daemon thread and an asyncio event loop.
`asyncio.run_coroutine_threadsafe(coro, loop)` schedules a coroutine onto the asyncio
loop from any thread, returning a `concurrent.futures.Future`. The EventBus uses this
internally: when `publish()` is called from a watchdog daemon thread, async subscribers
are scheduled onto the asyncio loop rather than called directly (which would violate
asyncio's single-thread contract and likely crash). This is **the** bridge — the only
pattern Akanga sanctions for thread→asyncio dispatch. If you encounter
`call_soon_threadsafe` or a `create_task` lambda suggested for this job, use
`run_coroutine_threadsafe` instead: it is the only one of the three that accepts a
coroutine directly, works from any thread, and hands back a Future you can attach an
error-logging done-callback to.

> Akanga node: `run_coroutine_threadsafe`

> → Foundation doc: `docs/foundations/asyncio-primer.md`

### Sync Queue Drain

The mechanism that executes the lazy work enqueued in Phase 1B. The drain worker reads
pending jobs from `sync_queue`, processes each (reads the affected file, updates the
stale display-name field, writes atomically), and marks it processed. In this phase
there is exactly **one kind of job**: node-title propagation — a node was renamed, and
every file whose edges still reference it by the old display name must be patched to
`new_name`. Do **not** branch on a `job_type` field; the Phase 2 schema has no such
column (it is reserved for later extensions like workspace and relation renames).
Drain is triggered on TUI open, on a specific node being opened, on an explicit sync
command, or on a background schedule. The `limit` parameter caps work per drain call
so startup time stays bounded regardless of queue depth.

> Akanga node: `Sync Queue Drain`

### Dangling Edges

`file_deleted` → `node_deleted` removes a node's row from the DB — but every edge in
*other* files that points at the deleted UUID is still sitting in frontmatter Akanga
does not control. Those edges now **dangle**: their `target_id` resolves to nothing.

The policy is **mark, never auto-delete.** The indexer's `node_deleted` handler
enqueues a `dangling_edge` job into `sync_queue` for the deleted UUID — the first
real use of the reserved `job_type` column (introducing that column, with existing
rows defaulting to title-sync semantics, is part of this extension). The job
triggers no rewrite of the referencing files; it exists to make the dangle
*visible* — a queryable record that "edges pointing at X have been unresolved since
`created_at`." Note this is specced policy, not a Phase 4 deliverable: the drain
worker you build below still handles exactly one job kind (title propagation), and
nothing in `tests/phase_04/` exercises dangling-edge jobs.

Downstream consumers must tolerate missing targets rather than crash. Phase 8's RAG
serializer already does: `build_context`'s triple loop skips any edge whose endpoint
is not in the loaded node set (`if not (src and tgt): continue`). That drop is safe
but **silent** — the LLM never learns an edge was omitted — which is exactly why the
`dangling_edge` job row matters: it is the visible ledger of what the serializer
silently drops.

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `File Watching` | note | `uses` → `watchdog`; `enables` → `Auto Re-index`; `has_prerequisite` → `Debouncing` |
| `Debouncing` | note | `solves` → `Event Burst`; `is_applied_in` → `File Watcher`; `is_applied_in` → `Git Auto-Commit` |
| `Threads vs asyncio` | note | `contrasts_with` → `asyncio` |
| `Event Bus` | note | `subtype_of` → `Pub/Sub Pattern`; `enables` → `Component Decoupling`; `is_applied_in` → `Akanga App` |
| `run_coroutine_threadsafe` | note | `motivated_by` → `Threads vs asyncio`; `solves` → `Thread-to-asyncio Bridge`; `is_part_of` → `Python asyncio`; `is_applied_in` → `Event Bus` |
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
- Debounces per file path — rapid saves to the same file coalesce into one event.
  Implementation: one lock-protected `dict[path → deadline]` plus a **single polling
  worker thread** (see Common Pitfalls — not a Timer per path)
- **Re-touch postpones the fire**: every new event to a path pushes that path's
  deadline forward — the watcher must never fire early while writes are still
  arriving inside the window (tested by `test_retouch_inside_window_postpones_fire`)
- **Deletes get a create-cancels-delete grace window**: a delete is published only
  if it *stays* deleted — a create/move of the same path inside the window cancels
  the pending delete (real editors save by delete-then-rename; tested by
  `test_recreate_within_grace_window_cancels_pending_delete`)
- Handles `on_created`, `on_modified`, **and** `on_moved` — atomic writes via
  `os.replace` arrive as move events on macOS; use `event.dest_path` for moves
- On settled change: publishes `file_changed(path)` to eventbus
- On delete (after the grace window): publishes `file_deleted(path)` to eventbus
- `stop()` sets the worker's `threading.Event`, stops the watchdog observer, and
  joins the worker thread

**`eventbus.py`** — `EventBus`:

```python
class EventBus:
    def subscribe(self, event: str, handler: Callable): ...
    def unsubscribe(self, event: str, handler: Callable): ...
    def publish(self, event: str, **kwargs): ...
    def set_loop(self, loop: asyncio.AbstractEventLoop): ...
```

- `publish()` called from a non-asyncio thread → async handlers are scheduled with
  `run_coroutine_threadsafe(handler(**kwargs), self._loop)` — never called directly
- **Startup buffering:** if an async dispatch arrives before `set_loop()` has been
  called, append the pending `(handler, kwargs)` to a `collections.deque` instead of
  dropping it or calling the handler from the wrong thread; `set_loop(loop)` stores
  the loop and then drains the buffer onto it
- **Done-callback logging:** every Future returned by `run_coroutine_threadsafe` gets
  `future.add_done_callback(...)` that logs `future.exception()` if one occurred —
  async handler errors must be visible, not silently dropped with the Future
- Sync subscriber errors are caught and logged per handler, never re-raised
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
    def drain(self, db: GraphDatabase, vault: Path, limit: int = 50) -> int: ...
```

Every job in `sync_queue` has the same semantics — node-title propagation:

- Fetch pending jobs with `pending_sync_jobs(db, limit)` (rows where `processed = 0`,
  oldest first); each job carries `entity_id` (the renamed node's UUID) and `new_name`
- **Re-read current truth first (the Phase 1B convergence contract):** treat the
  job's `new_name` as a snapshot, not the value to apply — look up the node's
  *current* title by `entity_id` in the DB at processing time and write that. In
  the tests the two are always equal; in a live vault, only the re-read makes
  out-of-order and stale jobs converge
- Find all `.md` files where `edges[].target_id == entity_id`, update `target` to
  the current title, write atomically
- Mark each job done with `mark_processed(db, job["id"])` and return the count

There is no `job_type` column in the Phase 2 schema — do not branch on one. The
single-semantics design is deliberate: workspace renames, relation renames, and
dangling-edge marking (see the Dangling Edges concept above) are future extensions,
and the column is reserved until they exist.

**`app.py`** — `AkangaApp` startup sequence:

```
1. db = GraphDatabase(db_path)        → connection opens in __init__ (no db.connect() call)
   # TODO: load_vault_config(vault) — reads akanga.yaml; no skeleton implementation
   # exists yet (described in Phase 00 concepts). Add when implemented.
2. eventbus.set_loop(loop)            → register the running asyncio loop
                                        (loop = asyncio.get_running_loop() in async context)
3. full_scan_and_index(vault, db)     → two-pass; DB fully populated
4. sync_worker.drain(db, vault)       → resolve stale display names
5. watcher.start()                    → begin watching for changes

on file_changed:
  indexer.index_file(path, db)            → re-index
  git_manager.commit("auto: update node") → debounced 5s (Phase 7)
  eventbus.publish('node_updated')        → TUI refreshes (Phase 5)
```

**Ordering matters:** `set_loop` must run *before* `watcher.start()` — the moment the
watcher starts, its daemon thread can call `publish()`, and async subscribers can only
be scheduled if the bus already knows the loop (the startup buffer catches anything
published even earlier, but never rely on it as the normal path). Drain runs *before*
the watcher too, so its file rewrites don't fire change events mid-startup.

---

## Common Pitfalls

**Calling async from a thread directly:** `await handler()` inside a watchdog callback will fail — watchdog runs in a non-asyncio thread. Use `asyncio.run_coroutine_threadsafe(handler(), loop)` or make the handler sync.

**A `threading.Timer` per path — the thread-exhaustion trap:** the tempting debounce design is `dict[path → Timer]`, cancelling and recreating a Timer on every event. Every `Timer` is a full OS thread; an editor save burst, a git checkout, or a bulk edit spawns dozens of short-lived threads, and cancel/recreate races multiply under load. The correct design is a **single polling worker thread**: watchdog callbacks only update a lock-protected `dict[path → deadline]` (`time.monotonic() + debounce_ms/1000`, pushed forward on every event); one worker thread loops every ~25ms, pops entries whose deadline has passed, and publishes their events. One dict, one thread, no cancellation races — and per-path independence comes free, since each path has its own deadline (a save to `a.md` never delays `b.md`).

**No stop signal on the debounce worker:** the worker loop must check a `threading.Event` (e.g. `while not self._stop.is_set(): ...`). `stop()` sets the event, stops the watchdog observer, and `join()`s the worker. Also mark the worker `daemon=True` as a safety net — a non-daemon thread keeps the process alive after the main thread exits — but the daemon flag is the backstop, not the shutdown mechanism.

**Re-raising subscriber exceptions:** If an EventBus subscriber raises and you let it propagate, all subsequent subscribers for that event are skipped. Always `try/except` per handler — and for async handlers, attach the done-callback that logs `future.exception()`; otherwise the async half of your error isolation is theater.

**The self-write echo loop:** your own components write files too. `sync_worker.drain()` rewrites vault files → the watcher fires `file_changed` → the indexer re-indexes → (from Phase 7) git commits — potentially round and round. The natural damper is the **content-hash skip** from Phase 2: the indexer compares the file's `content_hash` against the stored one and skips re-indexing when nothing actually changed, which breaks the loop after one harmless cycle. Don't disable that check, and don't "fix" the loop by ignoring your own writes via timing hacks.

**macOS delivers atomic writes as `on_moved`:** `write_node_file()` writes a temp file and `os.replace()`s it over the target. On macOS (FSEvents), that replace often arrives as a *move* event, not a modify. If your handler only implements `on_modified`/`on_created`, saves will silently produce no events on macOS while passing on Linux. Handle `on_moved` too, treating `event.dest_path` as the changed file (and still applying the temp-file filters to it).

> **Sync services and real editors — write signatures your watcher will meet**
>
> Put the vault in Dropbox/iCloud/OneDrive, or edit it with vim, and the watcher
> sees patterns the happy path never shows:
>
> - **Conflict copies.** Dropbox resolves a sync conflict by writing a *second*
>   file (`note (conflicted copy).md`) that carries the **same frontmatter `id`**
>   — one identity, two paths. The indexer warns loudly on a duplicate id and
>   keeps the **oldest path**; resolving the conflict and deleting the copy is on
>   the human.
> - **iCloud eviction.** With "Optimize Mac Storage" on, iCloud can replace a
>   local file with a placeholder stub — the file "changes" with no edit, and the
>   body is gone until macOS re-downloads it. Don't index placeholder content as
>   the node's truth.
> - **vim rename-backups.** vim's default save strategy writes a backup and
>   renames over the target — so every save can arrive as a **`file_deleted` for
>   the real path** followed by a create/move. This is why the create-cancels-delete
>   grace window is a watcher Rule (see the Rules list above), not an edge case:
>   a delete event is not proof the note is gone — only a delete that **stays**
>   deleted is treated as real.

---

## Deliverable

The complete test suite lives in `tests/phase_04/` — three files.

**`test_eventbus.py`** — the bus contract:

- `test_subscribe_and_publish` — a subscribed handler fires on the matching event
- `test_publish_passes_kwargs` — `publish(path=..., extra=...)` reaches the handler unchanged
- `test_multiple_subscribers` — two subscribers to the same event both fire
- `test_multiple_events` — subscribing to `event_a` does not trigger on `event_b`
- `test_unsubscribe` — after unsubscribe, the handler no longer fires
- `test_unsubscribe_nonexistent_handler_is_safe` — unsubscribing an unknown handler must not raise
- `test_subscriber_error_isolation` — a raising handler doesn't stop later subscribers; `publish()` never raises
- `test_no_subscribers_publish_is_safe` — publishing with zero subscribers must not raise
- The `set_loop` / buffering tests — `test_async_subscriber_receives_event_after_set_loop`,
  `test_publish_before_set_loop_buffers_events`, and
  `test_publish_racing_set_loop_delivers_every_event_exactly_once`: `publish()` before
  `set_loop()` buffers async dispatches instead of dropping them; `set_loop(loop)`
  drains the buffer onto the loop; a publish racing `set_loop` delivers every event
  exactly once

**`test_watcher.py`** — debounced filesystem events:

- `test_watcher_fires_on_file_creation` / `test_watcher_fires_on_file_modification` /
  `test_watcher_fires_on_file_deletion` — the three basic event paths (note: the test
  helper writes files with `os.replace`, so your `on_moved` handling is exercised on macOS)
- `test_watcher_event_contains_path` — the payload includes a `path` key
- `test_watcher_debounces_rapid_saves` — 10 rapid writes to one file coalesce to 1–3 events
- `test_watcher_parallel_saves_not_debounced` — writes to *different* files are not merged
- `test_watcher_ignores_swp_files` / `test_watcher_ignores_tilde_files` /
  `test_watcher_ignores_hidden_dirs` — the filter rules
- `test_retouch_inside_window_postpones_fire` — **the re-touch contract**: a second
  write inside the debounce window pushes the deadline forward; the watcher must not
  fire early
- `test_recreate_within_grace_window_cancels_pending_delete` — **the delete grace
  window**: a delete followed by a recreate inside the window publishes no
  `file_deleted` (create cancels delete)
- `test_watcher_stop_and_start` — `start()` then `stop()` completes without raising
- `test_watcher_nonexistent_vault_raises` — a missing vault path raises in `__init__` or `start()`
- `test_async_subscriber_receives_event` — **the bridge test**: `publish()` from a
  non-asyncio thread reaches an async subscriber via `run_coroutine_threadsafe`

**`test_sync_worker.py`** — queue drain:

- `test_drain_processes_pending_jobs_and_marks_processed` — drain propagates a renamed
  node's `new_name` into the `target` field of every referencing file (written
  atomically), marks each job `processed = 1` via `mark_processed`, respects the
  `limit` cap, and returns the processed count
- `test_drain_with_empty_queue_returns_zero` — an empty queue drains to 0 without touching any file

The debounce test proves rapid saves don't flood the indexer — the main performance
guarantee of this phase. The async-subscriber test proves the bridge is wired
correctly — async handlers always run on the event loop, even when `publish()` is
called from a watchdog daemon thread. The buffering tests prove startup events
survive the window before `set_loop()`.

Plus 7 vault nodes with typed edges.

---

## Logging and Debugging

Phase 4 is where Akanga becomes multi-component: the watcher fires from a daemon
thread, the EventBus dispatches to async subscribers, the indexer re-runs on every
file change. When something goes wrong — an event is dropped, a file change does not
propagate, a subscriber raises silently — the only tool you have is logging.

> → Foundation doc: `docs/observability-module.md` (Observability & Debugging) —
> the five-step Akanga logging wiring (module loggers, `configure_logging`,
> `--verbose`, the EventBus debug subscriber, and explicit subscriber-error
> logging) lives in its "Applying This Module to Akanga" section. Wire it up
> there (~30 minutes), then use the patterns below to diagnose problems.

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
is not working. Check that the watchdog callback only *updates the deadline* in the
`path → deadline` dict and that the worker thread is the one publishing — if the
callback publishes directly, nothing is debounced.

**"The watcher never fires."**

Add a DEBUG log inside the `on_modified` callback before the debounce logic. If that
log never appears, the OS is not delivering events — check that the vault path exists
and is not a symlink (watchdog on macOS can have issues with symlinked dirs).

The full observability module also covers structured JSON logs, timing decorators,
SQLite slow-query detection, in-memory metrics, and structured health endpoints —
return to it when you build the REST API (Phase 6) and the MCP server (Phase 8).

---

## Reflect

> **Break it on purpose:** Remove the `eventbus.set_loop(loop)` call from your
> startup sequence. Before running anything, predict what happens to async
> subscribers when the watcher publishes. Then observe: do events error, drop
> silently, or buffer? Explain the buffering contract — where do pre-loop
> publishes go, what drains them, and what happens to those events if
> `set_loop` is *never* called? Put `set_loop` back when you're done.

> **Solo:** Draw a timeline diagram showing: a file save event → OS notification → watchdog callback → deadline updated → debounce worker fires → EventBus publish → indexer subscriber → `node_updated` event. Where do thread boundaries occur?

> **Solo:** When a node is deleted, edges pointing at its UUID dangle. Why is "mark, never auto-delete" the right policy — what goes wrong if the indexer deletes those edges from the referencing files, and the target later comes back (a file restored from the trash, a `git checkout` of an older branch)?

> **Group:** What would happen if two files changed simultaneously during the debounce window? Would both trigger separate events, or could they interfere? Walk through the single-worker design together: the `path → deadline` dict, the ~25ms polling loop, and the `threading.Event` stop signal. Then argue the other side — what would a Timer-per-path design cost during a 200-file git checkout?
