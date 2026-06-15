# Phase 6 — REST API

**Estimated time:** 3–4 hours + ~1h vault/reflect

!!! warning "Changed 2026-06 (noteapp-alignment round)"
    Manual edge endpoints became file-first: `POST /api/v1/edges` now writes an `edges:`
    entry into the source note's frontmatter and reindexes (DELETE removes the entry), with
    new guards — 400 for self-edges, the reserved `wikilink` relation, or missing endpoints;
    409 for duplicates. New tests in `tests/phase_06/test_server.py`, including one that
    deletes the DB and asserts the edge survives. If you finished this phase before the
    change: rework `create_edge`/`delete_edge` per the rewritten WHAT/WHY/HOW in
    `skeletons/phase_06/src/akanga_core/server.py` (re-running `make skeleton PHASE=6`
    cannot update docstrings inside files you already own — open the skeleton file directly),
    and add the small `get_edge` accessor to your `GraphDatabase`.

**Core concept:** The TUI talks directly to `akanga_core` as a Python library — same
process, no network. The REST API adds a second surface: an HTTP server that exposes
everything the library can do over a network boundary. This enables external clients
(curl scripts, the future Tauri GUI (a Rust shell that packages a web frontend as a native desktop app), third-party tools), and teaches the skill of
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
the body: 200 OK, 201 Created, 204 No Content, 404 Not Found, 409 Conflict, 422 Unprocessable Entity.
Stateless: every request contains all information needed to process it — no session
state on the server between requests.

> Akanga node: `REST`

> → Foundation doc: `docs/foundations/http-fundamentals.md`

### FastAPI

A Python web framework built on Starlette (async HTTP) and Pydantic (validation).
Type-annotated function signatures become the API contract: FastAPI reads the
annotations, validates incoming data automatically, and generates an OpenAPI spec
(browsable at `/docs`) without any extra configuration. Async-first: route handlers
are coroutines on one asyncio loop, so slow I/O in one request never blocks the
others.

> Akanga node: `FastAPI`

### Lifespan Context Manager

FastAPI's pattern for startup and shutdown logic. A single `@asynccontextmanager`
function runs setup code before `yield` (on startup) and teardown code after `yield`
(on shutdown). For Akanga: startup opens the database and indexes the vault, so the API serves a
current index from the first request; shutdown closes the database. Without a clean
shutdown, the open connection and any background threads leak — the process can hang
on exit.

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
messages whenever something changes: `node_updated`, `node_deleted`.
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

> → Foundation doc: `docs/foundations/http-fundamentals.md` (security considerations section)

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
| `CORS` | note | `is_a` → `Browser Security Mechanism`; `solves` → `Cross-Site Request Forgery`; `is_applied_in` → `Akanga API` |

---

## Endpoints

The core endpoints below are in the skeleton (`skeletons/phase_06/src/akanga_core/server.py`)
and covered by `tests/phase_06/test_server.py` — they are the phase contract:

```
GET    /api/v1/nodes                    list / search nodes
POST   /api/v1/nodes                    create node (writes file + indexes)
GET    /api/v1/nodes/{id}               get node by UUID
PUT    /api/v1/nodes/{id}               update node (rewrites file)
DELETE /api/v1/nodes/{id}               delete node (removes file + deindexes)

GET    /api/v1/nodes/{id}/edges         all edges touching this node
GET    /api/v1/nodes/{id}/neighbors     neighbor nodes (outgoing)
GET    /api/v1/nodes/{id}/backlinks     nodes linking TO this node

POST   /api/v1/edges                    create manual edge (writes frontmatter edges: entry, then indexes)
DELETE /api/v1/edges/{id}              delete edge (removes the frontmatter entry; de-types the prose)

GET    /api/v1/templates                list available node templates
```

The following are stretch endpoints — not in the skeleton and not tested. Build them
only after the core suite is green (see "Stretch deliverables" in the Deliverable section):

```
GET    /api/v1/nodes/{id}/ego-graph     ego-graph data (?depth= · ?limit= — response carries "truncated": bool)
GET    /api/v1/workspaces               list workspaces (from config)
GET    /api/v1/relations                list relation vocabulary (from config)
POST   /api/v1/sync/drain               trigger sync queue drain
GET    /api/v1/sync/queue               view pending sync jobs
GET    /api/v1/git/status               git repo status
POST   /api/v1/git/push                 push to remote
WebSocket /ws                           push events to connected clients
```

**Query parameters on `GET /api/v1/nodes`:**
`?query=` (FTS5 search) · `?type=` · `?tag=` · `?limit=` · `?offset=` (`?workspace=` is stretch)

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

> **Security: CORS and Localhost Binding**

**What CORS is and why it matters for a local server:**

CORS (Cross-Origin Resource Sharing) is a browser security mechanism. When a
web page running at `http://evil.example.com` makes a JavaScript `fetch()` call
to `http://localhost:8000/api/v1/nodes`, the browser first sends a preflight
`OPTIONS` request asking: "does this server permit requests from my origin?" If
the server does not respond with the correct `Access-Control-Allow-Origin` header,
the browser blocks the response before the JavaScript code ever sees it.

This protects you from a class of attack called Cross-Site Request Forgery (CSRF):
a malicious web page silently reading your vault via your local server because
you happened to have a browser tab open. The attack does not require the user to
click anything — loading the page is enough.

**Why localhost binding is the first line of defence:**

The Akanga server binds to `127.0.0.1` by default. This means it only accepts
TCP connections from the same machine. A browser tab on the same machine *can*
reach it (CORS applies), but no device on your local network can reach it at all
— the connection is refused at the network layer before CORS is even relevant.

If you change `--host 0.0.0.0`, the server accepts connections from any device on
your network. At that point, anyone on the same Wi-Fi network can reach your vault.
CORS will not protect you from this — CORS only runs in browsers. A `curl` command
on a network-adjacent machine bypasses it entirely.

```
127.0.0.1 (default)  →  network-level isolation  →  no auth needed
0.0.0.0              →  network-exposed           →  CORS alone is not enough
```

**Safe CORS configuration for local-only use:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
```

`allow_origins` should list only the specific origins that need access: if you
are building a local web GUI that runs at `localhost:3000`, list exactly that.
Do not use `allow_origins=["*"]` — a wildcard allows any browser tab on any
site to read your vault content.

**What becomes dangerous if you expose on 0.0.0.0:**

| Setting | Localhost only | 0.0.0.0 (network-exposed) |
|---|---|---|
| `allow_origins=["http://localhost:3000"]` | Safe | Still safe for browsers, but non-browser callers bypass CORS |
| `allow_origins=["*"]` | Convenient | Any browser tab on any site can read your vault |
| No CORSMiddleware at all | Same-origin only (browser) | No browser cross-origin access |

**Relationship to path traversal protection:**

Path traversal protection (already in this phase) prevents a caller from escaping
the vault directory via crafted filenames. CORS prevents untrusted browser tabs from
reaching the server at all. These are independent controls at different layers:
network binding → CORS → path validation. Each layer fails open if the one above it
is misconfigured. All three need to be correct simultaneously.

> **If you expose on 0.0.0.0 for a legitimate reason** (e.g., accessing your vault
> from a phone on the same network), add basic HTTP authentication or bind to a VPN
> interface. There is no authentication mechanism in Akanga MVP — this is a documented
> and deliberate scope decision for a single-user local tool, but you must understand
> what you are trading away when you change the default binding.

---

## What You Build

**`server.py`** — FastAPI application (illustrative sketch — in the skeleton,
the lifespan is defined inside `create_app`):

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    # GraphDatabase opens the connection in __init__ — no db.connect() call needed.
    db = GraphDatabase(db_path)
    # The API serves the INDEX, so the vault must be indexed before the first request.
    # The scan is hash-first and idempotent, so an already-indexed vault is nearly free.
    full_scan_and_index(vault, db)
    yield
    # shutdown
    db.close()

app = FastAPI(lifespan=lifespan)
```

The tests construct the app through a **`create_app(vault, db_path)` factory** (see the
skeleton's `server.py`) — build the FastAPI instance inside the factory so tests can
spin it up against a temp vault and temp DB without global state leaking between runs.

The `full_scan_and_index` call in the lifespan is load-bearing, not decorative: **the
lifespan indexes the vault — the server starts serving N nodes from an existing vault
on a cold start**, with no dependency on the TUI or any earlier process having
populated the `.db`. Log the count at startup ("serving N indexed nodes") so an
empty graph is visibly a vault problem, not a silent one. The scan is hash-first and
idempotent, so re-running it on every startup is cheap.

**Pydantic request models** (these match the skeleton exactly — the skeleton and tests
are the normative contract):

```python
class CreateNodeRequest(BaseModel):
    title: str                  # required — omitting it returns HTTP 422
    type: str = "note"
    content: str = ""           # the markdown body (see terminology note below)
    tags: list[str] = []
    path: str = ""              # optional custom path within the vault

class UpdateNodeRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None

class CreateEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relation: str | None = None
    relation_id: str | None = None
```

**Why `path` is in the request model:** it is optional and always vault-relative
(e.g. `"projects/my-note.md"`). When omitted, the server auto-generates a slug
filename from the title (slugify: lowercase, non-alphanumeric runs collapsed to hyphens; see `textutil.slugify`). The field exists precisely so the SEC-02 containment check
has something to validate — a client-supplied path is the one input that can attempt
`../` escapes, absolute paths, or symlink tricks, and the create handler must
`resolve()` it and verify `is_relative_to(vault_root)` before writing anything.
One deliberate asymmetry: an explicit `path` that already exists gets **409 Conflict**
rather than a suffixed filename — a REST client stated exact intent and can retry with
a different path — while `create()` and the MCP `create_node` auto-suffix
(`my-note-1.md`), because a capture utility must never lose a note to a name collision
(decision N6).

**Frontmatter-level fields are not API fields:** `graph` (workspace names), `author`,
and `meta` live in the node's YAML frontmatter, not in the Phase 6 request model. The
skeleton's `CreateNodeRequest` carries only the five fields above; richer frontmatter
editing is out of scope for this phase's API.

**Terminology seam:** the API field `content`, the `Node` dataclass field `content`,
and "the markdown body" all name the same thing — the prose below the YAML
frontmatter; the docs use the three terms interchangeably.

**Responses are plain dicts**, not Pydantic models: `db.get_node()` returns a
small frozen record object (the reference solution names it `NodeRecord`). It
is not JSON-serializable and has no `content`/`frontmatter` fields, so build
the response dict explicitly
(`{"id": node.id, "title": node.title, "type": node.type, "tags": node.tags,
"path": str(node.path)}`) or use `dataclasses.asdict(node)`. Do **not** use
`vars(node)` — slots classes have no `__dict__`, so it raises `TypeError`.
See the skeleton's record-object note.

**WebSocket connection manager (stretch — untested, see Deliverable):**

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

**Path traversal vulnerability (SEC-02):** `os.path.normpath + startswith` does NOT follow symlinks, and a substring check like `".." in path` catches none of the real attack shapes reliably. Use `vault_root.joinpath(body.path).resolve().is_relative_to(vault_root.resolve())` — the only safe pattern. The test suite exercises three distinct escape shapes, and only resolve-then-contain defeats all of them:

- *Relative traversal* — `path: "../../etc/passwd"` (`test_create_node_path_traversal_blocked`). `resolve()` collapses the `..` segments so the containment check sees the real destination.
- *Absolute path* — `path: "/etc/passwd"`. `Path.joinpath` with an absolute right-hand side **silently discards the vault root** (`vault / "/etc/passwd"` is `/etc/passwd`), so the resolved path must still be checked with `is_relative_to` — a prefix/`startswith` check on the unresolved string never sees this.
- *Symlink escape* — a symlink inside the vault pointing outside it. The string looks vault-relative and contains no `..` at all; only `resolve()`, which follows symlinks, reveals the true target. This is why `normpath`/`startswith` and `".." in path` are banned — they validate the name, not the destination.

All three must return HTTP 400. SECURITY.md lists symlink escape as in-scope; the SEC-02 error-path tests in `tests/phase_06/test_server.py` cover these rejection cases.

**Forgetting `check_same_thread=False`:** SQLite connections opened outside the lifespan context and used across async routes will raise threading errors. Initialize once in lifespan, store in `app.state`.

**Returning 200 for creates:** Creates should return 201 (Created) with the new resource. A 200 is technically wrong and will fail strict clients.

**Not handling the DELETE of a non-existent node:** If the file is already gone (e.g., manual deletion), the DELETE endpoint should still return 404, not 500.

**DB-only manual edges violate Phase 2's "expendable DB" invariant.** The naive `POST /api/v1/edges` handler just calls `db.upsert_edge` and returns — the edge lives only in the index. But Phase 2 established that the DB is *derived*: `_reindex_edges` wipes a node's outgoing edges and rebuilds them from the file (`delete_edges_from` + re-derive) on the next index, and `rm *.db && scan` rebuilds the whole graph from the vault. A DB-only manual edge survives neither. The fix is *file-first*: write the edge into the **source node's frontmatter `edges:` block** (Phase 1A's source of truth) and then `index_file` the source, so the row is derived from the file like every other edge. `test_manual_edge_survives_db_rebuild` is the doctrine test — it deletes the `.db` and asserts the edge comes back. Two further wrinkles the suite pins: a typed inline `[[Target | relation]]` folds to a frontmatter entry with `target_id: ""`, so duplicate-detection and deletion must match by target title as well as id; and DELETE must *de-type the originating prose shorthand* (`[[Target | relation]]` → `[[Target]]`), or the next index re-folds the entry and the edge resurrects.

---

## Deliverable

The complete test suite is in `tests/phase_06/test_server.py`. The tests build the
app through your `create_app()` factory and exercise it with Starlette's `TestClient`.

Happy-path tests:

- `test_list_nodes_empty` — `GET /api/v1/nodes` on a fresh vault returns 200 and an empty list
- `test_create_node` — `POST /api/v1/nodes` returns 201 with a valid UUID `id`
- `test_get_node_by_id` / `test_get_node_not_found` — 200 with matching title; 404 for an unknown id
- `test_update_node` — `PUT` changes the title; a subsequent `GET` reflects it
- `test_delete_node` — `DELETE` returns 200/204; a subsequent `GET` returns 404
- `test_list_nodes_search` — `?query=` returns only matching nodes (FTS5 or LIKE fallback)
- `test_list_nodes_pagination` — `limit=2&offset=2` over 5 nodes returns exactly 2
- `test_create_and_get_edge` — `POST /api/v1/edges` returns 201; the edge appears in `/edges`
- `test_post_edge_writes_frontmatter_entry` — the edge is persisted to the source node's frontmatter `edges:` block
- `test_manual_edge_survives_db_rebuild` — the doctrine test: delete the `.db`, rescan, the edge is still there
- `test_reindex_after_post_does_not_duplicate` — re-indexing the source keeps each manual edge a single row
- `test_post_self_edge_returns_400` / `test_post_reserved_relation_returns_400` / `test_post_duplicate_edge_returns_409` — the guards
- `test_delete_edge_removes_frontmatter_entry` / `test_delete_folded_typed_edge_stays_dead` / `test_post_duplicate_of_folded_edge_returns_409` — delete removes the entry and de-types the prose; folded edges (`target_id: ""`) are matched by title
- `test_get_neighbors` / `test_get_backlinks` — A→B traversal in both directions
- `test_list_templates` — `GET /api/v1/templates` returns a non-empty list of template names

Error-path tests (the error-path requirement — every endpoint's failure mode is part of the contract):

- `test_create_node_path_traversal_blocked` — `path: "../../etc/passwd"` → 400 (SEC-02; see the pitfall above for the absolute-path and symlink-escape rejection cases the suite also covers)
- `test_create_node_missing_title_returns_422` — missing required field triggers Pydantic validation
- `test_delete_nonexistent_node` — deleting an unknown id → 404, not 500

Plus 9 vault nodes with typed edges (including the `CORS` node from the security callout).

### Stretch deliverables (untested)

These were previously billed as "most important" but have no tests yet — treat them
as extensions after the suite above is green:

- WebSocket `/ws` broadcast (`node_updated` events pushed to connected clients)
- A vault-file assertion test (POST writes a `.md` file; DELETE removes it) — the
  suite verifies create/delete via the API only, not by globbing the vault directory
- `GET /api/v1/nodes/{id}/ego-graph` and the other stretch endpoints listed above
  (workspaces, relations, sync, git)

---

## Reflect

> **Solo:** Why does Akanga's API bind to `127.0.0.1` instead of `0.0.0.0` by default? What attack surface would `0.0.0.0` open for a tool with no authentication?

> **Group:** The DB is a derived index that can be rebuilt. What does this mean for API design decisions? (E.g., should the API update the DB directly, or should it write the file and re-index? Which is the "right" approach and why?)
