# Observability Module — Structured Logging, Tracing, and Debugging for Python Services

**Estimated reading time:** 45–60 minutes
**Applies to:** Any Python CLI, background service, or API — not Akanga-specific.
**Prerequisites:** Python 3.10+, basic familiarity with `logging`, async/await, Typer or Click for CLI.

This module teaches the observability skills that distinguish a tool you built from
a tool you can operate. "It works on my machine" is not enough when a cron job fails
silently at 3am, a slow query degrades user experience, or an event is dropped and
nobody notices. Observability means you can answer the question *"what is my system
doing right now, and what did it do when it failed?"* — without adding print statements.

---

## 1. Structured Logging with Python's `logging` Module

### Why the `logging` Module, Not `print()`

`print()` goes to stdout, has no severity level, no timestamp, no source location,
no machine-readable format, and cannot be redirected or silenced without editing code.
Python's `logging` module solves all of these. It is part of the standard library,
so there is nothing to install.

The critical mental model: **logging is a hierarchy of loggers, not a single global
function.** Every module has its own logger named after the module. Log records travel
up the hierarchy to the root logger where handlers dispatch them.

### Log Levels — When to Use Each

| Level | `logging` constant | When to use it |
|---|---|---|
| DEBUG | `10` | Internal state, intermediate values, "I am entering function X with args Y". Verbose enough to reconstruct any execution path. |
| INFO | `20` | Normal lifecycle events: service started, index complete, connection established. One line per significant action. |
| WARNING | `30` | Something unexpected happened but the system continues. Degraded mode, missing optional config, slow query. |
| ERROR | `40` | A specific operation failed. The system continues but this request/event/job did not. Always include the exception. |
| CRITICAL | `50` | The service cannot continue. Reserve for situations that require immediate human attention. |

The default level is WARNING — only WARNING and above appear by default. Set the root
logger to INFO in production, DEBUG when diagnosing an issue.

### Setting Up Logging in a Module

Every module should get its own logger at module load time. Never configure handlers
in a library module — that is the application's job.

```python
# In any library module (e.g., akanga_core/indexer.py)
import logging

logger = logging.getLogger(__name__)
# __name__ resolves to "akanga_core.indexer" — the full module path.
# This appears in every log record so you know exactly where it came from.

def index_file(path, db):
    logger.debug("Indexing %s", path)   # Note: %-style, not f-string. Lazy formatting.
    try:
        node = parse(path)
        db.upsert(node)
        logger.info("Indexed node %s (%s)", node.id, node.title)
    except Exception:
        logger.exception("Failed to index %s", path)
        # logger.exception() logs at ERROR and appends the full traceback automatically.
        raise
```

Use `%s`-style formatting, not f-strings. The `logging` module defers string
formatting until the record is actually emitted — if the log level is above DEBUG,
the string is never formatted and there is no wasted work.

### Configuring Handlers in the Application Entry Point

```python
# In cli.py or app.py — the application entry point, not a library module.
import logging
import sys

def configure_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(
        fmt="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    ))
    logging.root.setLevel(level)
    logging.root.addHandler(handler)
```

Set handlers on the root logger once, at startup. All loggers in all modules
automatically propagate records up to it.

### Structured JSON Logging

Plain-text logs are human-readable but not machine-parseable. When you need to ship
logs to a file, a log aggregator (Loki, Datadog, CloudWatch), or grep by field,
JSON is the correct format.

```python
import json
import logging
import time

class JsonFormatter(logging.Formatter):
    """Emit each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        # Merge any extra fields passed as keyword arguments to the logger call.
        for key, value in record.__dict__.items():
            if key not in logging.LogRecord.__dict__ and not key.startswith("_"):
                payload[key] = value
        return json.dumps(payload, default=str)
```

Usage:

```python
handler = logging.StreamHandler(sys.stderr)
handler.setFormatter(JsonFormatter())
logging.root.addHandler(handler)

# Passing extra context fields:
logger.info("Node indexed", extra={"node_id": node.id, "vault": str(vault_path)})
# Output: {"ts": "2026-05-24T10:00:00Z", "level": "INFO", "logger": "akanga_core.indexer",
#          "msg": "Node indexed", "node_id": "abc-123", "vault": "/home/user/vault"}
```

### Log File Rotation

For a long-running service, logs must rotate or the disk fills.

```python
from logging.handlers import RotatingFileHandler

file_handler = RotatingFileHandler(
    "/var/log/akanga/akanga.json",
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=5,               # keep akanga.json.1 through .5
    encoding="utf-8",
)
file_handler.setFormatter(JsonFormatter())
logging.root.addHandler(file_handler)
```

Keep console output as human-readable text and file output as JSON — one handler each.
The `logging` module supports multiple handlers per logger.

---

## 2. Timing and Tracing Decorators

### The `@timed` Decorator

The simplest useful instrumentation: measure how long a function takes and log it.

```python
import functools
import logging
import time

logger = logging.getLogger(__name__)

def timed(logger: logging.Logger | None = None, level: int = logging.DEBUG):
    """
    Decorator that logs the execution time of a function.

    Usage:
        @timed()
        def my_function():
            ...

        @timed(logger=logging.getLogger("my_module"), level=logging.INFO)
        def important_function():
            ...
    """
    _logger = logger or logging.getLogger(__name__)

    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            start = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
                elapsed = time.perf_counter() - start
                _logger.log(level, "%s completed in %.3fs", fn.__qualname__, elapsed)
                return result
            except Exception:
                elapsed = time.perf_counter() - start
                _logger.log(level, "%s failed after %.3fs", fn.__qualname__, elapsed)
                raise
        return wrapper
    return decorator
```

Usage:

```python
@timed(level=logging.INFO)
def full_scan_and_index(vault: Path, db: GraphDatabase) -> int:
    ...
```

### Context Manager for Operation Timing

For timing blocks of code that are not a single function call:

```python
import contextlib
import logging
import time

@contextlib.contextmanager
def timed_block(name: str, logger: logging.Logger, level: int = logging.DEBUG):
    """
    Context manager that logs the duration of a code block.

    Usage:
        with timed_block("db_upsert", logger):
            db.upsert(node)
    """
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.log(level, "%s took %.3fs", name, elapsed)
```

Usage:

```python
with timed_block("full_index", logger, level=logging.INFO):
    for path in vault.glob("**/*.md"):
        index_file(path, db)
```

### When to Instrument

Instrument at the boundary of every significant external call: file reads, DB writes,
HTTP requests, subprocess invocations. Do not instrument pure in-memory computation
unless you suspect it is slow. The goal is to know *where* time is going, not to
measure everything.

---

## 3. Async Tracing — Tracing Coroutines Without Blocking

Synchronous decorators cannot wrap `async def` functions correctly — they would lose
the coroutine semantics. An async-aware `timed` decorator handles both:

```python
import asyncio
import functools
import logging
import time

def timed(logger: logging.Logger | None = None, level: int = logging.DEBUG):
    _logger = logger or logging.getLogger(__name__)

    def decorator(fn):
        if asyncio.iscoroutinefunction(fn):
            @functools.wraps(fn)
            async def async_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = await fn(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    _logger.log(level, "%s completed in %.3fs", fn.__qualname__, elapsed)
                    return result
                except Exception:
                    elapsed = time.perf_counter() - start
                    _logger.log(level, "%s failed after %.3fs", fn.__qualname__, elapsed)
                    raise
            return async_wrapper
        else:
            @functools.wraps(fn)
            def sync_wrapper(*args, **kwargs):
                start = time.perf_counter()
                try:
                    result = fn(*args, **kwargs)
                    elapsed = time.perf_counter() - start
                    _logger.log(level, "%s completed in %.3fs", fn.__qualname__, elapsed)
                    return result
                except Exception:
                    elapsed = time.perf_counter() - start
                    _logger.log(level, "%s failed after %.3fs", fn.__qualname__, elapsed)
                    raise
            return sync_wrapper
    return decorator
```

Now `@timed()` works identically on sync and async functions.

### Async Context Manager for Block Timing

```python
import contextlib
import logging
import time

@contextlib.asynccontextmanager
async def async_timed_block(name: str, logger: logging.Logger, level: int = logging.DEBUG):
    start = time.perf_counter()
    try:
        yield
    finally:
        elapsed = time.perf_counter() - start
        logger.log(level, "%s took %.3fs", name, elapsed)
```

### Tracing Coroutine Scheduling Latency

When you schedule a coroutine and need to know how long it waited in the event loop
queue before starting (scheduling latency, not execution time):

```python
async def traced_coro(name: str, coro, logger: logging.Logger):
    """Wrap a coroutine to log scheduling latency and execution time."""
    queued_at = time.perf_counter()
    try:
        started_at = time.perf_counter()
        wait_ms = (started_at - queued_at) * 1000
        logger.debug("%s scheduling latency: %.1fms", name, wait_ms)
        result = await coro
        elapsed = time.perf_counter() - started_at
        logger.debug("%s execution: %.3fs", name, elapsed)
        return result
    except Exception:
        logger.exception("%s raised", name)
        raise
```

---

## 4. EventBus Introspection — Debug Subscribers That Log All Events

When a system uses an event bus, events are the communication fabric. If something
breaks and you do not know which events fired, debugging is guesswork. The solution
is a debug subscriber that attaches at startup (when `--verbose` is set) and logs
every event that passes through the bus.

```python
import logging

logger = logging.getLogger("eventbus.debug")

def make_debug_subscriber(bus):
    """
    Attach a subscriber to every known event type that logs the event name and payload.
    Call this at startup when --verbose is set.

    Args:
        bus: An EventBus instance with a subscribe(event_name, handler) method.

    Usage:
        if verbose:
            make_debug_subscriber(eventbus)
    """
    KNOWN_EVENTS = [
        "file_changed", "file_deleted",
        "node_updated", "node_deleted",
        "active_result", "sync_complete",
    ]

    def make_handler(event_name):
        def handler(**kwargs):
            logger.debug(
                "EVENT %s %s",
                event_name,
                {k: str(v) for k, v in kwargs.items()},
            )
        return handler

    for event_name in KNOWN_EVENTS:
        bus.subscribe(event_name, make_handler(event_name))
```

A simpler approach when the EventBus supports wildcard subscriptions or a pre-publish
hook:

```python
class EventBus:
    def __init__(self, debug: bool = False):
        self._debug = debug
        self._logger = logging.getLogger("eventbus")
        ...

    def publish(self, event: str, **kwargs):
        if self._debug:
            self._logger.debug("publish %s %s", event, kwargs)
        # ... normal dispatch logic
```

The debug parameter is the cleaner design: the bus itself logs before dispatching
rather than adding a phantom subscriber. Both approaches are valid; choose based on
whether you control the EventBus source.

### What to Log Per Event

At DEBUG level, log: event name, full payload (truncated if large), timestamp.
At INFO level (production), log: only events that represent significant state changes
(`node_updated`, `sync_complete`) — not high-frequency events (`file_changed` fires
every keystroke).

---

## 5. SQLite Slow-Query Detection

### Using `set_trace_callback`

SQLite exposes a trace callback that fires before every statement executes. This is
the correct hook for query logging — it works without modifying individual call sites.

```python
import logging
import sqlite3
import time

logger = logging.getLogger("sqlite.trace")

SLOW_QUERY_THRESHOLD_MS = 50  # Queries slower than this are WARNING; others are DEBUG.


def make_trace_callback(threshold_ms: float = SLOW_QUERY_THRESHOLD_MS):
    """
    Returns a trace callback that logs SQL statements with their execution time.

    Usage:
        conn = sqlite3.connect(db_path)
        conn.set_trace_callback(make_trace_callback())
    """
    wall = {}

    def before(statement: str):
        wall["start"] = time.perf_counter()
        logger.debug("SQL: %s", statement.strip())

    def after(statement: str):
        if "start" in wall:
            elapsed_ms = (time.perf_counter() - wall["start"]) * 1000
            if elapsed_ms > threshold_ms:
                logger.warning("SLOW QUERY (%.1fms): %s", elapsed_ms, statement.strip())

    # sqlite3.set_trace_callback accepts a single callable; we use the before variant.
    # For timing, wrap with a class or use connection.execute monkeypatching (see below).
    return before
```

`set_trace_callback` only receives the SQL string, not timing. For timing, the
idiomatic approach is to wrap the connection's `execute` method:

```python
class TimedConnection:
    """Thin wrapper around sqlite3.Connection that logs slow queries."""

    def __init__(self, conn: sqlite3.Connection, threshold_ms: float = 50.0):
        self._conn = conn
        self._threshold = threshold_ms / 1000.0  # convert to seconds
        self._logger = logging.getLogger("sqlite.timed")

    def execute(self, sql: str, params=()):
        start = time.perf_counter()
        cursor = self._conn.execute(sql, params)
        elapsed = time.perf_counter() - start
        if elapsed > self._threshold:
            self._logger.warning(
                "SLOW QUERY %.1fms: %s | params=%s",
                elapsed * 1000,
                sql.strip(),
                params,
            )
        else:
            self._logger.debug("%.1fms: %s", elapsed * 1000, sql.strip())
        return cursor

    def __getattr__(self, name):
        return getattr(self._conn, name)
```

### Using `EXPLAIN QUERY PLAN`

When a query is slow, the next step is to understand why. SQLite's `EXPLAIN QUERY PLAN`
shows the access path (table scan vs index use) without executing the query.

```python
def explain_query(conn: sqlite3.Connection, sql: str, params=()) -> str:
    """
    Return EXPLAIN QUERY PLAN output for a SQL statement.
    Call this when you observe a slow query — not in production hot paths.

    Usage:
        print(explain_query(conn, "SELECT * FROM nodes WHERE type = ?", ("note",)))
    """
    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    lines = []
    for row in rows:
        # Columns: id, parent, notused, detail
        indent = "  " * row[1] if row[1] >= 0 else ""
        lines.append(f"{indent}{row[3]}")
    return "\n".join(lines)
```

**How to read the output:**

- `SCAN TABLE nodes` — full table scan. No index used. Will degrade at large row count.
- `SEARCH TABLE nodes USING INDEX idx_nodes_type` — index used. Fast.
- `SEARCH TABLE nodes_fts USING fts5` — FTS5 virtual table scan. Fast for text queries.

If you see `SCAN TABLE` on a large table, add an index:

```sql
CREATE INDEX IF NOT EXISTS idx_nodes_type ON nodes(type);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
```

### Checking Index Health

```python
def check_index_usage(conn: sqlite3.Connection, table: str) -> None:
    """Log all indexes defined on a table and their estimated selectivity."""
    indexes = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='index' AND tbl_name=?",
        (table,),
    ).fetchall()
    logger.info("Indexes on %s: %d", table, len(indexes))
    for name, sql in indexes:
        logger.debug("  %s: %s", name, sql)
```

---

## 6. The `--verbose` / `--debug` CLI Flag Pattern

Every CLI tool should support a verbosity flag that increases log output without
modifying any other configuration. The canonical pattern in Typer:

```python
# In cli.py
import logging
import typer
from typing import Annotated

app = typer.Typer()

# Shared verbose option — can be applied to any command.
VerboseOption = Annotated[
    bool,
    typer.Option("--verbose", "-v", help="Enable DEBUG-level logging.", is_eager=False),
]

def configure_logging(verbose: bool) -> None:
    """Configure root logging level and console handler. Call once at startup."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stderr,
    )
    if verbose:
        logging.getLogger().debug("Verbose logging enabled.")


@app.command()
def serve(
    vault: str = "./vault",
    db: str = "./.akanga.db",
    verbose: VerboseOption = False,
):
    """Start the Akanga REST API server."""
    configure_logging(verbose)
    logger = logging.getLogger(__name__)
    logger.info("Starting server — vault=%s db=%s", vault, db)
    ...


@app.command()
def index(
    vault: str = "./vault",
    db: str = "./.akanga.db",
    verbose: VerboseOption = False,
):
    """Index (or re-index) a vault."""
    configure_logging(verbose)
    ...
```

**Key design rules:**

1. `configure_logging` is called exactly once, at the start of the command handler,
   before any other code runs.
2. All library code uses `logging.getLogger(__name__)` and never calls `basicConfig`.
3. The `--verbose` flag sets the root logger level to DEBUG. This affects all loggers
   in all modules simultaneously — no per-module flag needed.
4. Direct the handler output to `stderr`, not `stdout`. Tools that process the output
   of a CLI (pipes, redirections) should not receive log lines mixed into data output.

### Adding a `--log-file` Option

```python
LogFileOption = Annotated[
    str | None,
    typer.Option("--log-file", help="Write JSON logs to this file (in addition to stderr).")
]

def configure_logging(verbose: bool, log_file: str | None = None) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    handlers = [logging.StreamHandler(sys.stderr)]
    if log_file:
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=10_000_000, backupCount=3, encoding="utf-8"
        )
        file_handler.setFormatter(JsonFormatter())
        handlers.append(file_handler)
    logging.basicConfig(level=level, handlers=handlers)
```

---

## 7. Metrics — Simple Counters and Gauges Without a Metrics Server

Before introducing Prometheus, StatsD, or any metrics library, Python's standard
library can carry you a long way with in-memory counters that are readable on demand.

### In-Memory Counter Registry

```python
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field

@dataclass
class MetricsRegistry:
    """
    Thread-safe in-memory metrics store.
    No external dependencies. Exportable to dict for /metrics or /health endpoints.
    """
    _counters: dict[str, int] = field(default_factory=lambda: defaultdict(int))
    _gauges: dict[str, float] = field(default_factory=dict)
    _histograms: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    _lock: threading.Lock = field(default_factory=threading.Lock)
    _started_at: float = field(default_factory=time.time)

    def increment(self, name: str, by: int = 1) -> None:
        with self._lock:
            self._counters[name] += by

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def record(self, name: str, value: float) -> None:
        """Record a single observation in a histogram (e.g., query latency)."""
        with self._lock:
            self._histograms[name].append(value)

    def snapshot(self) -> dict:
        """Return a point-in-time snapshot of all metrics."""
        with self._lock:
            histograms = {}
            for name, values in self._histograms.items():
                if values:
                    sorted_vals = sorted(values)
                    n = len(sorted_vals)
                    histograms[name] = {
                        "count": n,
                        "mean": sum(sorted_vals) / n,
                        "p50": sorted_vals[n // 2],
                        "p95": sorted_vals[int(n * 0.95)],
                        "p99": sorted_vals[int(n * 0.99)],
                    }
            return {
                "uptime_seconds": time.time() - self._started_at,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": histograms,
            }

# Singleton for the process. Import and use from any module.
metrics = MetricsRegistry()
```

Usage:

```python
from akanga_core.metrics import metrics

# In indexer.py
metrics.increment("nodes.indexed")
metrics.increment("edges.created", by=len(edges))

# In db.py
start = time.perf_counter()
cursor = conn.execute(sql, params)
metrics.record("db.query_ms", (time.perf_counter() - start) * 1000)
```

### Exposing Metrics via the Health Endpoint

```python
# In server.py
from akanga_core.metrics import metrics

@app.get("/metrics")
async def get_metrics() -> dict:
    """Machine-readable metrics snapshot. Suitable for polling by a monitoring script."""
    return metrics.snapshot()
```

---

## 8. Health Endpoints — Structured Sub-System Status

A simple `GET /health` that returns `200 OK` tells you the HTTP server is alive.
It does not tell you whether the database is accessible, the file watcher is running,
or the git repository is in a valid state. A structured health response does.

### The Pattern

```python
# In server.py
import time
from enum import Enum

class HealthStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"

@app.get("/health")
async def health_check() -> dict:
    """
    Structured health response. Check each sub-system independently.
    Overall status is the worst of all sub-system statuses.
    Returns 200 even if degraded — 503 only when fully down.
    """
    checks = {
        "db": _check_db(),
        "watcher": _check_watcher(),
        "git": _check_git(),
    }
    statuses = [c["status"] for c in checks.values()]
    if HealthStatus.DOWN in statuses:
        overall = HealthStatus.DOWN
    elif HealthStatus.DEGRADED in statuses:
        overall = HealthStatus.DEGRADED
    else:
        overall = HealthStatus.OK

    response = {
        "status": overall,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "checks": checks,
    }
    status_code = 503 if overall == HealthStatus.DOWN else 200
    from fastapi.responses import JSONResponse
    return JSONResponse(content=response, status_code=status_code)

def _check_db() -> dict:
    try:
        row = db.execute("SELECT COUNT(*) FROM nodes").fetchone()
        return {"status": HealthStatus.OK, "node_count": row[0]}
    except Exception as e:
        return {"status": HealthStatus.DOWN, "error": str(e)}

def _check_watcher() -> dict:
    if app_state.watcher and app_state.watcher.is_alive():
        return {"status": HealthStatus.OK}
    return {"status": HealthStatus.DEGRADED, "detail": "watcher not running"}

def _check_git() -> dict:
    if not app_state.git_manager:
        return {"status": HealthStatus.OK, "detail": "git not configured"}
    try:
        app_state.git_manager.repo.git.status()
        return {"status": HealthStatus.OK}
    except Exception as e:
        return {"status": HealthStatus.DEGRADED, "error": str(e)}
```

**Design rules:**

- Return `200` for degraded (some things work). Return `503` only when the service
  cannot handle any requests at all.
- Each check is independent — a DB failure does not prevent the watcher check from running.
- Include diagnostic context (node count, error message) so the health endpoint
  doubles as a lightweight diagnostic tool.

---

## 9. Log Aggregation for Local-First Tools

A tool that runs locally has no log aggregator. Where do logs go, and how do you
find them later?

### Option 1: stderr Only (Simplest)

Logs go to the terminal. Lost when the terminal closes. Acceptable for interactive use;
not acceptable for background services.

### Option 2: systemd / launchd Journal

When running under systemd or launchd, anything written to stderr is automatically
captured by the system journal.

```bash
# Read logs for a systemd service named "akanga"
journalctl -u akanga --since "1 hour ago" --follow

# Filter by log level (requires JSON logging)
journalctl -u akanga -o json | jq 'select(.level == "ERROR")'
```

This is free with no extra configuration when the service runs under systemd. It is
the recommended approach for local background services.

### Option 3: Rotating File Log

When you need log history beyond what the journal retains, add a rotating file handler:

```python
import logging.handlers

file_handler = logging.handlers.RotatingFileHandler(
    filename="/var/log/akanga/akanga.json",  # or ~/.local/share/akanga/akanga.json
    maxBytes=10 * 1024 * 1024,  # 10 MB
    backupCount=7,               # keep one week of 10MB files
    encoding="utf-8",
)
file_handler.setFormatter(JsonFormatter())
logging.root.addHandler(file_handler)
```

### Option 4: Structured JSON + `jq` for Ad-Hoc Analysis

JSON logs are queryable with `jq` without any log server:

```bash
# All ERROR lines in the last 100MB of logs
cat akanga.json | jq 'select(.level == "ERROR")'

# All slow query warnings
cat akanga.json | jq 'select(.msg | startswith("SLOW QUERY"))'

# Count events by logger
cat akanga.json | jq -r '.logger' | sort | uniq -c | sort -rn
```

**Recommendation for local-first tools:** stderr for interactive use, rotating JSON
file for background services, systemd journal integration automatically when running
under systemd. No external log server needed until you have multiple machines.

---

## Applying This Module to Akanga

The Akanga-specific wiring is documented in `docs/learning/phase-04-concurrency-and-events.md`
(Logging and Debugging section). Here is a brief map of where each concept lands:

| Concept | Where it applies in Akanga |
|---|---|
| Module loggers (`__name__`) | Every `akanga_core/*.py` module |
| `configure_logging()` | `cli.py` — called at the start of each command handler |
| `--verbose` flag | All CLI commands: `serve`, `index`, `tui`, `mcp-server` |
| `@timed` decorator | `indexer.full_scan_and_index`, `db.search`, `rag.context_for_query` |
| EventBus debug subscriber | `app.py` — attached when `verbose=True` |
| `TimedConnection` | `db.py` — wraps the SQLite connection |
| `EXPLAIN QUERY PLAN` | Used during development to verify FTS5 and edge indexes |
| `MetricsRegistry` | `akanga_core/metrics.py` — exported at `GET /metrics` |
| Structured health endpoint | `server.py` — `GET /health` with DB, watcher, git checks |
| Rotating JSON file logs | `cli.py` `serve` command — optional `--log-file` flag |

---

## Quick Reference

```python
# Get a logger in any module
import logging
logger = logging.getLogger(__name__)

# Time any function (sync or async)
from akanga_core.observability import timed
@timed(level=logging.INFO)
def my_function(): ...

# Time a block
from akanga_core.observability import timed_block
with timed_block("operation_name", logger): ...

# Log a slow query warning automatically
conn = TimedConnection(sqlite3.connect(path), threshold_ms=50)

# Check a query's access plan
print(explain_query(conn, "SELECT * FROM nodes WHERE type = ?", ("note",)))

# Record a metric
from akanga_core.metrics import metrics
metrics.increment("nodes.indexed")
metrics.record("db.query_ms", elapsed_ms)

# Dump all metrics
print(metrics.snapshot())
```
