# Akanga — Detailed Architecture

This document is the comprehensive technical reference for the Akanga knowledge
graph. It covers every module, class, design pattern, API endpoint, and
communication path in the system.

For the bird's-eye view, see `docs/architecture-overview.md`.

---

## 1. Module Map

| Module | File | Purpose |
|---|---|---|
| models | `akanga_core/models.py` | Node and Edge dataclasses |
| parser | `akanga_core/parser.py` | YAML frontmatter parsing, atomic file I/O, content hashing |
| db | `akanga_core/db.py` | Thread-safe SQLite wrapper with WAL and FTS5 |
| indexer | `akanga_core/indexer.py` | Full-text search via FTS5 with injection protection |
| links | `akanga_core/links.py` | Wiki-link extraction and path resolution |
| graph | `akanga_core/graph.py` | BFS ego-graph traversal |
| eventbus | `akanga_core/eventbus.py` | Thread-safe pub/sub with asyncio bridge |
| watcher | `akanga_core/watcher.py` | Filesystem monitoring (watchdog) + debouncing |
| gitmgr | `akanga_core/gitmgr.py` | Git operations via GitPython |
| app | `akanga_core/app.py` | Application orchestrator |
| server | `akanga_core/server.py` | FastAPI REST API + WebSocket |
| rag | `akanga_core/rag.py` | RAG context builder for LLM consumption |
| tui | `akanga_tui/app.py` | Textual terminal UI |
| mcp | `akanga_mcp/server.py` | FastMCP server for Claude integration |

---

## 2. Data Model

### Node

The fundamental unit of the knowledge graph. Each Markdown file in the vault
becomes exactly one Node.

```python
@dataclass
class Node:
    id: str                        # UUID — stable identity, survives renames
    title: str                     # from frontmatter, or filename fallback
    path: str                      # absolute path to the .md file
    body: str                      # Markdown content after the frontmatter
    frontmatter: dict[str, Any]    # all YAML metadata as a dictionary
```

Identity is the UUID in frontmatter, not the filename. If a file has no `id`
field, the parser falls back to an MD5 hash of the path. This guarantees that
edges remain valid even when files are renamed or moved.

### Edge

A typed directed relationship between two nodes.

```python
@dataclass
class Edge:
    source: str              # source node UUID
    target: str              # target node UUID
    relation: str | None     # one of 71 relation types, or None
```

### Edge Extraction

Edges are encoded as wiki-style links in Markdown body text:

```
[[Target Title]]              → relation defaults to "mentions"
[[Target Title|contradicts]]  → explicit relation type
```

The `links.extract_edges()` function uses the regex
`\[\[([^\]|]+)(?:\|([^\]]+))?\]\]` to extract `(target, relation)` tuples.
`resolve_path()` resolves targets: first relative to the current file's
directory, then relative to vault root, with automatic `.md` extension fallback.

### 71 Relation Types

Organized in 11 categories with prefix codes:

| Prefix | Category | Example Relations |
|---|---|---|
| EP | Epistemic | supports, contradicts, questions |
| HT | Hierarchical | is-part-of, contains, specializes |
| SC | Structural | depends-on, implements, extends |
| CT | Contextual | relates-to, contextualizes, exemplifies |
| AP | Application | applies, demonstrates, uses |
| DR | Derivation | derives-from, inspired-by, adapts |
| CC | Causal-Consequential | causes, prevents, enables |
| EV | Evaluative | critiques, validates, compares |
| PA | Parallel | parallels, contrasts, analogous-to |
| SO | Social | authored-by, cited-by, influenced-by |
| TC | Temporal-Chronological | precedes, follows, contemporaneous |

Full list: `docs/foundations/relation-vocabulary.md`.

---

## 3. Storage Layer

### Parser (`parser.py`)

Four functions, no classes:

| Function | Purpose |
|---|---|
| `parse_node_file(path)` | Reads a Markdown file via `python-frontmatter`, extracts YAML metadata and body, returns a `Node`. Falls back to filename for title, MD5 of path for ID. |
| `atomic_write(path, content)` | Creates a tempfile in the same directory, writes content, calls `fsync`, copies permissions from original, then `os.replace()` for atomic swap. Cleans up tempfile on failure. |
| `write_node_file(path, frontmatter_dict, content)` | Serializes frontmatter + body via `frontmatter.dumps()`, then calls `atomic_write()`. |
| `content_hash(path)` | SHA-256 of raw file bytes for change detection. |

The atomic write pattern guarantees that a crash mid-write never leaves a
partially-written file. `os.replace()` is an atomic filesystem operation on
POSIX systems — it either completes fully or has no effect.

### Database (`db.py`)

```python
class Database:
    def __init__(self, db_path: str) -> None
    def setup(self) -> None
    def upsert_node(self, node: Node) -> None
    def get_node(self, node_id: str) -> Node | None
    def get_all_nodes(self, limit: int = 100, offset: int = 0) -> list[Node]
    def get_neighbors(self, node_id: str) -> list[Node]
    def get_backlinks(self, node_id: str) -> list[Node]
    def delete_node(self, node_id: str) -> None
    def close(self) -> None
```

**Thread safety:** Every method acquires `threading.Lock` before touching the
connection. The connection is created with `check_same_thread=False` to allow
cross-thread access under the lock.

**Schema:**

```sql
CREATE TABLE nodes (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    path TEXT NOT NULL UNIQUE,
    body TEXT,
    frontmatter TEXT          -- JSON-serialized dict
);

CREATE TABLE edges (
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    relation TEXT,
    FOREIGN KEY (source) REFERENCES nodes(id) ON DELETE CASCADE
);

CREATE VIRTUAL TABLE nodes_fts USING fts5(
    title, body,
    content='nodes',
    content_rowid='rowid'
);
```

**FTS5 sync triggers:** Three triggers (AFTER INSERT, AFTER DELETE, AFTER UPDATE
on `nodes`) keep the `nodes_fts` virtual table in sync automatically. No
application code is needed to maintain the search index.

**WAL mode:** Enabled via `PRAGMA journal_mode=WAL`. Allows concurrent reads
while a write is in progress — critical because the watcher thread writes while
the TUI or API thread reads.

**Frontmatter storage:** The `frontmatter` column stores the full YAML metadata
as a JSON string. This preserves all user-defined fields without requiring schema
changes.

### Indexer (`indexer.py`)

```python
def search_fts(db: Database, query: str) -> list[dict]
```

Splits the query into terms, wraps each in double quotes to prevent FTS5
operator injection (SEC-06). Without this, a user searching for `NEAR` or `AND`
would trigger FTS5 operators instead of a literal text match. Results are ordered
by FTS5 rank (relevance).

---

## 4. Graph Algorithms (`graph.py`)

### Data Structures

```python
class EdgeDirection(Enum):
    OUTGOING = "outgoing"
    INCOMING = "incoming"

@dataclass
class EgoEdge:
    source_id: str
    target_id: str
    relation: str
    relation_id: str
    direction: EdgeDirection

@dataclass
class EgoGraph:
    root: Node
    nodes: dict[str, Node]
    edges: list[EgoEdge]
```

### BFS Ego-Graph Traversal

```python
def build_ego_graph(root_id: str, db: Database, max_depth: int = 2) -> EgoGraph
```

1. Initialize a visited set with the root node
2. BFS queue holds `(node_id, depth)` pairs
3. At each node: query both outgoing neighbors AND incoming backlinks
4. Add unvisited nodes to the queue, record all edges regardless
5. Stop expanding nodes at `max_depth`
6. Return `EgoGraph` containing all discovered nodes and edges

Depth 2 is the practical default: depth 1 misses multi-hop reasoning, depth 3+
explodes combinatorially (a node with 10 neighbors at depth 3 could touch
10^3 = 1000 nodes).

---

## 5. Runtime Services

### EventBus (`eventbus.py`)

```python
class EventBus:
    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None
    def subscribe(self, event: str, handler: Callable) -> None
    def unsubscribe(self, event: str, handler: Callable) -> None
    def publish(self, event: str, **kwargs: Any) -> None
```

**Pattern:** Observer / pub-sub with three key design choices:

1. **Handler snapshot:** `publish()` copies the handler list under the lock
   before iterating. This prevents deadlocks if a handler modifies subscriptions
   during dispatch.

2. **Async bridge:** For coroutine handlers, uses
   `loop.call_soon_threadsafe(lambda: asyncio.create_task(handler(**kwargs)))`.
   This safely schedules async work from a synchronous thread context.

3. **Error isolation:** Each handler invocation is wrapped in `try/except`.
   One failing subscriber never breaks other subscribers.

**Events in the system:**

| Event | Published by | Payload | Subscribers |
|---|---|---|---|
| `file_changed` | VaultWatcher (via Debouncer) | `path: Path` | AkangaApp |
| `file_deleted` | VaultWatcher | `path: Path` | AkangaApp |
| `node_updated` | AkangaApp | `node_id: str` | TUI, WebSocket handler |

### VaultWatcher + Debouncer (`watcher.py`)

**VaultWatcher** wraps `watchdog.observers.Observer` for cross-platform
filesystem monitoring (inotify on Linux, FSEvents on macOS, ReadDirectoryChangesW
on Windows).

```python
class VaultWatcher:
    def __init__(self, vault: Path, eventbus: EventBus, debounce_ms: int = 500)
    def start(self) -> None
    def stop(self) -> None
```

**Event routing:**

| FS Event | Action |
|---|---|
| `on_modified`, `on_created` | Schedule debounced processing |
| `on_deleted` | Immediately publish `file_deleted` + cancel pending debounce |
| `on_moved` | Delete old path + schedule new path |

**Filtering:** Ignores hidden files (`.` prefix in any path component), swap
files (`.swp`, `.swo`, `.tmp`, `~` suffix), and non-Markdown files. Path
validation via `is_relative_to(vault)` prevents watching outside the vault.

**Debouncer** coalesces rapid FS events. A single save in nvim fires 5-10
events within 50ms. Without debouncing, the indexer would re-index the same
file 10 times per save.

```python
class Debouncer:
    def __init__(self, callback: Callable[[str], None], debounce_ms: int = 500)
    def submit(self, path: str) -> None
    def cancel(self, path: str) -> None
    def stop(self) -> None
```

Implementation: A background daemon thread polls a `pending` dict every 50ms.
Each `submit(path)` sets `fire_time = now + 500ms`. When `fire_time` passes
without being reset, the callback executes. Thread safety via `threading.Lock`
on the pending dict, `threading.Event` for stop signal.

### GitManager (`gitmgr.py`)

```python
class GitManager:
    def __init__(self, vault_path: str | Path) -> None
    def ensure_repo(self) -> Repo | None
    def stage_and_commit(self, paths: list[str | Path], message: str) -> str | None
```

**`stage_and_commit` flow:**
1. Convert absolute paths to vault-relative paths
2. Validate each path is inside the vault (path traversal guard)
3. Stage via `repo.index.add(rel_paths)`
4. Check `repo.is_dirty(index=True)` to skip empty commits
5. Commit with the provided message
6. Return the commit SHA, or `None` on failure

**Graceful degradation:** If GitPython is not installed (`ImportError`) or the
vault is not a git repo (`InvalidGitRepositoryError`), all operations silently
return `None`. The rest of the system continues to work without git.

### AkangaApp (`app.py`) — The Orchestrator

```python
class AkangaApp:
    def __init__(self, vault_path: str, db_path: str = "akanga.db")
    def start_all(self) -> None
```

**Owns:** Database, EventBus, VaultWatcher, GitManager.

**Wires:** Subscribes to `file_changed` and `file_deleted` events at init time.

**`_on_file_changed(path)` pipeline:**
1. `parse_node_file(path)` — read the file into a Node
2. `db.upsert_node(node)` — store/update in SQLite
3. `events.publish("node_updated", node_id=node.id)` — notify frontends
4. `git.stage_and_commit([path], message)` — auto-commit the change

**Pattern:** Mediator — AkangaApp mediates between all components. No component
references another directly; they all communicate through AkangaApp and the
EventBus.

---

## 6. Interface Layer

### REST API (`server.py`)

**Framework:** FastAPI. Created via a factory function:

```python
def create_app(akanga_app: AkangaApp) -> FastAPI
```

**Endpoints:**

| Method | Path | Parameters | Response | Purpose |
|---|---|---|---|---|
| GET | `/nodes` | `limit`, `offset` | `list[Node]` | Paginated node listing |
| GET | `/nodes/{node_id}` | — | `Node` or 404 | Single node by UUID |
| GET | `/graph/{node_id}` | `depth` (default 2) | `EgoGraph` or 404 | Ego-graph subgraph |
| WS | `/ws` | — | JSON messages | Real-time update stream |

**WebSocket protocol:** On connect, the handler subscribes to EventBus
`node_updated`. Each update pushes `{"event": "node_updated", "id": "..."}` to
the client. On disconnect, the handler unsubscribes.

**Error handling:** Missing nodes return HTTP 404. `ValueError` from
`build_ego_graph` (unknown node) is caught and returned as 404.

### Terminal UI (`akanga_tui/app.py`)

**Framework:** Textual (rich terminal UI library built on Rich).

```python
class AkangaTUI(App):
    def __init__(self, db_path: str, vault_path: Path, event_bus: EventBus)
```

**Layout:**

```
┌──────────────────────────────────────────────┐
│ Header                                        │
├─────────────┬────────────────────────────────┤
│ Filter: [  ]│ Markdown content               │
│ ─────────── │                                │
│ Node 1      │                                │
│ Node 2      │                                │
│ Node 3      │────────────────────────────────│
│ ...         │ Ego-graph panel                │
├─────────────┴────────────────────────────────┤
│ Footer                                        │
└──────────────────────────────────────────────┘
```

**Custom widget:** `NodeItem(ListItem)` stores `node_id` and `title`, allowing
the selection handler to look up the full node from the database.

**Interaction flow:**
1. On mount: subscribe to `node_updated`, set EventBus asyncio loop, load all nodes
2. User types in filter input: `_update_list_view()` filters by title substring
3. User selects a node: `_show_node()` fetches from DB, renders body as Markdown,
   builds ego-graph and renders it in the bottom panel
4. EventBus fires `node_updated`: `_on_node_updated` calls `_refresh_node_list`
   via `call_from_thread` to safely update the UI from an async context

---

## 7. AI Integration Layer

### RAG Context Builder (`rag.py`)

```python
MAX_CONTEXT_CHARS = 12_000
MAX_BODY_CHARS = 500

def build_context(
    node_id: str,
    max_triples: int = 80,
    db: Database = None,
    vault: Path = None,
) -> str
```

**Pipeline:**
1. Build BFS ego-graph at depth 2 from the target node
2. Collect entities: for each node, read body from disk (not DB), cap at 500 chars
3. Root node listed first, then neighbors
4. Stop adding entities if total exceeds 12k chars (reserve ~1k for triples)
5. Serialize edges as typed triples: `"Source --[relation]--> Target"`
6. Incoming edges get an inverse relation: `"Target --[is_relation_by]--> Source"`
7. Stop adding triples at the 80-triple cap or character limit
8. Wrap everything in `<graph_context>...</graph_context>` delimiters

**Why `<graph_context>` delimiters?** SEC-01 mitigation: prompt injection
protection. The delimiters let the LLM distinguish between its instructions
and injected graph content.

**Why max_triples=80, not 200?** 200 triples at ~160 chars each = ~32k chars,
far exceeding the 12k context cap. 80 triples stays comfortably within budget.

**Why read body from disk?** The DB stores body text, but reading from disk
ensures the context always reflects the latest file state, even if the DB
is slightly behind due to debouncing.

### MCP Server (`akanga_mcp/server.py`)

**Framework:** FastMCP (Python SDK for Model Context Protocol).

```python
mcp = FastMCP("Akanga Mirin")

@mcp.tool()
def search_nodes(query: str) -> list[dict]

@mcp.tool()
def get_graph_context(node_id: str) -> str
```

**Transport:** stdio — designed for Claude Desktop subprocess integration.
Claude launches the server as a child process and communicates via stdin/stdout
using JSON-RPC 2.0.

**Security:** Binds to `127.0.0.1` only (SEC-04). No network exposure.

**Initialization:** `init_server(vault, db_path)` sets module-level globals.
Entry point reads `AKANGA_VAULT_PATH` and `AKANGA_DB_PATH` from environment
variables.

**Tool details:**

| Tool | Input | Output | Delegates to |
|---|---|---|---|
| `search_nodes` | search query string | list of node dicts | `indexer.search_fts()` |
| `get_graph_context` | node UUID | wrapped context string | `rag.build_context()` |

---

## 8. Design Patterns

| Pattern | Where | Purpose |
|---|---|---|
| Dataclass (Value Object) | Node, Edge, EgoEdge, EgoGraph | Data containers with structural equality |
| Repository | Database class | Abstracts SQLite behind typed CRUD methods |
| Observer (pub/sub) | EventBus | Decouples producers from consumers |
| Debounce | Debouncer class | Coalesces rapid events into single actions |
| Mediator | AkangaApp | Central coordinator that wires all components |
| Factory | `create_app()` | Constructs FastAPI with injected dependencies |
| Atomic Write | `atomic_write()` | Crash-safe file operations via tempfile + os.replace |
| Bridge | EventBus async bridge | Connects thread world to asyncio world |
| Facade | MCP Server tools | Simple tool interface over complex graph operations |
| Graceful Degradation | GitManager | System works without optional dependencies |

---

## 9. Communication Paths

Every inter-component communication in the system:

### Write Path (file change to index update)

```
User edits .md file
  → OS fires filesystem events
  → VaultWatcher receives via watchdog Observer
  → Debouncer coalesces (500ms window)
  → EventBus.publish("file_changed", path=...)
  → AkangaApp._on_file_changed(path)
    → parser.parse_node_file(path) → Node
    → db.upsert_node(node)
    → FTS5 triggers auto-sync the search index
    → EventBus.publish("node_updated", node_id=...)
    → git.stage_and_commit([path], message)
```

### Read Path (query to response)

```
Full-text search:
  User query → search_fts(db, query) → FTS5 MATCH → ranked results

Graph traversal:
  node_id → build_ego_graph(root_id, db, depth=2) → BFS → EgoGraph

RAG context:
  node_id → build_context() → BFS ego-graph → entity list + typed triples
  → <graph_context> wrapped string
```

### Real-Time Update Paths

```
TUI live update:
  EventBus("node_updated")
  → AkangaTUI._on_node_updated (async handler)
  → call_from_thread(_refresh_node_list)
  → ListView re-rendered

WebSocket push:
  EventBus("node_updated")
  → WebSocket on_update handler (async)
  → websocket.send_json({"event": "node_updated", "id": ...})
  → Client receives JSON
```

### MCP Tool Calls

```
Claude calls search_nodes(query):
  → MCP JSON-RPC request via stdio
  → search_fts(db, query)
  → JSON-RPC response with results

Claude calls get_graph_context(node_id):
  → MCP JSON-RPC request via stdio
  → build_context(node_id, db, vault)
  → BFS → triples → <graph_context> string
  → JSON-RPC response
```

---

## 10. Frontend Integration Guide

A new frontend (web SPA, mobile app, CLI tool) can integrate with Akanga
through three paths:

### Option A: REST API

Use the HTTP endpoints for standard CRUD and graph queries:
- `GET /nodes` — paginated node listing
- `GET /nodes/{id}` — single node with full body
- `GET /graph/{id}?depth=2` — ego-graph subgraph
- `WS /ws` — real-time `node_updated` events

Best for: web frontends, mobile apps, any HTTP-capable client.

### Option B: MCP Server

Use the MCP tools for AI-powered interfaces:
- `search_nodes(query)` — full-text search
- `get_graph_context(node_id)` — pre-formatted context for LLMs

Best for: AI assistants, Claude integrations, chatbot interfaces.

### Option C: Direct Library Import

Import `akanga_core` and use `AkangaApp` as the entry point:

```python
from akanga_core.app import AkangaApp

app = AkangaApp(vault_path="./vault", db_path="./akanga.db")
app.start_all()

# Use app.db for queries, app.events for real-time
```

Best for: Python applications, plugins, custom tooling.

### Shared Infrastructure

All three paths share the same Database and EventBus. A change detected by the
watcher propagates to every connected frontend simultaneously. There is no
authentication layer — this is a local-first, single-user system by design.
