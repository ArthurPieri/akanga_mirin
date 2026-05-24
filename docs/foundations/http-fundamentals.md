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
    return db.search_nodes(query=query, type=type, limit=limit, offset=offset)
```

### Pydantic models for request bodies

Declare the expected shape of a POST/PUT body as a Pydantic model. FastAPI
automatically parses JSON and validates it; invalid input returns a 422:

```python
from pydantic import BaseModel

class NodeCreate(BaseModel):
    title: str
    type: str = "note"
    tags: list[str] = []
    content: str = ""

@app.post("/api/v1/nodes", status_code=201)
async def create_node(payload: NodeCreate):
    # payload is a validated NodeCreate instance
    node = db.create_node(
        title=payload.title,
        type=payload.type,
        tags=payload.tags,
        content=payload.content,
    )
    return node
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

## In this codebase

- `src/akanga_core/server.py` — the full REST API. Every endpoint described in
  this document exists there.
- The WebSocket endpoint at `GET /ws` is in `server.py`; the client side is in
  `src/akanga_tui/app.py`.
- **Phase 3** of the learning path teaches HTTP fundamentals by reading
  `server.py` and adding a new endpoint from scratch.
- **Phase 5** covers the WebSocket broadcast mechanism and live TUI updates.
