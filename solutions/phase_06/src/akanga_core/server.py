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
import re
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db import GraphDatabase, NodeRecord
from .indexer import full_scan_and_index, index_file
from .parser import content_hash, parse_node_file, write_node_file
from .textutil import slugify

logger = logging.getLogger(__name__)

# Built-in node templates exposed by GET /api/v1/templates.
TEMPLATES = ["note", "active-http", "active-tcp", "active-service", "virtual", "diagram"]

# Relations that are DERIVED from prose and re-created on every index, so the
# API must never mint or delete them as manual edges (a manual `wikilink` edge
# is indistinguishable from a prose-derived one and would resurrect on rescan).
RESERVED_RELATIONS = {"wikilink"}

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


def _node_dict(node: NodeRecord) -> dict[str, Any]:
    """Convert a DB NodeRecord (attribute access, not JSON-serializable) to a dict."""
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


# ── File-first manual edges (N1) ─────────────────────────────────────────────────
# Manual edges are persisted to the SOURCE node's frontmatter `edges:` block and
# then re-indexed — so the DB stays expendable (rm *.db && scan rebuilds them).
# A folded typed edge persists in the file with `target_id: ""` (resolution is a
# DB-only step), so matching an entry cannot rely on target_id alone.


def _fm_edge_matches(
    entry: dict, relation: str, target_id: str, target_title: str
) -> bool:
    """True when a frontmatter `edges:` entry denotes the same logical edge.

    Relations must match (both normalized to ""). Then either the stored
    `target_id` equals the wanted one, OR — because folded prose edges carry
    `target_id: ""` forever — the entry's display title matches the target
    node's title case-insensitively (the same case rule as `resolve_wikilink`).
    An empty `target_title` never matches via the title fallback.
    """
    if str(entry.get("relation") or "") != (relation or ""):
        return False
    entry_tid = str(entry.get("target_id") or "")
    if entry_tid:
        return entry_tid == target_id
    return bool(target_title) and (
        str(entry.get("target") or "").strip().lower() == target_title.strip().lower()
    )


def _append_fm_edge(
    full_path: Path,
    relation: str,
    relation_id: str,
    target_title: str,
    target_id: str,
) -> bool:
    """Append a typed edge to the source file's frontmatter; False if duplicate.

    Underscore keys (`relation_id`/`target_id`) — the `write_back` convention.
    """
    node = parse_node_file(str(full_path))
    edges = list(node.frontmatter.get("edges") or [])
    for entry in edges:
        if isinstance(entry, dict) and _fm_edge_matches(
            entry, relation, target_id, target_title
        ):
            return False  # duplicate (catches folded entries with target_id="")
    edges.append(
        {
            "relation": relation,
            "relation_id": relation_id,
            "target": target_title,
            "target_id": target_id,
        }
    )
    node.frontmatter["edges"] = edges
    write_node_file(str(full_path), node.frontmatter, node.content)
    return True


def _remove_fm_edge(
    full_path: Path, relation: str, target_id: str, target_title: str
) -> bool:
    """Remove the matching frontmatter edge AND de-type its inline shorthand.

    Removing only the `edges:` entry is not enough: `index_file` re-folds the
    body's `[[Target | relation]]` shorthand on the very next index, resurrecting
    the edge. So the originating shorthand is rewritten to a plain `[[Target]]`
    (which legitimately re-derives as an untyped `wikilink` edge — the prose
    reference survives, the typed edge does not). Returns True if an entry died.
    """
    node = parse_node_file(str(full_path))
    edges = list(node.frontmatter.get("edges") or [])
    removed: dict | None = None
    kept: list = []
    for entry in edges:
        if (
            removed is None
            and isinstance(entry, dict)
            and _fm_edge_matches(entry, relation, target_id, target_title)
        ):
            removed = entry
            continue
        kept.append(entry)
    if removed is None:
        return False

    node.frontmatter["edges"] = kept
    content = node.content
    entry_target = str(removed.get("target") or "")
    entry_relation = str(removed.get("relation") or "")
    if entry_target and entry_relation:
        pattern = re.compile(
            r"\[\[\s*"
            + re.escape(entry_target)
            + r"\s*\|\s*"
            + re.escape(entry_relation)
            + r"\s*\]\]"
        )
        content = pattern.sub(f"[[{entry_target}]]", content)
    write_node_file(str(full_path), node.frontmatter, content)
    return True


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
    raw_path = body.path or f"{slugify(body.title)}.md"
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
    """All raw edge rows touching this node (as source OR target).

    The SQL lives in `GraphDatabase.get_edges_touching`, behind the DB's
    lock — route handlers never reach into `db.conn` with hand-written
    queries (exemplar honesty; adversarial-analysis-v5 #7).
    """
    _existing_node_or_404(node_id)
    return get_db().get_edges_touching(node_id)


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
    """Create a manual typed edge — FILE-FIRST (N1).

    The edge is written into the SOURCE node's frontmatter `edges:` block and
    the file is re-indexed, so the DB row is derived from the file like any
    other edge: `rm *.db && scan` rebuilds it, honouring the Phase 2 doctrine
    that the DB is expendable. Guards: both endpoints validated with 400 (a
    body problem, not a URL problem); self-edges and the reserved `wikilink`
    relation rejected with 400; a duplicate (matched by target_id OR resolved
    title) rejected with 409.
    """
    db = get_db()
    source = db.get_node(body.source_id)
    if source is None:
        raise HTTPException(status_code=400, detail="source_id does not exist")
    target = db.get_node(body.target_id)
    if target is None:
        raise HTTPException(status_code=400, detail="target_id does not exist")
    if body.source_id == body.target_id:
        raise HTTPException(status_code=400, detail="Self-edges are not allowed")
    relation = body.relation or ""
    if relation in RESERVED_RELATIONS:
        raise HTTPException(
            status_code=400, detail=f"Relation {relation!r} is reserved for derived edges"
        )

    full_path = _safe_disk_path(str(source.path))
    if not _append_fm_edge(
        full_path, relation, body.relation_id or "", target.title, body.target_id
    ):
        raise HTTPException(status_code=409, detail="Edge already exists")

    # Re-index the rewritten file: the fold pipeline derives the DB row from the
    # new frontmatter entry. upsert_edge then returns that row's id (INSERT OR
    # IGNORE → the existing id) — so the 201 body carries a usable, real id.
    index_file(str(full_path), get_db(), str(_vault_root()))
    edge_id = db.upsert_edge(
        source_id=body.source_id,
        target_id=body.target_id,
        relation=relation,
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
    """Delete a manual edge — FILE-FIRST (N1); 404 when the edge is unknown.

    The frontmatter `edges:` entry is removed (matched by target_id OR resolved
    title, since folded entries persist with `target_id: ""`) AND its originating
    `[[Target | relation]]` shorthand is de-typed to `[[Target]]`, so re-indexing
    cannot re-fold it; the file is then re-indexed and the row dropped. A
    prose-derived `wikilink` edge has no frontmatter entry — it returns 204 but
    resurrects on rescan (edit the prose to remove it).
    """
    db = get_db()
    edge = db.get_edge(edge_id)
    if edge is None:
        raise HTTPException(status_code=404, detail="Edge not found")

    relation = edge.get("relation") or ""
    if relation not in RESERVED_RELATIONS:
        source = db.get_node(edge["source_id"])
        if source is not None:
            target = db.get_node(edge["target_id"]) if edge.get("target_id") else None
            full_path = _safe_disk_path(str(source.path))
            if _remove_fm_edge(
                full_path,
                relation,
                edge.get("target_id") or "",
                target.title if target else "",
            ):
                index_file(str(full_path), get_db(), str(_vault_root()))
    db.delete_edge(edge_id)  # ignore return: reindex may have already removed it


# ── Templates ──────────────────────────────────────────────────────────────────


@router.get("/api/v1/templates")
def list_templates() -> dict[str, list[str]]:
    """The built-in node template names (static in Phase 6)."""
    return {"templates": TEMPLATES}
