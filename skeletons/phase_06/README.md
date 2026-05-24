# Phase 6 — REST API

Add a FastAPI HTTP server that exposes the knowledge graph over a REST interface.

`server.py` is the only skeleton file — all prior-phase modules (parser, db,
indexer, links, eventbus, watcher, app) must be copied from your Phase 05 solution.

## What you will build

- `create_app(vault, db_path)` — FastAPI factory with lifespan DB init
- `POST   /api/v1/nodes`                — create node (SEC-02 path-traversal guard)
- `GET    /api/v1/nodes`                — list / FTS search with type/tag/pagination
- `GET    /api/v1/nodes/{id}`           — fetch single node by UUID
- `PUT    /api/v1/nodes/{id}`           — update title, content, or tags
- `DELETE /api/v1/nodes/{id}`           — delete file + DB row + edges (204)
- `GET    /api/v1/nodes/{id}/edges`     — all edges for node
- `GET    /api/v1/nodes/{id}/neighbors` — outgoing neighbor nodes
- `GET    /api/v1/nodes/{id}/backlinks` — nodes that link TO this node
- `POST   /api/v1/edges`                — create explicit typed edge
- `DELETE /api/v1/edges/{id}`           — delete edge by UUID (204)

## Security note — SEC-02 (Path Traversal)

The `POST /api/v1/nodes` endpoint **must** validate that the requested path
is within the vault directory:

```python
vault_root = Path(vault).resolve()
full_path = vault_root.joinpath(body.path).resolve()
if not full_path.is_relative_to(vault_root):
    raise HTTPException(status_code=400, detail="Path must be within vault")
```

Never skip this check — a malicious client could write files anywhere on disk.

## Running the tests

```bash
# From this directory
PYTHONPATH=src pytest -v
# Or via the repo Makefile
make test PHASE=6
```

## Running the server

```bash
# From this directory (after copying prior-phase solutions)
PYTHONPATH=src uvicorn akanga_core.server:create_app --factory \
    --host 127.0.0.1 --port 8000
```
