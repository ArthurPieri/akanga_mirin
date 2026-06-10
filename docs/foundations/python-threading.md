# Python Threading

Phase 4 of the learning path covers concurrency — the hardest conceptual leap in the codebase. This doc covers the **threading** side. The companion doc `asyncio-primer.md` covers the async side. Both meet in `eventbus.py`.

---

## The GIL: why threads work for I/O but not CPU

Python has a **Global Interpreter Lock (GIL)**. Only one thread can execute Python bytecode at a time. This means:

- **I/O-bound work** (waiting on disk, network, timers) — threads are effective. While one thread waits, the GIL is released and another thread runs.
- **CPU-bound work** (number crunching, image processing) — threads don't help. All threads fight over the same GIL; you get no real parallelism.

The akanga watcher is I/O-bound by nature (it waits for filesystem events and timers), so threading is the right tool.

```python
# Threads shine here — waiting for I/O releases the GIL
import threading, time

def wait_for_file():
    time.sleep(2)   # GIL released during sleep; other threads run
    print("done")

t = threading.Thread(target=wait_for_file)
t.start()
print("main thread continues immediately")
t.join()
```

---

## `threading.Thread` — creating and starting threads

```python
import threading

def worker(name, count):
    for i in range(count):
        print(f"{name}: {i}")

# target= is the function; args= is a tuple of arguments
t = threading.Thread(target=worker, args=("background", 3), daemon=True)
t.start()   # spawns the thread; returns immediately
t.join()    # blocks the current thread until t finishes
```

**`daemon=True`** means the thread will be killed automatically when the main thread exits. Non-daemon threads keep the process alive until they finish. In akanga, the watchdog observer thread is daemonized so the process can exit cleanly when the user presses `q`.

**`start()` vs `join()`**: `start()` launches the thread. `join()` waits for it to finish. A common pattern is to start several threads then join them all:

```python
threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(5)]
for t in threads:
    t.start()
for t in threads:
    t.join()
print("all done")
```

---

## `threading.Lock` — mutual exclusion

When two threads share mutable state, you need a **lock** to prevent races. A lock allows only one thread to hold it at a time.

```python
import threading

counter = 0
lock = threading.Lock()

def increment():
    global counter
    with lock:          # acquires; releases automatically on exit (even on exception)
        counter += 1

threads = [threading.Thread(target=increment) for _ in range(1000)]
for t in threads: t.start()
for t in threads: t.join()
print(counter)   # reliably 1000; without lock it can be less
```

**Always use `with lock:`**, never `lock.acquire()` / `lock.release()` manually. If an exception fires between acquire and release, the lock stays locked forever and every other thread blocks forever (a deadlock).

---

## `threading.Event` — signaling between threads

An `Event` is a thread-safe boolean flag. Use it instead of `time.sleep` when one thread needs to wait for another thread to signal that something is ready.

```python
import threading

ready = threading.Event()

def producer():
    print("working...")
    import time; time.sleep(1)
    ready.set()   # unblocks any thread waiting on ready

def consumer():
    ready.wait()            # blocks until set() is called
    print("got the signal")

    # With a timeout:
    if ready.wait(timeout=5):
        print("signaled in time")
    else:
        print("timed out")

t1 = threading.Thread(target=producer)
t2 = threading.Thread(target=consumer)
t1.start(); t2.start()
t1.join(); t2.join()
```

`event.is_set()` checks the flag without blocking. `event.clear()` resets it.

---

## `threading.Timer` — one-shot deferred call

`Timer` is a subclass of `Thread` that waits for a delay before calling a function. It's cancelable before the delay expires.

```python
import threading

def greet(name):
    print(f"Hello, {name}!")

timer = threading.Timer(2.0, greet, args=["world"])
timer.start()

# Cancel before it fires:
timer.cancel()   # no-op if already fired; safe to call either way
```

Under the hood, `Timer` just sleeps for the delay then calls the function in its own thread. Canceling it sets an internal `Event` that makes the sleep return early.

---

## The debounce pattern

Debouncing is the classic use of `Timer` + `Lock`: when a stream of rapid events arrives, you only want to act on the *last* one after the stream quiets down for a moment.

The algorithm is:
1. When an event arrives, cancel the existing timer (if any).
2. Start a new timer for N seconds.
3. If no new event arrives, the timer fires and the callback runs.
4. If another event arrives before the timer fires, go to step 1.

This is exactly what akanga's file watcher does so that rapid editor saves (`:w`, auto-save, temp-file writes) produce only one re-index per "save session" instead of dozens.

```python
import threading

_timers: dict[str, threading.Timer] = {}
_lock = threading.Lock()

def debounced(key: str, fn, delay: float = 0.5):
    with _lock:
        existing = _timers.pop(key, None)
        if existing:
            existing.cancel()          # cancel the old timer
        timer = threading.Timer(delay, fn)
        _timers[key] = timer
        timer.start()                  # start a fresh timer

debounced("my-file.md", lambda: print("re-index"))
debounced("my-file.md", lambda: print("re-index"))   # cancels the first
# only one "re-index" fires after 0.5 s
```

The lock is essential: if two filesystem events arrive on different watchdog threads at the same millisecond, you'd have a race on `_timers` without it.

---

## The debounce pattern in akanga: `watcher.py`

This is the debounce handler at the heart of the `watcher.py` you build in Phase 4:

```python
class _EventHandler(FileSystemEventHandler):
    def __init__(self, vault_path, on_change, on_delete, debounce_sec=0.5):
        super().__init__()
        self._debounce_sec = debounce_sec
        self._timers: dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def _debounced(self, key: str, fn: Callable, path: str) -> None:
        with self._lock:
            existing = self._timers.pop(key, None)
            if existing:
                existing.cancel()
            timer = threading.Timer(self._debounce_sec, fn, args=[path])
            self._timers[key] = timer
            timer.start()

    def on_modified(self, event):
        if not event.is_directory and self._is_relevant(event.src_path):
            self._debounced(event.src_path, self.on_change, event.src_path)
```

Key points:
- `_timers` is a dict keyed by file path — each file gets its own independent debounce timer.
- `_lock` protects `_timers` because watchdog dispatches events from its own thread (sometimes multiple threads).
- `timer.cancel()` is called before creating a new one — "cancel and restart" on every event.

---

## Thread-safety rules

These rules will save you hours of debugging subtle, intermittent bugs:

**Shared mutable state always needs a lock.** If two threads can read and write the same variable, you have a data race. Races produce wrong values silently — no exception is raised.

**`list` and `dict` operations are NOT atomic.** Appending to a list involves multiple bytecode instructions. Between any two instructions the GIL can be handed to another thread.

```python
# UNSAFE — another thread can read the list between the check and the append
if key not in my_dict:
    my_dict[key] = compute()   # another thread may have added key here already

# SAFE — use a lock
with lock:
    if key not in my_dict:
        my_dict[key] = compute()
```

**`int` increment is NOT atomic.** `counter += 1` compiles to `LOAD`, `ADD`, `STORE` — three instructions, not one.

```python
# UNSAFE
counter += 1

# SAFE
with lock:
    counter += 1
```

---

## `GraphDatabase._lock` in akanga: `db.py`

The database is accessed from many threads simultaneously: the watcher thread, the FastAPI request threads, the active-node manager. Every write (and reads that must be consistent) goes through the lock:

```python
class GraphDatabase:
    def __init__(self, path: str):
        self._lock = threading.Lock()
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        # check_same_thread=False allows the connection to be shared,
        # but WE are responsible for preventing concurrent access — hence the lock.

    def upsert_node(self, node: Node, hash_value: str | None = None) -> None:
        with self._lock, self.conn:   # self.conn as context manager = transaction
            self.conn.execute("INSERT OR REPLACE INTO nodes ...", (...))
            self.conn.execute("DELETE FROM nodes_fts WHERE node_id = ?", ...)
            self.conn.execute("INSERT INTO nodes_fts ...", (...))

    def get_node_by_path(self, path: str) -> dict | None:
        with self._lock:
            cur = self.conn.execute("SELECT * FROM nodes WHERE path = ?", (path,))
            row = cur.fetchone()
        # lock released before deserializing — row is local, safe to process unlocked
        return self._deserialize_row(row) if row else None
```

`with self._lock, self.conn:` is a Python idiom for two context managers at once — equivalent to `with self._lock: with self.conn:`. The SQLite connection used as a context manager commits on success, rolls back on exception.

---

## Where threading is used in this codebase

| File | What it does |
|---|---|
| `watcher.py` | `threading.Lock` + `threading.Timer` for the debounce pattern |
| `db.py` | `threading.Lock` on every read/write |
| `gitmgr.py` | `threading.Timer` for 5-second debounced auto-commit |
| `eventbus.py` | Thread-safe publish — the bridge between the watchdog thread and the asyncio event loop (see `asyncio-primer.md`) |

---

## Summary

| Concept | Use for |
|---|---|
| `threading.Thread` | Run a function in the background |
| `daemon=True` | Thread dies when main exits |
| `thread.join()` | Wait for a thread to finish |
| `threading.Lock` | Protect shared mutable state |
| `threading.Event` | Signal between threads without sleep |
| `threading.Timer` | Defer a call; cancel before it fires |
| Debounce pattern | Coalesce rapid events into one action |

The single rule to remember: **any mutable object touched by more than one thread needs a lock.** Everything else follows from that.
