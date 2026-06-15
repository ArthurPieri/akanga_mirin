# HTTP Fundamentals

A practical reference for HTTP, REST, and how FastAPI implements them —
directly applicable to reading `server.py` in akanga.

---

## The request / response model

HTTP is a client-server protocol. A client sends a **request**; a server returns
a **response**. Both are plain text (plus a body). The connection is stateless:
each request carries everything the server needs to process it. The server holds
no memory of previous requests.

```
Client                              Server
  |                                   |
  |  GET /api/v1/nodes?query=akanga   |
  |---------------------------------> |
  |                                   |  (looks up nodes, builds JSON)
  |  200 OK                           |
  |  Content-Type: application/json   |
  |  {"nodes": [...]}                 |
  | <-------------------------------- |
```

A request has:
- **Method** — what action to take
- **Path** — which resource to act on
- **Headers** — metadata (auth tokens, content type, etc.)
- **Body** — optional payload (usually JSON on POST/PUT)

A response has:
- **Status code** — numeric result
- **Headers** — metadata (content type, cache control, etc.)
- **Body** — the data (or empty)

---

## HTTP methods

The method tells the server *what kind of action* to perform on a resource.

| Method | Meaning | Typical use |
|--------|---------|-------------|
| GET | Retrieve | Fetch a node, list nodes, read edges |
| POST | Create | Create a new node or edge |
| PUT | Replace | Update an existing node (full replacement) |
| DELETE | Remove | Delete a node or edge |
| PATCH | Partial update | Rarely used in akanga; PUT is preferred |

**GET is safe and idempotent** — calling it ten times produces the same result as
calling it once and changes nothing on the server.

**PUT is idempotent** — calling it twice with the same body leaves the server in
the same state as calling it once.

**POST is neither** — calling it twice creates two resources.

---

## Status codes

Three-digit numbers grouped by category:
- **2xx** — success
- **4xx** — client error (the request was wrong)
- **5xx** — server error (the server failed)

The ones you'll see in `server.py`:

| Code | Name | When akanga uses it |
|------|------|---------------------|
| 200 | OK | GET returned data; PUT updated a node |
| 201 | Created | POST created a new node or edge |
| 204 | No Content | DELETE succeeded; no body to return |
| 400 | Bad Request | Malformed JSON; validation error |
| 404 | Not Found | Node UUID doesn't exist |
| 409 | Conflict | Duplicate title or UUID on create |
| 422 | Unprocessable Entity | FastAPI validation failed (Pydantic) |
| 500 | Internal Server Error | Unexpected exception (bug) |

---

## URL structure: path parameters vs query parameters

**Path parameters** identify a specific resource. They are part of the URL path
and are required.

```
GET /api/v1/nodes/3f8a1b2c-4d5e-6789-abcd-ef0123456789
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  path parameter: the node's UUID
```

**Query parameters** filter, sort, or paginate. They follow a `?` and are
optional.

```
GET /api/v1/nodes?query=akanga&type=active&limit=20&offset=0
                  ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                  query parameters
```

The distinction matters for REST design: path params identify *which* thing;
query params describe *how* to retrieve it.

---

## JSON bodies

POST and PUT requests send a JSON body. The server parses it and validates it
against an expected shape (a schema). A `Content-Type: application/json` header
tells the server the body is JSON.

Creating a node:
```json
POST /api/v1/nodes
Content-Type: application/json

{
  "title": "My New Node",
  "type": "note",
  "tags": ["python", "learning"],
  "content": "# My New Node\n\nHello world."
}
```

Server response on success:
```json
HTTP/1.1 201 Created
Content-Type: application/json

{
  "id": "3f8a1b2c-4d5e-6789-abcd-ef0123456789",
  "title": "My New Node",
  "type": "note",
  "tags": ["python", "learning"],
  "created_at": "2026-05-24T09:00:00Z"
}
```

---

## REST in practice

REST (Representational State Transfer) is a set of conventions for designing
HTTP APIs. In practice it means:

1. **Resources, not actions** — URLs name things (`/nodes`, `/edges`), not verbs
   (`/getNode`, `/createEdge`).
2. **Methods carry the verb** — the HTTP method says what to do (`GET`, `POST`,
   `DELETE`).
3. **Stateless** — each request is self-contained. No server-side session.
4. **Uniform interface** — the same conventions apply to every resource.

A REST-ish URL table for nodes:

| Method | Path | Action |
|--------|------|--------|
| GET | /api/v1/nodes | List all nodes |
| POST | /api/v1/nodes | Create a node |
| GET | /api/v1/nodes/{id} | Get one node |
| PUT | /api/v1/nodes/{id} | Replace a node |
| DELETE | /api/v1/nodes/{id} | Delete a node |
| GET | /api/v1/nodes/{id}/edges | Get a node's edges |
| GET | /api/v1/nodes/{id}/neighbors | Get neighbor nodes |

---

## FastAPI

FastAPI maps HTTP concepts directly to Python functions.

### Route decorators

The decorator binds a function to a method + path:

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/api/v1/nodes")
async def list_nodes():
    ...

@app.post("/api/v1/nodes")
async def create_node():
    ...

@app.delete("/api/v1/nodes/{node_id}")
async def delete_node(node_id: str):
    ...
```

### Path parameters

Curly braces in the path become function arguments. FastAPI validates the type:

```python
@app.get("/api/v1/nodes/{node_id}")
async def get_node(node_id: str):
    node = db.get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node
```

### Query parameters

Function arguments *not* in the path template are treated as query parameters.
Defaults make them optional:

```python
@app.get("/api/v1/nodes")
async def list_nodes(
    query: str | None = None,
    type: str | None = None,
    limit: int = 50,
    offset: int = 0,
):
    return db.search_fts(query=query, limit=limit)
```

### Pydantic models for request bodies

Declare the expected shape of a POST/PUT body as a Pydantic model. FastAPI
automatically parses JSON and validates it; invalid input returns a 422:

```python
from pydantic import BaseModel

class NodeCreate(BaseModel):       # the Phase 6 skeleton names this CreateNodeRequest
    title: str                     # required — omitting it returns HTTP 422
    type: str = "note"             # optional, defaults to "note"
    content: str = ""              # optional — the markdown body
    tags: list[str] = []           # optional
    path: str = ""                 # optional vault-relative path; validated (see Security considerations)

@app.post("/api/v1/nodes", status_code=201)
async def create_node(payload: NodeCreate):
    # payload is a validated NodeCreate instance
    # 1) Determine file path from payload.title (slugify — lowercase the title, collapse non-alphanumeric runs to hyphens — then join the vault path)
    # 2) write_node_file(str(file_path), {"title": payload.title, "type": payload.type}, payload.content or "")
    # 3) node = parse_node_file(str(file_path))
    # 4) db.upsert_node(node)
    # Build the response dict explicitly — don't return vars(node)/__dict__:
    # the DB read model is a slots dataclass (no __dict__), so vars() raises
    # TypeError, and an explicit dict keeps the JSON shape stable (Phase 6's rule).
    return {"id": node.id, "title": node.title, "type": node.type, "tags": node.tags}
```

### Returning status codes

Use `status_code` in the decorator for the success case. Raise `HTTPException`
for errors:

```python
from fastapi import HTTPException

@app.delete("/api/v1/nodes/{node_id}", status_code=204)
async def delete_node(node_id: str):
    ok = db.delete_node(node_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Node not found")
    # 204 = no body; FastAPI handles the empty response
```

---

## WebSockets

HTTP is request/response: the client must initiate every exchange. WebSockets
upgrade an HTTP connection into a **persistent, bidirectional channel** — either
side can send a message at any time.

The upgrade handshake:
```
Client: GET /ws HTTP/1.1
        Upgrade: websocket
        Connection: Upgrade

Server: HTTP/1.1 101 Switching Protocols
        Upgrade: websocket
```

After that, both sides communicate with **frames**, not requests. The connection
stays open until one side closes it.

In FastAPI:

```python
from fastapi import WebSocket

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            data = await ws.receive_text()   # block until client sends
            await ws.send_text(f"echo: {data}")
    except WebSocketDisconnect:
        pass   # client disconnected
```

In akanga, the server doesn't wait for client messages — it only *sends*.
Whenever a node event fires (created, updated, deleted), `ConnectionManager`
broadcasts JSON to every connected TUI client:

```python
await manager.broadcast(json.dumps({
    "event": "node_updated",
    "node_id": node.id,
    "title": node.title,
}))
```

The TUI listens and refreshes its view without polling.

---

## Security considerations

An HTTP API is a trust boundary: every value in a request — path parameters,
query strings, JSON fields — is attacker-controlled until proven otherwise. Two
controls matter for a local-first server like the one you build in Phase 6.

### Path containment: `Path.resolve()` + `is_relative_to()`

The create-node endpoint accepts an optional vault-relative `path` field. A
client-supplied file path is the classic injection point: it can attempt to
escape the vault and read or overwrite arbitrary files. The only safe pattern
is **resolve, then check containment**:

```python
candidate = (vault_root / payload.path).resolve()
if not candidate.is_relative_to(vault_root.resolve()):
    raise HTTPException(status_code=400, detail="Path escapes the vault")
```

**Why a `".." in path` substring check fails.** It validates the *name*, not the
*destination*, and misses two of the three real attack shapes:

1. **Relative traversal** — `"../../etc/passwd"`. The substring check catches
   this one, but `resolve()` handles it more robustly by collapsing the `..`
   segments before the containment test.
2. **Absolute paths** — `"/etc/passwd"` contains no `..` at all. Worse,
   `pathlib` joining with an absolute right-hand side **silently discards the
   left side**: `vault_root / "/etc/passwd"` is just `/etc/passwd`. A prefix or
   substring check on the unresolved string never sees this.
3. **Symlink escapes** — a symlink inside the vault that points outside it. The
   string looks perfectly vault-relative; only `resolve()`, which follows
   symlinks, reveals the true target.

All three must be rejected with HTTP 400. This is the SEC-02 check — the Phase 6
test suite exercises each shape.

### CORS: a localhost-only allowlist

CORS (Cross-Origin Resource Sharing) is a *browser* mechanism: it decides which
web origins may read responses from your server via JavaScript. For a local
knowledge-graph server the threat is a malicious page in an open browser tab
silently calling `http://localhost:8000` — so the allowlist must name only the
local origins you actually use:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
```

Never use `allow_origins=["*"]` — that lets any website's JavaScript read your
vault. And remember CORS only constrains browsers: `curl` and other non-browser
clients ignore it entirely. That is why the server also binds to `127.0.0.1` by
default — network-level isolation is the first line of defence; CORS is the
second; path containment is the third. Each control covers a failure of the one
above it.

---

## In your implementation (Phase 6)

- **Phase 6** is where you build the full REST API (`server.py` in your
  implementation): every endpoint, status code, and Pydantic model described in
  this document, plus the SEC-02 path containment check and the CORS allowlist
  from the section above.
- The WebSocket `/ws` broadcast (server pushes `node_updated` events; the TUI
  client refreshes without polling) is a Phase 6 stretch deliverable.
- The phase doc is `docs/learning/phase-06-rest-api.md`; the skeleton and
  `tests/phase_06/test_server.py` are the normative contract.
