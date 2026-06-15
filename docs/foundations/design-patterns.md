# Design Patterns in Akanga

**Audience:** developers reading Akanga's code who want the *why* behind each design choice · **Read time:** ~18 min

This document explains the software design patterns used in the Akanga knowledge graph. You will encounter all of these patterns as you work through Phases 0–8. Understanding the pattern before you write the code makes the "why" of each design decision legible.

---

## Why this document exists

Akanga is not just a knowledge graph — it is a worked example of how production Python systems are structured. The patterns below are not academic; every one of them appears verbatim in the codebase, chosen because it solved a real problem.

---

## 1. Observer (Pub/Sub) — EventBus

**What it is:** Objects subscribe to named topics. When an event is published to a topic, all subscribers are notified without the publisher knowing who is listening.

**Where:** `eventbus.py` — `EventBus.publish()`, `EventBus.subscribe()`

**Why Akanga uses it:** The file watcher publishes; the indexer, the git auto-commit batcher, and the TUI all need to react when a vault file changes. If the watcher called each of these directly, every new feature would require modifying the watcher. With the EventBus, each new consumer subscribes independently; the watcher never changes.

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

**Where:** `watcher.py` — `_EventHandler._debounced()` and `app.py` — `AkangaApp`'s git commit batcher (`_commit_loop` / `_flush_commit`)

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
db.get_neighbors(node_id)
db.search_fts("asyncio primer", limit=10)

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

**Why Akanga uses it:** The system has five subsystems: database, file watcher, event bus, git manager, and indexer. The server and TUI would need to construct and wire them all themselves — getting the startup order right and tearing down in the correct order on shutdown. `AkangaApp` (the Phase 8 composition root) encapsulates all of this. Callers call `start_all()` and `stop_all()`.

```python
# Caller sees one method
app.start_all()

# AkangaApp wires everything in the right order (start_all is synchronous)
def start_all(self) -> None:
    full_scan_and_index(self.vault_path, self.db)  # DB reflects the vault as of now
    self.watcher.start()                           # daemon thread reports changes
    self._start_commit_batcher()                   # debounced git auto-commits
```

**The ordering invariant:** the initial index runs *before* `watcher.start()`, so the
DB reflects the vault before any change event arrives, and shutdown stops the watcher
*before* flushing the final commit. The Facade encodes this ordering so callers cannot
get it wrong. (The bundled subscribers are synchronous; if you add an async one, call
`eventbus.set_loop(loop)` during startup — the bus buffers events published before the
loop is set, so there is no startup race to get wrong.)

---

## 6. Dependency Injection — Passing db and eventbus

**What it is:** Instead of a component creating its own dependencies, the dependencies are passed in by the caller.

**Where:** Every collaborator in the codebase — `VaultWatcher(vault_path, eventbus)`, `GraphDatabase(db_path)`, `AkangaApp(vault_path, db_path)`

**Why Akanga uses it:** Unit tests need to substitute a real SQLite database with an in-memory one, or a real EventBus with a mock. If `VaultWatcher` constructed its own `EventBus`, a test could not observe what it publishes. Passing dependencies in makes components testable in isolation.

```python
# Test can inject a fresh in-memory db and observe a real bus
db = GraphDatabase(":memory:")
watcher = VaultWatcher("./vault", EventBus())   # bus injected, not constructed inside

# Production wiring (AkangaApp does this for you)
app = AkangaApp(vault_path="./vault", db_path="./.akanga.db")
```

**Contrast with module-level singletons:** A common anti-pattern is `DB = GraphDatabase(settings.DB_PATH)` at module level. Module-level singletons are shared across all tests in a pytest session — one test's writes contaminate the next test's reads. Dependency injection solves this by making every test's dependencies independent.

---

## 7. Strategy — Active Node Action Types

**What it is:** Define a family of interchangeable algorithms (strategies) behind a common interface. The client picks which strategy to use at runtime without knowing how it works.

**Where:** *Deferred design — no phase builds this.* An earlier active-node design would
have put HTTP and TCP health-check actions behind one interface, dispatched on an
`action` field; it was cut (see `future-ideas.md`). The pattern is kept here because it
is the cleanest illustration of Strategy and the most likely shape a future extension
would take.

**Why the pattern fits:** Two interchangeable checks (HTTP endpoint vs TCP port) would
both produce the same result shape (up/down + timestamp). A caller dispatching on the
`action` field would call one `_check()` method regardless of kind; adding a new action
type (e.g. a CLI command) means adding a branch, not rewriting the caller.

---

## 8. Two-Phase Commit (Index then Link)

**What it is:** Split a write operation into two sequential passes: first write all objects, then write all relationships between them.

**Where:** `indexer.py` — `full_scan_and_index()` — first pass indexes all nodes, second pass extracts and resolves edges

**Why Akanga uses it:** When resolving a wikilink `[[B]]` in node A, node B must already be in the database so its UUID can be retrieved. If both passes ran simultaneously, a node that appears early in the scan might link to a node that has not been indexed yet — the link resolution would fail or produce a dangling edge. The two-pass approach guarantees that all nodes exist before any edges are created.

---

## 9. Labeled Property Graph

**What it is:** A graph data model with three ingredients: **nodes** that carry properties (key-value pairs), **edges** that carry a type label (the relation), and optionally properties on the edges themselves. This is the model behind Neo4j and most modern graph databases — as opposed to a plain hyperlink graph, where edges are anonymous, or RDF triples, where everything is a flat statement.

**Where:** The entire data model — `Node`, `Edge`, the frontmatter schema, and the 72-type relation vocabulary. Phase 1A is where you build it.

**Why Akanga uses it:** "A links to B" tells you almost nothing. "A *contradicts* B" or "A *depends_on* B" is a queryable fact. The label is what turns a pile of cross-referenced notes into a knowledge graph: you can filter traversals by relation type, ask directed questions ("what does this node refute?"), and compute meaningful neighborhoods.

How Akanga's files map onto the model:

```yaml
# frontmatter of vault/bfs.md
title: BFS
type: note              # node property
tags: [algorithms]      # node property
edges:
  - relation: contrasts_with    # edge label, from the 72-type vocabulary
    target: "[[DFS]]"
  - relation: is_applied_in     # second typed edge from the same node
    target: "[[Ego-Graph Endpoint]]"
```

- Every Markdown file is a **node**; its frontmatter keys (`title`, `type`, `tags`, `graph`) are the node's properties.
- Every frontmatter edge entry (and every inline `[[wikilink]]` shorthand) becomes an **edge**; its `relation` field is the label, drawn from the 72-type vocabulary in `relation-vocabulary.md`.
- The SQLite `edges` table stores `(source_id, target_id, relation)` — the relational projection of the same model. The files are the source of truth; the table is the derived index.

**The design consequence:** because the label lives on the edge, not the node, adding a new way for two notes to relate never requires touching either note's schema — you add one edge entry. That is the property-graph advantage over baking relationships into node fields.

---

## 10. Graph Traversal (BFS for Ego-Graphs)

**What it is:** Visiting the nodes of a graph outward from a starting node. Breadth-First Search (BFS) uses a queue and explores in expanding rings — every node at distance 1, then distance 2, and so on. Depth-First Search (DFS) follows one path as deep as it can before backtracking.

**Where:** `graph.py` — the ego-graph query you build in Phase 3 (`get_ego_graph(node_id, depth)`), which powers the TUI graph view and the `/ego-graph` endpoint.

**Why Akanga uses BFS:** an ego-graph is "everything within N hops of this node" — exactly the shape BFS produces, already grouped by distance. Two details are non-negotiable:

```python
from collections import deque

def ego_graph(db, root_id: str, max_depth: int = 2) -> set[str]:
    visited = {root_id}                  # 1. visited-set: break cycles
    queue = deque([(root_id, 0)])
    while queue:
        node_id, depth = queue.popleft()
        if depth >= max_depth:           # 2. depth limit: bound the result
            continue
        for neighbor in db.get_neighbors(node_id):
            if neighbor.id not in visited:
                visited.add(neighbor.id)
                queue.append((neighbor.id, depth + 1))
    return visited
```

1. **The visited-set breaks cycles.** Knowledge graphs are full of them (`A supports B`, `B refines A`). Without `visited`, the traversal loops forever.
2. **The depth limit bounds the result.** A well-connected vault is a small world — at depth 4 the "ego-graph" is usually the whole graph. The limit is what keeps the view local.

**Why not recursive DFS:** the natural recursive implementation puts one stack frame per traversal step on the Python call stack, which is capped (default `sys.getrecursionlimit()` is 1000). A long chain of notes — or a cycle you failed to detect — raises `RecursionError` in production. Iterative BFS with an explicit `deque` uses heap memory instead of stack frames, never hits the recursion limit, and gives you the by-distance ordering for free.

---

## 11. Dataclasses + Services (the deliberately anemic domain model)

**What it is:** Domain data lives in plain dataclasses that carry no behavior; the behavior lives in module-level functions that take their dependencies as arguments. The opposite of the *rich* domain object (`node.save()`, `node.link_to(other)`) you may expect from object-oriented Python — Martin Fowler calls this the "anemic domain model," and means it as a warning. Akanga adopts it on purpose.

**Where:** `models.Node` and `db.NodeRecord` are pure data; `graph.build_ego_graph(root_id, db)` and the indexer functions are the behavior.

```python
# Not this — the rich/active-record object
node.save()
node.link_to(other)
graph = node.ego_graph()        # where does the db come from?

# This — dumb data + a function that names its dependency
record = db.get_node(node_id)            # a frozen NodeRecord, no methods
ego = build_ego_graph(node_id, db)       # the db is right there in the signature
```

**Why Akanga uses it:** Graphs are the textbook OOP example — a `Node` object holding methods and direct references to its neighbours feels like the obvious model, and that instinct is fair. Three concrete forces push the other way:

1. **A self-saving `Node` welds the parse model to the storage model.** Akanga keeps two models apart on purpose (decision W9): `models.Node` is the round-trip parse model — it carries `content` and `frontmatter`; `db.NodeRecord` is the six-field DB read model — `@dataclass(frozen=True, slots=True)`, no body. A `node.save()` method would force one class to know both the frontmatter shape and the SQL schema, so a frontmatter change could ripple into a schema change. Two dumb dataclasses keep that seam honest: write path takes a `Node`, read path returns a `NodeRecord`.

2. **Behavior lives where its dependencies live.** `build_ego_graph(root_id, db)` openly declares the `db` it needs in its signature — which is exactly what makes Dependency Injection (§6) and isolated testing work. A `node.ego_graph()` method has no parameter to inject; it would have to reach for a hidden module-level `db` global, the very anti-pattern §6 exists to avoid.

3. **Dumb data crosses boundaries cleanly; live objects do not.** A `NodeRecord` is just six fields — it pickles, serializes to JSON, and travels across the watcher/async thread boundary without complaint. An object holding a live SQLite handle or a `threading.Lock` cannot be pickled, cannot be handed to another thread, and cannot be returned as an HTTP response body.

**Where the line is — this is not "never use classes":** `GraphDatabase` *is* a class, because it owns a resource: one shared connection plus the `threading.Lock` that serializes writes. That is the Repository pattern (§3), and a resource-owning object is precisely where a class earns its keep. The distinction is about what the object holds, not about avoiding `class`.

**The rule, stated crisply:** state that owns a resource → a class; data that crosses a boundary → a dataclass; behavior → a module function with injected dependencies.

> → You build the first of these dataclasses (`Edge`, `Node`) in Phase 1A.

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
| Strategy | *(deferred design)* | Sketched for the cut active-node design — swap health-check implementations behind one interface |
| Two-Phase Commit | `indexer.py` | Ensure referenced nodes exist before creating edges |
| Labeled Property Graph | `models.py`, frontmatter schema | Typed, queryable edges instead of anonymous links |
| Graph Traversal (BFS) | `graph.py` | Bounded ego-graphs with cycle-safe iteration |
| Anemic Domain Model | `models.py` + `graph.py` functions | Keep parse/storage models apart; data crosses boundaries, behavior is injected |

---

## Further Reading

- GoF Design Patterns (Gang of Four) — Observer, Strategy, Facade chapters
- *Python Concurrency with asyncio* — `run_coroutine_threadsafe` and thread/loop bridging
- SQLite WAL mode documentation — why Repository + WAL enables concurrent reads
- Python `tempfile` module docs — `mkstemp` and why `dir=` matters for atomicity
