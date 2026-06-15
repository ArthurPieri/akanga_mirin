# asyncio Primer

**Audience:** developers comfortable with Python functions who have read `python-threading.md` — this is the async half of Akanga's concurrency model · **Read time:** ~12 min

This doc covers the **async** half of akanga's concurrency model. Read `python-threading.md` first — the two models run side by side in the system you build and meet at `EventBus.publish()`.

---

## The event loop: one thread, many coroutines

`asyncio` is **single-threaded**. It runs a scheduler called the **event loop** that switches between coroutines when they are waiting for I/O. Only one coroutine runs at a time, but while one is waiting (on a network response, a sleep, a file), the loop runs another.

This is different from threading:

| | `threading` | `asyncio` |
|---|---|---|
| Concurrency unit | OS thread | coroutine |
| Switching | OS scheduler (preemptive) | `await` keyword (cooperative) |
| Shared state | needs a lock | single-threaded, safer by default |
| Best for | blocking I/O, C extensions | many concurrent I/O tasks |

The mental model: the event loop is a single worker who picks up tasks, works on each until it hits a waiting point, sets it aside, picks up the next task. Nothing runs truly in parallel — but when all you're doing is waiting on networks, that's fine.

---

## `async def` and `await`

A function defined with `async def` is a **coroutine function**. Calling it returns a **coroutine object** — it does not execute anything yet.

```python
async def fetch(url):
    print(f"fetching {url}")
    await asyncio.sleep(1)     # suspend here; event loop runs other tasks
    print("done")

# This does NOT run fetch — it just creates a coroutine object:
coro = fetch("https://example.com")

# To actually run it you need to await it inside another coroutine,
# or hand it to asyncio.run():
asyncio.run(fetch("https://example.com"))
```

`await` is the suspension point. When a coroutine hits `await`, it yields control back to the event loop and says "wake me up when this is ready." The loop is then free to run other coroutines.

**Common mistake**: forgetting to `await` a coroutine. The coroutine object is created but never runs. Python 3.11+ warns about this; earlier versions silently discard it.

```python
# WRONG — greet() returns a coroutine object; nothing prints
async def greet():
    print("hello")

async def main():
    greet()        # missing await — creates the object, throws it away

# RIGHT
async def main():
    await greet()
```

---

## `asyncio.run(main())` — entry point

`asyncio.run()` creates a fresh event loop, runs the given coroutine until it completes, then closes the loop.

```python
import asyncio

async def main():
    print("start")
    await asyncio.sleep(0.1)
    print("end")

asyncio.run(main())   # correct top-level call
```

**Never call `asyncio.run()` from inside a running event loop** — it raises `RuntimeError: This event loop is already running`. FastAPI, pytest-asyncio, and Jupyter all manage their own event loops; inside them you `await` directly instead of calling `asyncio.run()`.

---

## `asyncio.gather(*coros)` — concurrent coroutines

`gather` runs multiple coroutines **concurrently** within the same event loop. They are not parallel (no multiple CPUs) but they interleave — while one is awaiting I/O, another runs.

```python
import asyncio

async def fetch(name, delay):
    print(f"{name}: start")
    await asyncio.sleep(delay)
    print(f"{name}: done after {delay}s")
    return name

async def main():
    results = await asyncio.gather(
        fetch("a", 1),
        fetch("b", 2),
        fetch("c", 0.5),
    )
    print(results)   # ['a', 'b', 'c'] — in call order, not completion order

asyncio.run(main())
# Total elapsed: ~2s, not 3.5s — they overlapped
```

In akanga, `asyncio.create_task()` (a lower-level relative of gather) is how a FastAPI handler can kick off background work without blocking the response — it schedules a coroutine on the running loop and moves on. (An earlier active-node design used one polling task per node; it was cut — see `future-ideas.md`.)

---

## `asyncio.sleep(n)` — yield without blocking

`asyncio.sleep(n)` suspends the current coroutine for `n` seconds and gives the event loop time to run other tasks. It is the async equivalent of `time.sleep(n)` — but `time.sleep` blocks the entire thread (and thus the entire event loop), while `asyncio.sleep` only suspends the current coroutine.

```python
# WRONG inside async code — blocks the event loop for 5 seconds; nothing else runs
import time
async def bad():
    time.sleep(5)

# RIGHT — suspends only this coroutine; event loop runs others
async def good():
    await asyncio.sleep(5)
```

---

## `asyncio.get_event_loop()` vs `asyncio.get_running_loop()`

These look similar but behave differently:

- **`asyncio.get_running_loop()`** — returns the currently-running event loop. Raises `RuntimeError` if there is no running loop. Use this inside `async def` code when you need the loop object.
- **`asyncio.get_event_loop()`** — more permissive; creates a new loop if none exists (behavior changed in Python 3.10+). Mostly useful in older code or non-async contexts where you're constructing a loop manually.

```python
async def inside_coroutine():
    loop = asyncio.get_running_loop()   # always correct inside async def
    task = loop.create_task(some_coro())
    return task
```

---

## `loop.create_task(coro)` — schedule without waiting

`create_task` schedules a coroutine to run on the event loop and returns a `Task` object immediately — without suspending the caller. The task runs when the event loop gets to it (i.e., the next time the current coroutine awaits something).

```python
async def background_job():
    await asyncio.sleep(1)
    print("job done")

async def main():
    task = asyncio.create_task(background_job())
    print("task scheduled, continuing...")
    await asyncio.sleep(2)   # event loop runs background_job during this sleep
    # task is done by now
```

A robust pattern keeps a reference to every task you schedule — a bare `create_task(...)` whose return value is dropped can be garbage-collected mid-flight:

```python
self._tasks: set[asyncio.Task] = set()

task = asyncio.create_task(self._background_job(node_id))
self._tasks.add(task)                        # keep a strong reference …
task.add_done_callback(self._tasks.discard)  # … and drop it when finished
```

Storing tasks in a container also lets you cancel them later — on shutdown, or when the work they were doing is no longer needed.

---

## The critical bridge: `asyncio.run_coroutine_threadsafe`

This is the most important function for understanding how akanga's threading and asyncio worlds connect.

**The problem**: the watchdog file watcher runs in its own OS thread. An eventbus subscriber may be an `async def` function (say, an indexer hook that awaits I/O). You cannot `await` a coroutine from a non-async thread — there is no event loop in that thread to run it.

**The solution**: `asyncio.run_coroutine_threadsafe(coro, loop)` submits a coroutine to a running event loop from any thread. It is thread-safe. It returns a `concurrent.futures.Future` (not an asyncio Future) that you can check or block on from the calling thread.

```python
import asyncio, threading

async def greet(name):
    await asyncio.sleep(0.1)
    print(f"hello {name}")

# Imagine this loop is running in another thread
loop = asyncio.new_event_loop()
loop_thread = threading.Thread(target=loop.run_forever, daemon=True)
loop_thread.start()

# From the main (non-async) thread, submit a coroutine:
future = asyncio.run_coroutine_threadsafe(greet("world"), loop)
future.result()   # optional: block until the coroutine finishes
```

The submitted coroutine runs inside `loop`'s thread — not the calling thread. This is safe because the event loop is single-threaded; the coroutine runs when the loop schedules it.

---

## Why the bridge matters: `eventbus.py`

This is the heart of the `EventBus` you build in Phase 4. `publish()` dispatches each subscriber by three rules — and the loop check and the buffer append happen inside **one** lock acquisition, because reading `self._loop` outside the lock would race `set_loop()`:

```python
def publish(self, event: str, **kwargs) -> None:
    with self._lock:
        handlers = list(self._handlers.get(event, ()))   # snapshot, then release the lock

    for handler in handlers:
        try:
            if asyncio.iscoroutinefunction(handler):
                with self._lock:
                    loop = self._loop
                    if loop is None:
                        # Startup window: no loop yet. BUFFER (handler, kwargs) —
                        # never drop it, never call the coroutine directly. set_loop()
                        # drains the buffer FIFO once the loop is registered.
                        self._buffer.append((handler, dict(kwargs)))
                if loop is not None:
                    future = asyncio.run_coroutine_threadsafe(handler(**kwargs), loop)
                    future.add_done_callback(_log_future_exception)
            else:
                handler(**kwargs)            # sync subscriber: the only no-loop fallback
        except Exception:
            logger.exception("subscriber for %r failed", event)
```

The three dispatch rules:

- **async subscriber + loop set** → `run_coroutine_threadsafe` schedules it on the loop, with a done-callback that logs any exception the coroutine raises.
- **async subscriber + no loop yet** → **buffer** the `(handler, kwargs)` pair; it is never dropped and never called directly. `set_loop()` stores the loop (under the same lock) and then drains the buffer FIFO, so a too-early event is replayed exactly once.
- **sync subscriber** → call it directly. This is the only path that needs no loop, and it is the path the shipped `AkangaApp` uses (its subscribers are synchronous).

The flow when a file changes, *if* you have wired an async subscriber:

1. The watchdog thread calls `eventbus.publish("file_changed", path=...)`.
2. `publish()` runs in the watchdog thread — no event loop there.
3. The loop was registered by `set_loop()` during startup (you pass `asyncio.get_running_loop()` from inside the async app).
4. `run_coroutine_threadsafe` hands the coroutine to that loop; the done-callback logs any error.
5. The loop runs the subscriber as a coroutine.

Without this bridge a thread could never trigger async work — and without the buffer, any event published in the startup window before `set_loop()` would be silently lost.

---

## FastAPI and asyncio

FastAPI is an async web framework built on Starlette and `uvicorn`. It manages its own event loop. Route handlers defined as `async def` run as coroutines within that loop:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/v1/nodes")
async def list_nodes(query: str = ""):
    # This runs as a coroutine inside FastAPI's event loop.
    # You can await I/O here. Do NOT use time.sleep() here.
    results = await some_async_db_call(query)
    return results
```

In akanga's `server.py`, all route handlers are `async def`, and the lifespan context manager (startup/shutdown) is also async — Phase 6's opens the database and indexes the vault before the first request, then closes the database on shutdown:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    db = GraphDatabase(resolved_db)
    _app_state["db"] = db
    full_scan_and_index(resolved_vault, db)   # the API serves the index
    yield
    db.close()
```

---

## Common mistakes

**1. Calling `asyncio.run()` inside a running loop**

```python
# WRONG — raises RuntimeError inside FastAPI, pytest-asyncio, Jupyter
async def handler():
    result = asyncio.run(some_coro())   # RuntimeError!
    return result

# RIGHT — just await
async def handler():
    result = await some_coro()
    return result
```

**2. Forgetting to await a coroutine**

```python
async def main():
    fetch_data()    # returns a coroutine object; does NOT run fetch_data
    await fetch_data()  # this runs it
```

**3. Blocking the event loop with `time.sleep`**

```python
async def handler():
    time.sleep(2)       # blocks ALL coroutines for 2 seconds
    await asyncio.sleep(2)  # only suspends this coroutine
```

**4. Calling `await` outside `async def`**

```python
# SyntaxError — await is only valid inside async def
result = await some_coro()

# Fix: wrap it
async def wrapper():
    return await some_coro()
asyncio.run(wrapper())
```

---

## Where asyncio appears in your implementation

| File (phase where you build it) | What it does |
|---|---|
| `eventbus.py` (Phase 4) | `run_coroutine_threadsafe` bridges the watchdog thread to the event loop; async subscribers published before `set_loop()` are buffered and drained FIFO |
| `watcher.py` (Phase 4) | the watchdog file watcher runs in a daemon thread; `_EventHandler._debounced()` publishes events that cross into the async world through the bridge |
| `app.py` (Phase 8) | `AkangaApp` composition root; `start_all()` / `stop_all()` are synchronous and wire the watcher, db, eventbus, and git manager |
| `server.py` (Phase 6) | FastAPI async throughout; lifespan is an async context manager |

---

## Summary

| Concept | When to use |
|---|---|
| `async def` / `await` | Define and suspend coroutines |
| `asyncio.run(main())` | Top-level entry point; never inside a running loop |
| `asyncio.gather(*coros)` | Run several coroutines concurrently |
| `asyncio.sleep(n)` | Yield without blocking; never use `time.sleep` in async code |
| `loop.create_task(coro)` | Schedule a coroutine without awaiting it |
| `asyncio.get_running_loop()` | Get the current loop from inside a coroutine |
| `run_coroutine_threadsafe(coro, loop)` | Submit a coroutine from a non-async thread to a running loop |

The one rule to remember: **`await` is the only safe way to suspend a coroutine**. Everything else in asyncio follows from understanding that single cooperative scheduling point.
