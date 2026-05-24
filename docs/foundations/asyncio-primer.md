# asyncio Primer

This doc covers the **async** half of akanga's concurrency model. Read `python-threading.md` first — the two models run side by side in this codebase and meet at `EventBus.publish()`.

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

In akanga, `ActiveNodeManager` uses `asyncio.create_task()` (a lower-level relative of gather) to run one polling loop per active node concurrently.

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

In akanga's `ActiveNodeManager._schedule_if_active()`:

```python
self._tasks[node_id] = asyncio.create_task(
    self._run_loop(node_id, active_cfg, interval)
)
```

Each active node gets a persistent polling loop running as an independent task. Tasks are stored in `self._tasks` so they can be canceled when a node is updated or deleted.

---

## The critical bridge: `asyncio.run_coroutine_threadsafe`

This is the most important function for understanding how akanga's threading and asyncio worlds connect.

**The problem**: the watchdog file watcher runs in its own OS thread. The eventbus subscribers (like `ActiveNodeManager.on_node_updated`) are `async def` functions. You cannot `await` a coroutine from a non-async thread — there is no event loop in that thread to run it.

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

This is the exact code from `src/akanga_core/eventbus.py`:

```python
def publish(self, topic: str, payload: Any) -> None:
    for cb in list(self._subs.get(topic, [])):
        coro = cb(topic, payload)              # cb is async def; calling it gives a coroutine
        if self._loop and self._loop.is_running():
            # Called from a non-async thread (e.g., watchdog):
            future = asyncio.run_coroutine_threadsafe(coro, self._loop)
            future.add_done_callback(self._handle_error)
        else:
            try:
                loop = asyncio.get_running_loop()
                task = loop.create_task(coro)  # already inside the loop — just schedule it
                task.add_done_callback(self._handle_task_error)
            except RuntimeError:
                logger.warning("No event loop available for publish on topic '%s'", topic)
```

The flow when a file changes:

1. Watchdog thread calls `eventbus.publish("node.updated", {...})`.
2. `publish()` is running in the watchdog thread — no event loop here.
3. `self._loop` was set by `AkangaApp.start_all()` and is the asyncio event loop running in the main thread.
4. `run_coroutine_threadsafe` hands the coroutine to the main thread's event loop.
5. The event loop runs the subscriber (e.g., `ActiveNodeManager.on_node_updated`) as a coroutine.

Without this bridge, the watcher could never trigger async behavior — it would have to call synchronous code only.

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

In akanga's `server.py`, all route handlers are `async def`, and the lifespan context manager (startup/shutdown) is also async:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await akanga_app.start_all()   # starts active manager, watcher, etc.
    yield
    await akanga_app.stop_all()
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

## Where asyncio is used in this codebase

| File | What it does |
|---|---|
| `eventbus.py` | `run_coroutine_threadsafe` bridges watchdog thread to event loop; `create_task` for same-loop delivery |
| `active.py` | `ActiveNodeManager` — one `asyncio.Task` per active node, running concurrent HTTP/TCP checks with `aiohttp` |
| `app.py` | `start_all()` / `stop_all()` are async; sets the loop on the eventbus so the bridge knows which loop to target |
| `server.py` | FastAPI async throughout; lifespan is an async context manager |

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
