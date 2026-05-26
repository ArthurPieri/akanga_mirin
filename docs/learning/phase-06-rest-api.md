# Phase 6 — REST API

**Core concept:** The TUI talks directly to `akanga_core` as a Python library — same
process, no network. The REST API adds a second surface: an HTTP server that exposes
everything the library can do over a network boundary. This enables external clients
(curl scripts, the future Tauri GUI, third-party tools), and teaches the skill of
designing a contract that outlasts any single implementation.

**What makes this non-obvious:** The API is not just "wrap the library in HTTP." It
requires thinking about: what does a client actually need? What validates at the
boundary vs what trusts internal guarantees? What events should be pushed vs polled?

---

## Learning Objectives

By the end of this phase, you will be able to:
- Implement a full CRUD REST API with FastAPI, including proper HTTP status codes
- Understand FastAPI's lifespan context manager for startup/shutdown resource management
- Apply SEC-02 path traversal protection: `Path.resolve().is_relative_to(vault_root)`
- Write API tests using FastAPI's `TestClient` (synchronous) or `AsyncClient` (async)
- Configure CORS correctly for a local-only API (127.0.0.1, no public origins)

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the linked foundation doc before proceeding.

- [ ] I understand HTTP verbs (GET/POST/PUT/DELETE) and status codes → See `docs/foundations/http-fundamentals.md`
- [ ] I know what Pydantic models are and how FastAPI uses them for validation
- [ ] I understand async functions and FastAPI's async routing
- [ ] I've completed Phases 0–5

---

## Quick Start

```bash
make skeleton PHASE=6    # copy the starting code into ./src/
make test PHASE=6        # run the tests (they will fail initially)
make study PHASE=6       # open the tmux study session
make serve               # start the REST API server (after implementation)
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### REST (Representational State Transfer)

An architectural style for HTTP APIs. Resources are identified by URLs (`/api/v1/nodes/{id}`).
Operations are expressed as HTTP methods: GET (read), POST (create), PUT (replace),
DELETE (remove). Responses carry status codes that express outcome without reading
the body: 200 OK, 201 Created, 204 No Content, 404 Not Found, 422 Unprocessable Entity.
Stateless: every request contains all information needed to process it — no session
state on the server between requests.

> Akanga node: `REST`

→ Foundation doc: `docs/foundations/http-fundamentals.md`

### FastAPI

A Python web framework built on Starlette (async HTTP) and Pydantic (validation).
Type-annotated function signatures become the API contract: FastAPI reads the
annotations, validates incoming data automatically, and generates an OpenAPI spec
(browsable at `/docs`) without any extra configuration. Async-first: route handlers
are coroutines, so the API server and the active manager share the same asyncio loop
without blocking each other.

> Akanga node: `FastAPI`

### Lifespan Context Manager

FastAPI's pattern for startup and shutdown logic. A single `@asynccontextmanager`
function runs setup code before `yield` (on startup) and teardown code after `yield`
(on shutdown). For Akanga: startup loads vault config, indexes the vault, drains the
sync queue, starts the file watcher, starts the active manager. Shutdown stops the
watcher and active manager cleanly. Without proper shutdown, background threads and
asyncio tasks leak — the process hangs on exit.

> Akanga node: `Lifespan Context Manager`

### Pydantic Models

FastAPI uses Pydantic models for request validation and response serialization.
Define a model class with typed fields; FastAPI validates incoming JSON against it
and returns HTTP 422 with field-level error details if validation fails. Response
models strip internal fields (like `path`, which clients shouldn't see) and control
exactly what gets serialized. Pydantic is the boundary enforcer: it ensures the API
never receives malformed data and never leaks internal state.

> Akanga node: `Pydantic`

### WebSocket (Push Events)

A persistent, bidirectional connection initiated over HTTP and then upgraded. The
client opens one WebSocket connection to `/ws`; the server pushes events as JSON
messages whenever something changes: `node_updated`, `node_deleted`, `active_result`.
The client never needs to poll. This is how the Tauri GUI (v2) will receive live
updates — the same event model as the TUI's EventBus, but over the network.

> Akanga node: `WebSocket`

### Path Traversal Protection

A security vulnerability where a user-supplied file path escapes the intended
directory using `../` sequences. Example: a POST to create a node with
`path: "../../etc/crontab"` could overwrite system files if unchecked.
Protection: resolve the absolute path of the supplied filename, then assert it
starts with the vault root path. If not, reject with HTTP 400. This is the one
security check that must exist at the API boundary — internal code can trust paths
that have already been validated.

> Akanga node: `Path Traversal Protection`

→ Foundation doc: `docs/foundations/http-fundamentals.md` (security considerations section)

### API Boundary vs Library Consumer

The TUI is a library consumer: it imports `akanga_core` directly, calls functions,
and trusts internal invariants. The REST API is a boundary: it receives arbitrary
input from untrusted callers, validates everything, and translates between HTTP
concepts and internal data structures. This distinction determines where validation
lives. The library validates nothing (it trusts callers). The API validates
everything (it trusts nothing from the outside). Never duplicate validation inside
the library "just in case" — that's the API's job.

> Akanga node: `API Boundary`

### OpenAPI

A machine-readable specification of an HTTP API: endpoints, request schemas,
response schemas, status codes. FastAPI generates it automatically from type
annotations — zero extra work. Browsable at `/docs` (Swagger UI) and `/redoc`.
Useful for: exploring the API during development, generating client libraries,
writing integration tests against the spec. The spec is the contract; the
implementation must match it.

> Akanga node: `OpenAPI`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `REST` | note | `subtype_of` → `API Architectural Style`; `contrasts_with` → `WebSocket`; `is_applied_in` → `Akanga API` |
| `FastAPI` | reference | `implements` → `REST`; `uses` → `Pydantic`; `uses` → `asyncio` |
| `Lifespan Context Manager` | note | `is_part_of` → `FastAPI`; `solves` → `Resource Leak on Shutdown`; `is_applied_in` → `Akanga Server` |
| `Pydantic` | reference | `is_applied_in` → `FastAPI`; `implements` → `API Boundary`; `enables` → `Automatic Validation` |
| `WebSocket` | note | `contrasts_with` → `REST`; `enables` → `Push Events`; `is_applied_in` → `Akanga API` |
| `Path Traversal Protection` | note | `subtype_of` → `Security Pattern`; `is_applied_in` → `Akanga API`; `solves` → `Path Traversal Attack` |
| `API Boundary` | note | `contrasts_with` → `Library Consumer`; `qualifies` → `Pydantic`; `is_applied_in` → `Akanga API` |
| `OpenAPI` | note | `was_generated_by` → `FastAPI`; `documents` → `Akanga API`; `enables` → `Client Code Generation` |

---

## Endpoints

```
GET    /api/v1/nodes                    list / search nodes
POST   /api/v1/nodes                    create node (writes file + indexes)
GET    /api/v1/nodes/{id}               get node by UUID
PUT    /api/v1/nodes/{id}               update node (rewrites file)
DELETE /api/v1/nodes/{id}               delete node (removes file + deindexes)

GET    /api/v1/nodes/{id}/edges         outgoing edges
GET    /api/v1/nodes/{id}/neighbors     neighbor nodes (outgoing)
GET    /api/v1/nodes/{id}/backlinks     nodes linking TO this node
GET    /api/v1/nodes/{id}/ego-graph     ego-graph data (depth param)
GET    /api/v1/nodes/{id}/results       active check results

POST   /api/v1/edges                    create manual edge
DELETE /api/v1/edges/{id}              delete edge

GET    /api/v1/workspaces               list workspaces (from config)
GET    /api/v1/relations                list relation vocabulary (from config)

POST   /api/v1/sync/drain               trigger sync queue drain
GET    /api/v1/sync/queue               view pending sync jobs

GET    /api/v1/git/status               git repo status
POST   /api/v1/git/push                 push to remote

WebSocket /ws                           push events to connected clients
```

**Query parameters on `GET /api/v1/nodes`:**
`?query=` (FTS5 search) · `?type=` · `?tag=` · `?workspace=` · `?limit=` · `?offset=`

---

## Key Design Decisions

**Localhost-only by default.** The server binds to `127.0.0.1:8000` unless `--host`
overrides it. If the user binds to `0.0.0.0`, a startup warning is logged — there
is no auth mechanism at MVP. This is a deliberate scope decision, not an oversight.

**The API does not bypass the file system.** `POST /api/v1/nodes` writes a `.md` file
to the vault, then indexes it — the same path as any other write. There are no
database-only nodes. The file is always created first.

**Sync on write.** After every node write or delete, the file watcher will detect the
change within 500ms. The API does not need to manually trigger re-indexing — the
watcher handles it. This keeps the API stateless between write calls.

---

## What You Build

**`server.py`** — FastAPI application:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    # Note: GraphDatabase opens the connection in __init__ — no db.connect() call needed.
    # db = GraphDatabase(db_path) is called before passing db into the lifespan.
    # TODO: load_vault_config(vault) — reads akanga.yaml config; no skeleton
    # implementation exists yet (described in Phase 00 concepts). Add when implemented.
    indexer.full_scan_and_index(vault, db)
    sync_worker.drain(db, vault)
    watcher.start()
    active_manager.start()
    yield
    # shutdown
    active_manager.stop()
    watcher.stop()

app = FastAPI(lifespan=lifespan)
```

**Pydantic schemas (examples):**

```python
class NodeCreate(BaseModel):
    title: str
    type: Literal["note", "reference"]
    tags: list[str] = []
    graph: list[str] = []      # workspace names — resolved to IDs internally
    author: str | None = None  # defaults to vault config owner
    meta: dict = {}
    url: str = ""              # reference nodes only
    external_type: str = ""
    description: str = ""
    body: str = ""

class NodeResponse(BaseModel):
    id: str
    title: str
    type: str
    tags: list[str]
    graph: list[dict]          # [{name, id}]
    author: str
    created_at: str
    updated_at: str
    meta: dict
    edges: list[dict]
    # path is intentionally excluded from response
```

**WebSocket connection manager:**

```python
class ConnectionManager:
    def __init__(self): self.active: list[WebSocket] = []
    async def connect(self, ws: WebSocket): ...
    def disconnect(self, ws: WebSocket): ...
    async def broadcast(self, event: str, payload: dict): ...

# Wired to eventbus — on node_updated, broadcast to all WS clients
```

**`cli.py`** — Typer commands:

```
akanga index   --vault PATH --db PATH
akanga serve   --vault PATH --db PATH --host HOST --port PORT --git-init
akanga tui     --vault PATH --db PATH
akanga version
```

---

## Common Pitfalls

**Path traversal vulnerability (SEC-02):** `os.path.normpath + startswith` does NOT follow symlinks. Use `Path(body.path).resolve().is_relative_to(vault_root.resolve())` — the only safe approach.

**Forgetting `check_same_thread=False`:** SQLite connections opened outside the lifespan context and used across async routes will raise threading errors. Initialize once in lifespan, store in `app.state`.

**Returning 200 for creates:** Creates should return 201 (Created) with the new resource. A 200 is technically wrong and will fail strict clients.

**Not handling the DELETE of a non-existent node:** If the file is already gone (e.g., manual deletion), the DELETE endpoint should still return 404, not 500.

---

## Deliverable

```python
def test_create_and_get_node(client):
    resp = client.post("/api/v1/nodes", json={
        "title": "Test Node", "type": "note"
    })
    assert resp.status_code == 201
    node_id = resp.json()["id"]
    resp2 = client.get(f"/api/v1/nodes/{node_id}")
    assert resp2.status_code == 200
    assert resp2.json()["title"] == "Test Node"

def test_node_file_is_written(client, tmp_vault):
    client.post("/api/v1/nodes", json={"title": "Filed", "type": "note"})
    md_files = list(tmp_vault.glob("*.md"))
    assert any("Filed" in f.read_text() for f in md_files)

def test_delete_removes_file(client, tmp_vault):
    resp = client.post("/api/v1/nodes", json={"title": "Gone", "type": "note"})
    node_id = resp.json()["id"]
    client.delete(f"/api/v1/nodes/{node_id}")
    assert not any(node_id in f.stem for f in tmp_vault.glob("*.md"))

def test_path_traversal_rejected(client):
    resp = client.post("/api/v1/nodes", json={
        "title": "../../etc/crontab", "type": "note"
    })
    assert resp.status_code == 400

def test_search(client):
    client.post("/api/v1/nodes", json={
        "title": "Cognition Note", "type": "note", "tags": ["cognition"]
    })
    resp = client.get("/api/v1/nodes?tag=cognition")
    assert any(n["title"] == "Cognition Note" for n in resp.json())

def test_websocket_broadcast(client):
    with client.websocket_connect("/ws") as ws:
        client.post("/api/v1/nodes", json={"title": "WS Test", "type": "note"})
        msg = ws.receive_json(timeout=2)
        assert msg["event"] == "node_updated"

def test_ego_graph_endpoint(client):
    # create two nodes, edge between them, then call ego-graph
    ...
```

Plus 8 vault nodes with typed edges. The `test_node_file_is_written` and
`test_websocket_broadcast` tests are the most important — they prove the API
is not a DB-only shortcut and that push events work end-to-end.

---

## Reflect

> **Solo:** Why does Akanga's API bind to `127.0.0.1` instead of `0.0.0.0` by default? What attack surface would `0.0.0.0` open for a tool with no authentication?

> **Group:** The DB is a derived index that can be rebuilt. What does this mean for API design decisions? (E.g., should the API update the DB directly, or should it write the file and re-index? Which is the "right" approach and why?)
