"""Phase 06 — FastAPI REST server for the Akanga knowledge graph.

The API never bypasses the file system: ``POST /api/v1/nodes`` writes a
real `.md` file into the vault and THEN indexes it, exactly like a
hand-written note picked up by the watcher. The DB stays an expendable,
derived index; the files stay the source of truth.

Security posture (all three layers, outermost first):

- Network binding — serve on ``127.0.0.1`` only (the CLI's concern).
- CORS (S2) — explicit localhost dev origins, NEVER ``"*"``: the API is
  unauthenticated, so the origin allowlist is the only thing standing
  between a malicious browser tab and the vault.
- SEC-02 path traversal — every client-supplied or stored path is
  validated with ``Path.resolve()`` + ``is_relative_to()`` BEFORE any
  filesystem write/delete. ``resolve()`` follows symlinks, which is the
  only defence that catches all three escape shapes: ``../`` traversal,
  absolute paths (``joinpath('/etc/passwd')`` silently DISCARDS the vault
  root — pathlib semantics), and a symlink inside the vault pointing out.
  A '``..`` in the string' check catches only the first.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import GraphDatabase
from .indexer import full_scan_and_index
from .parser import content_hash, parse_node_file, write_node_file

logger = logging.getLogger(__name__)

# Built-in node templates exposed by GET /api/v1/templates.
TEMPLATES = ["note", "active-http", "active-tcp", "active-service", "virtual", "diagram"]

# ── APIRouter — handlers register here; create_app() includes the router ──────
router = APIRouter()


# ── Pydantic request models ────────────────────────────────────────────────────


class CreateNodeRequest(BaseModel):
    """Body of ``POST /api/v1/nodes``. Only `title` is required.

    An empty `path` means "derive the filename from the title"; a missing
    `title` is rejected by FastAPI/Pydantic with 422 before the handler runs.
    """

    title: str
    type: str = "note"
    content: str = ""
    tags: list[str] = []
    path: str = ""  # optional vault-relative path, e.g. "ideas/spark.md"


class UpdateNodeRequest(BaseModel):
    """Body of ``PUT /api/v1/nodes/{id}`` — every field optional (patch style)."""

    title: str | None = None
    content: str | None = None
    tags: list[str] | None = None


class CreateEdgeRequest(BaseModel):
    """Body of ``POST /api/v1/edges`` — a manual typed edge between two nodes."""

    source_id: str
    target_id: str
    relation: str | None = None
    relation_id: str | None = None


# ── App state ──────────────────────────────────────────────────────────────────
# Route handlers are plain functions — they cannot see create_app()'s locals.
# The lifespan stores the open DB + vault root here; get_db() is the one
# sanctioned accessor.

_app_state: dict[str, Any] = {}


def get_db() -> GraphDatabase:
    """Return the shared GraphDatabase, failing LOUDLY if never initialized.

    A clear RuntimeError at the accessor beats a confusing KeyError deep
    inside a route handler when the lifespan never ran.
    """
    if "db" not in _app_state:
        raise RuntimeError("App not initialized. Call create_app() first.")
    return _app_state["db"]


def _vault_root() -> Path:
    """The vault root, resolved once per call so symlinked tmp dirs compare equal."""
    return Path(_app_state["vault"]).resolve()


# ── Internal helpers ───────────────────────────────────────────────────────────


def _node_dict(node: Any) -> dict[str, Any]:
    """Convert a DB node (SimpleNamespace — not JSON-serializable) to a dict."""
    return {
        "id": node.id,
        "title": node.title,
        "type": node.type,
        "tags": node.tags,
        "path": str(node.path),
    }


def _safe_disk_path(raw_path: str) -> Path:
    """SEC-02: resolve `raw_path` against the vault and verify containment.

    ``joinpath`` + ``resolve`` + ``is_relative_to`` is the full defence:

    - ``../../etc/passwd``  → resolves above the vault       → 400
    - ``/etc/passwd``       → joinpath DISCARDS the vault    → 400
    - ``link/x.md`` via a symlink out of the vault — resolve() follows
      the symlink to the real location outside                → 400

    Must be called BEFORE any write/delete; the symlink case otherwise
    plants a file outside the vault.
    """
    vault_root = _vault_root()
    full_path = vault_root.joinpath(raw_path).resolve()
    if not full_path.is_relative_to(vault_root):
        raise HTTPException(status_code=400, detail="Path escapes the vault (SEC-02)")
    return full_path


def _existing_node_or_404(node_id: str) -> Any:
    """Fetch a node by UUID or abort with 404 — shared by all /{id} routes."""
    node = get_db().get_node(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


def _index_node_file(full_path: Path) -> Any:
    """Parse a freshly written node file and upsert it into the DB.

    The DB stores the path RELATIVE to the vault root (same convention as
    the Phase 2 indexer) so the index survives the vault being moved.
    """
    node = parse_node_file(str(full_path))
    node.content_hash = content_hash(str(full_path))
    node.path = str(full_path.relative_to(_vault_root()))
    get_db().upsert_node(node)
    return node


# ── App factory ────────────────────────────────────────────────────────────────


def create_app(
    vault: str | None = None,
    db_path: str | None = None,
) -> FastAPI:
    """Create and configure the FastAPI application.

    The factory pattern lets tests and the CLI spin up the app against
    different vault/db paths without global state leaking between runs:
    the DB is opened in the lifespan (TestClient's ``with`` block runs
    it), not at import time.
    """
    import os

    resolved_vault = vault or os.environ.get("AKANGA_VAULT", "./vault")
    resolved_db = db_path or os.environ.get("AKANGA_DB", "./.akanga.db")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Open the DB and index the vault on startup, close on shutdown.

        One ``check_same_thread=False`` connection (GraphDatabase's own
        lock serializes access) shared by every request — opening a
        connection per request would defeat WAL's snapshot semantics.

        The API serves the INDEX, so the index must reflect the vault
        BEFORE the first request: without the startup scan, a server
        pointed at an existing vault answers ``GET /nodes`` with ``[]``
        until some other process happens to index the same DB file. The
        scan is hash-first and idempotent (Phase 2), so an already-indexed
        vault costs one hash per file and zero writes.
        """
        db = GraphDatabase(resolved_db)
        _app_state["db"] = db
        _app_state["vault"] = resolved_vault
        count = full_scan_and_index(resolved_vault, db)
        logger.info("serving %d indexed nodes from %s", count, resolved_vault)
        try:
            yield
        finally:
            db.close()
            _app_state.pop("db", None)
            _app_state.pop("vault", None)

    app = FastAPI(title="Akanga Knowledge Graph API", lifespan=lifespan)

    # S2: explicit localhost dev origins only. NEVER allow_origins=["*"] —
    # the API is unauthenticated, so a wildcard would let ANY website the
    # browser visits read and write the personal knowledge graph.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Without include_router zero routes are registered → every request 404s.
    app.include_router(router)
    return app


# ── Node routes ────────────────────────────────────────────────────────────────


@router.post("/api/v1/nodes", status_code=201)
def create_node(body: CreateNodeRequest) -> dict[str, Any]:
    """Create a node: write the `.md` file into the vault, then index it.

    SEC-02 validation happens FIRST — before any byte touches disk — so a
    traversal/absolute/symlink path can never plant a file outside the
    vault. The UUID is minted here and written into the frontmatter so a
    later re-parse returns the same identity (no UUID churn).
    """
    raw_path = body.path or f"{body.title.lower().replace(' ', '-')}.md"
    full_path = _safe_disk_path(raw_path)

    if full_path.exists():
        raise HTTPException(status_code=409, detail="A node already exists at this path")

    fm = {"id": str(uuid4()), "title": body.title, "type": body.type, "tags": body.tags}
    write_node_file(str(full_path), fm, body.content)
    node = _index_node_file(full_path)
    return _node_dict(get_db().get_node(node.id))


@router.get("/api/v1/nodes")
def list_nodes(
    query: str = "",
    type: str = "",  # noqa: A002 — query-param name fixed by the API contract
    tag: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List nodes — optional FTS5 search (`?query=`), filters, pagination.

    Search goes through ``db.search_fts`` (SEC-06 quoting lives there);
    type/tag filters are applied in Python on the result. Plain listing
    delegates LIMIT/OFFSET to SQLite.
    """
    db = get_db()
    if query:
        nodes = db.search_fts(query, limit=limit)
    else:
        nodes = db.list_nodes(limit=limit, offset=offset)
    if type:
        nodes = [n for n in nodes if n.type == type]
    if tag:
        nodes = [n for n in nodes if tag in n.tags]
    return [_node_dict(n) for n in nodes]


@router.get("/api/v1/search")
def search_nodes(q: str = "", limit: int = 20) -> list[dict[str, Any]]:
    """Dedicated FTS5 search endpoint — same engine as ``GET /nodes?query=``.

    Kept as a stable alias so non-browser clients (the Phase 8 MCP server)
    can search without learning the node-listing parameter set.
    """
    if not q:
        return []
    return [_node_dict(n) for n in get_db().search_fts(q, limit=limit)]


@router.get("/api/v1/nodes/{node_id}")
def get_node(node_id: str) -> dict[str, Any]:
    """Resolve a UUID to full node details; 404 when unknown."""
    return _node_dict(_existing_node_or_404(node_id))


@router.put("/api/v1/nodes/{node_id}")
def update_node(node_id: str, body: UpdateNodeRequest) -> dict[str, Any]:
    """Update title/content/tags — rewrites the file, then re-indexes.

    The DB does not store prose, so the current body is read from disk
    first; otherwise an update that only changes the title would wipe the
    content. The stored path is re-validated (SEC-02) before writing —
    never trust a path just because it sits in the index.
    """
    existing = _existing_node_or_404(node_id)
    full_path = _safe_disk_path(str(existing.path))

    current = parse_node_file(str(full_path))
    fm = dict(current.frontmatter)
    fm["id"] = str(existing.id)  # never lose the UUID across rewrites
    fm["title"] = body.title if body.title is not None else existing.title
    fm["type"] = existing.type  # type is not updatable via this endpoint
    fm["tags"] = body.tags if body.tags is not None else existing.tags
    new_content = body.content if body.content is not None else current.content

    write_node_file(str(full_path), fm, new_content)
    _index_node_file(full_path)
    return _node_dict(get_db().get_node(node_id))


@router.delete("/api/v1/nodes/{node_id}", status_code=204)
def delete_node(node_id: str) -> None:
    """Delete the vault file and the DB row (plus all touching edges).

    File first, then DB: if the unlink fails the index still knows about
    the node, and a re-scan converges. ``GraphDatabase.delete_node``
    already removes outgoing (CASCADE) and incoming edges plus the FTS row.
    """
    existing = _existing_node_or_404(node_id)
    full_path = _safe_disk_path(str(existing.path))
    if full_path.exists():
        full_path.unlink()
    get_db().delete_node(node_id)


# ── Graph routes ───────────────────────────────────────────────────────────────


@router.get("/api/v1/nodes/{node_id}/edges")
def get_node_edges(node_id: str) -> list[dict[str, Any]]:
    """All raw edge rows touching this node (as source OR target)."""
    _existing_node_or_404(node_id)
    db = get_db()
    with db._lock:
        rows = db.conn.execute(
            "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
            (node_id, node_id),
        ).fetchall()
    return [dict(row) for row in rows]


@router.get("/api/v1/nodes/{node_id}/neighbors")
def get_node_neighbors(node_id: str) -> list[dict[str, Any]]:
    """Immediate neighbour nodes reachable via OUTGOING edges."""
    _existing_node_or_404(node_id)
    return [_node_dict(n) for n in get_db().get_neighbors(node_id)]


@router.get("/api/v1/nodes/{node_id}/backlinks")
def get_node_backlinks(node_id: str) -> list[dict[str, Any]]:
    """Nodes that link TO this node (incoming edges, Obsidian-style)."""
    _existing_node_or_404(node_id)
    return [_node_dict(n) for n in get_db().get_backlinks(node_id)]


# ── Edge routes ────────────────────────────────────────────────────────────────


@router.post("/api/v1/edges", status_code=201)
def create_edge(body: CreateEdgeRequest) -> dict[str, Any]:
    """Create a manual typed edge between two EXISTING nodes.

    Both endpoints are validated with 400 (not 404): the missing node is
    a problem with the request body, not with the URL the client hit.
    """
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
    """Delete a single edge row by UUID; 404 when it does not exist."""
    db = get_db()
    with db._lock, db.conn:
        row = db.conn.execute(
            "SELECT id FROM edges WHERE id = ?", (edge_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Edge not found")
        db.conn.execute("DELETE FROM edges WHERE id = ?", (edge_id,))


# ── Templates ──────────────────────────────────────────────────────────────────


@router.get("/api/v1/templates")
def list_templates() -> dict[str, list[str]]:
    """The built-in node template names (static in Phase 6)."""
    return {"templates": TEMPLATES}
