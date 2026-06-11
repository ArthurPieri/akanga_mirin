"""FastAPI REST server for the Akanga knowledge graph (Phase 06).

The factory pattern (``create_app(vault, db_path)``) lets tests and the
CLI create the app with different vault/db paths without global state
leaking between runs: the ASGI lifespan opens the ``GraphDatabase`` on
startup, parks it in ``_app_state``, and closes it on shutdown.

SEC-02 — path traversal protection — is enforced on EVERY filesystem
path the API touches, with ``Path.resolve()`` + ``is_relative_to()``:

- ``../../etc/passwd`` (relative escape) resolves outside the vault;
- ``/etc/passwd`` (absolute) silently REPLACES the vault root in
  ``joinpath`` — a '..'-substring check can never catch it;
- ``link/x.md`` through a symlink looks vault-relative lexically but
  ``resolve()`` follows the symlink to its real, outside location.

CORS (S2) is restricted to explicit localhost origins. NEVER ``"*"`` —
the API is unauthenticated, so the origin allowlist is the only thing
standing between a malicious web page and the vault.
"""
from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import GraphDatabase
from .parser import content_hash, parse_node_file, write_node_file

# ── APIRouter — handlers register here; create_app() includes the router ──────
router = APIRouter()

# Built-in node templates exposed via GET /api/v1/templates.
TEMPLATES = ["note", "active-http", "active-tcp", "active-service", "virtual", "diagram"]


# ── Pydantic request models ────────────────────────────────────────────────────


class CreateNodeRequest(BaseModel):
    title: str
    type: str = "note"
    content: str = ""
    tags: list[str] = []
    path: str = ""  # Optional custom path within vault


class UpdateNodeRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class CreateEdgeRequest(BaseModel):
    source_id: str
    target_id: str
    relation: str | None = None
    relation_id: str | None = None


# ── App state ──────────────────────────────────────────────────────────────────

_app_state: dict[str, Any] = {}


def get_db() -> GraphDatabase:
    """Return the shared GraphDatabase, failing LOUDLY if uninitialised.

    Route handlers are plain functions and cannot see create_app()'s
    locals; the lifespan parks the open DB here. An explicit RuntimeError
    beats a confusing KeyError deep inside a handler.
    """
    if "db" not in _app_state:
        raise RuntimeError("App not initialized. Call create_app() first.")
    return _app_state["db"]


def _vault_root() -> Path:
    """The vault root, resolved once per call so symlinks are normalised."""
    if "vault" not in _app_state:
        raise RuntimeError("App not initialized. Call create_app() first.")
    return Path(_app_state["vault"]).resolve()


def _safe_vault_path(candidate: str | Path, vault_root: Path) -> Path:
    """SEC-02 gate: resolve *candidate* and require it stays in the vault.

    ``resolve()`` collapses ``..`` segments AND follows symlinks, and
    ``joinpath`` with an absolute candidate discards the vault root
    entirely — so the only safe check is on the fully resolved path.
    Raises HTTP 400 on escape; returns the resolved path otherwise.
    """
    full_path = vault_root.joinpath(candidate).resolve()
    if not full_path.is_relative_to(vault_root):
        raise HTTPException(status_code=400, detail="Path escapes the vault (SEC-02)")
    return full_path


def _node_dict(node: Any) -> dict[str, Any]:
    """Convert a db SimpleNamespace node into a JSON-serializable dict."""
    return {
        "id": node.id,
        "title": node.title,
        "type": node.type,
        "tags": list(node.tags),
        "path": str(node.path),
    }


def _node_disk_path(node: Any, vault_root: Path) -> Path:
    """Resolve a node's stored path (vault-relative or absolute) to disk.

    Re-validated through the SEC-02 gate even though it came from our own
    DB — defence in depth against a row written by older/buggy code.
    """
    stored = Path(str(node.path))
    candidate = stored if stored.is_absolute() else vault_root / stored
    return _safe_vault_path(candidate, vault_root)


# ── App factory ────────────────────────────────────────────────────────────────


def create_app(
    vault: str | None = None,
    db_path: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    Wires up the lifespan (open/close the DB), the CORS allowlist, and
    all ``/api/v1`` routes. Vault and DB locations come from the
    arguments or the ``AKANGA_VAULT`` / ``AKANGA_DB`` environment
    variables.
    """
    vault = vault or os.environ.get("AKANGA_VAULT", "./vault")
    db_path = db_path or os.environ.get("AKANGA_DB", "./.akanga.db")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db = GraphDatabase(db_path)
        _app_state["db"] = db
        _app_state["vault"] = vault
        try:
            yield
        finally:
            db.close()
            _app_state.pop("db", None)
            _app_state.pop("vault", None)

    app = FastAPI(title="Akanga Knowledge Graph API", lifespan=lifespan)

    # S2: explicit localhost dev origins only — a wildcard would let ANY
    # website the user's browser visits talk to this unauthenticated API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    return app


# ── Node routes ────────────────────────────────────────────────────────────────


@router.post("/api/v1/nodes", status_code=201)
def create_node(body: CreateNodeRequest) -> dict[str, Any]:
    """Create a node: validate the path (SEC-02), write the file, index it."""
    db = get_db()
    vault_root = _vault_root()

    relative = body.path or (body.title.lower().replace(" ", "_") + ".md")
    full_path = _safe_vault_path(relative, vault_root)

    if full_path.exists():
        raise HTTPException(status_code=409, detail="A node already exists at this path")

    # Mint the UUID up front and persist it in the frontmatter so a
    # re-parse never churns the identity.
    fm = {"id": str(uuid4()), "title": body.title, "type": body.type, "tags": body.tags}
    write_node_file(str(full_path), fm, body.content)

    node = parse_node_file(str(full_path))
    node.content_hash = content_hash(str(full_path))
    db.upsert_node(node)

    created = db.get_node(node.id)
    return _node_dict(created)


@router.get("/api/v1/nodes")
def list_nodes(
    query: str = "",
    type: str = "",  # noqa: A002 — query-parameter name is part of the API contract
    tag: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List nodes with optional FTS search, type/tag filters, and pagination."""
    db = get_db()
    nodes = db.search_fts(query, limit=limit) if query else db.list_nodes(limit, offset)
    if type:
        nodes = [n for n in nodes if n.type == type]
    if tag:
        nodes = [n for n in nodes if tag in n.tags]
    return [_node_dict(n) for n in nodes]


@router.get("/api/v1/nodes/{node_id}")
def get_node(node_id: str) -> dict[str, Any]:
    """Retrieve a single node by UUID; 404 when unknown."""
    node = get_db().get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return _node_dict(node)


@router.put("/api/v1/nodes/{node_id}")
def update_node(node_id: str, body: UpdateNodeRequest) -> dict[str, Any]:
    """Update title/content/tags in both the file and the DB.

    The body content is re-read from disk first — the DB stores no prose,
    so writing without re-reading would silently blank the note whenever
    the client sends only a title change.
    """
    db = get_db()
    existing = db.get_node(node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Node not found")

    vault_root = _vault_root()
    path = _node_disk_path(existing, vault_root)

    current = parse_node_file(str(path))
    fm = dict(current.frontmatter)
    fm["id"] = existing.id  # never lose the UUID
    fm["title"] = body.title if body.title is not None else existing.title
    fm["type"] = existing.type  # type is not updatable via this endpoint
    fm["tags"] = body.tags if body.tags is not None else existing.tags
    new_content = body.content if body.content is not None else current.content

    write_node_file(str(path), fm, new_content)
    node = parse_node_file(str(path))
    node.content_hash = content_hash(str(path))
    db.upsert_node(node)

    return _node_dict(db.get_node(node_id))


@router.delete("/api/v1/nodes/{node_id}", status_code=204)
def delete_node(node_id: str) -> None:
    """Delete a node's file and its DB row (edges included); 404 if unknown."""
    db = get_db()
    existing = db.get_node(node_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Node not found")

    path = _node_disk_path(existing, _vault_root())
    if path.exists():
        os.remove(path)
    # GraphDatabase.delete_node removes the FTS row plus edges in BOTH
    # directions (outgoing via CASCADE and explicitly, incoming explicitly).
    db.delete_node(node_id)


# ── Edge / graph routes ────────────────────────────────────────────────────────


@router.get("/api/v1/nodes/{node_id}/edges")
def get_node_edges(node_id: str) -> list[dict[str, Any]]:
    """Raw edge rows where the node is source OR target."""
    db = get_db()
    if db.get_node(node_id) is None:
        raise HTTPException(status_code=404, detail="Node not found")
    with db._lock:
        rows = db.conn.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/api/v1/nodes/{node_id}/neighbors")
def get_node_neighbors(node_id: str) -> list[dict[str, Any]]:
    """Immediate neighbours reachable via OUTGOING edges."""
    db = get_db()
    if db.get_node(node_id) is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return [_node_dict(n) for n in db.get_neighbors(node_id)]


@router.get("/api/v1/nodes/{node_id}/backlinks")
def get_node_backlinks(node_id: str) -> list[dict[str, Any]]:
    """Nodes that link TO this node (incoming edges)."""
    db = get_db()
    if db.get_node(node_id) is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return [_node_dict(n) for n in db.get_backlinks(node_id)]


@router.post("/api/v1/edges", status_code=201)
def create_edge(body: CreateEdgeRequest) -> dict[str, Any]:
    """Create a manual typed edge between two EXISTING nodes (400 otherwise)."""
    db = get_db()
    if db.get_node(body.source_id) is None:
        raise HTTPException(status_code=400, detail="source_id does not exist")
    if db.get_node(body.target_id) is None:
        raise HTTPException(status_code=400, detail="target_id does not exist")

    edge_id = db.upsert_edge(
        source_id=body.source_id,
        target_id=body.target_id,
        relation=body.relation,
        relation_id=body.relation_id,
    )
    return {
        "id": edge_id,
        "source_id": body.source_id,
        "target_id": body.target_id,
        "relation": body.relation,
        "relation_id": body.relation_id,
    }


@router.delete("/api/v1/edges/{edge_id}", status_code=204)
def delete_edge(edge_id: str) -> None:
    """Delete an edge by UUID; 404 if unknown."""
    db = get_db()
    with db._lock, db.conn:
        row = db.conn.execute("SELECT id FROM edges WHERE id = ?", (edge_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Edge not found")
        db.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))


# ── Templates ──────────────────────────────────────────────────────────────────


@router.get("/api/v1/templates")
def list_templates() -> dict[str, list[str]]:
    """Available node templates by name."""
    return {"templates": list(TEMPLATES)}
