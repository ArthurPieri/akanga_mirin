"""FastAPI REST server for the Akanga knowledge graph."""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, FastAPI
from pydantic import BaseModel

# ── APIRouter — register handlers on this router, then include it in create_app()
router = APIRouter()

# ── Pydantic request/response models ───────────────────────────────────────────
# (Provided — learner should understand these but not need to write them)


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
# Learner must implement these — or use app.state / dependency injection

_app_state: dict[str, Any] = {}


def get_db():
    """WHAT: Return the shared GraphDatabase instance, raising if the app
    has not been initialized yet.

    WHY: Every route handler needs the DB, but FastAPI route functions are
    plain functions — they cannot see create_app()'s locals. The lifespan
    stores the open GraphDatabase in `_app_state`; this accessor is the one
    sanctioned way for handlers to reach it. Failing LOUDLY when the app was
    never initialized beats a confusing KeyError deep inside a handler.

    HOW:
    1. If "db" is not a key in `_app_state`, raise
       `RuntimeError("App not initialized. Call create_app() first.")`.
    2. Otherwise return `_app_state["db"]`.
    """
    raise NotImplementedError(
        "If 'db' not in _app_state: raise RuntimeError('App not initialized...'). "
        "Otherwise return _app_state['db']."
    )


# ── App factory ────────────────────────────────────────────────────────────────


def create_app(
    vault: str | None = None,
    db_path: str | None = None,
) -> FastAPI:
    """WHAT: Create and configure the FastAPI application.

    WHAT: Wire up lifespan (open DB, start watcher), register all routes,
    and return the configured FastAPI instance.

    WHY: The factory pattern lets tests and the CLI create the app with
    different vault/db paths without global state leaking between runs.

    HOW:
    1. Read vault and db_path from args or environment (AKANGA_VAULT, AKANGA_DB).
    2. Define a lifespan context manager that:
       a. Opens GraphDatabase(db_path)
       b. Stores it in _app_state["db"] and _app_state["vault"]
       c. Indexes the vault BEFORE the first request:
              from .indexer import full_scan_and_index
              count = full_scan_and_index(vault, db)
          and log "serving {count} indexed nodes from {vault}". The API
          serves the INDEX — without this scan, a server pointed at an
          existing vault answers GET /nodes with [] until something else
          happens to index the same DB file. The scan is hash-first and
          idempotent (Phase 2), so restarts are cheap.
       d. Yields (server runs here)
       e. Closes the DB on shutdown
    3. Create FastAPI(lifespan=lifespan)
    4. Add CORS middleware (S2) — restricted to localhost dev origins::

           from fastapi.middleware.cors import CORSMiddleware
           app.add_middleware(
               CORSMiddleware,
               allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
               allow_methods=["*"],
               allow_headers=["*"],
           )

       NEVER use allow_origins=["*"]. A wildcard lets ANY website your
       browser visits issue requests to your personal knowledge graph —
       the API is unauthenticated, so the origin allowlist is the only
       thing standing between a malicious page and your vault. List the
       exact localhost origins of your own front-end and nothing else.
    5. app.include_router(router)  — wire all @router.* endpoints into the app.
       Without this, zero routes are registered and every request gets 404.
    6. Return app
    """
    raise NotImplementedError(
        "Create FastAPI app with lifespan that opens GraphDatabase and stores it "
        "in _app_state. Add CORSMiddleware with allow_origins="
        "['http://localhost:5173', 'http://127.0.0.1:5173'] — NEVER '*'. "
        "Register all routes (include_router) and return the app."
    )


# ── Routes ─────────────────────────────────────────────────────────────────────
# These are defined as standalone functions for clarity.
# In your implementation, nest them inside create_app() or use an APIRouter.


@router.post("/api/v1/nodes", status_code=201)
def create_node(body: CreateNodeRequest):
    """WHAT: Create a new node — write a .md file to the vault, index it in the DB.

    WHY: Nodes are the unit of knowledge in Akanga. The API lets TUI clients
    and external tools add knowledge without knowing the vault file layout.

    HOW:
    1. SEC-02 — path traversal protection:
       vault_root = Path(_app_state["vault"]).resolve()
       If body.path is given: full_path = vault_root.joinpath(body.path).resolve()
       Assert full_path.is_relative_to(vault_root) — raise HTTP 400 if not.
    2. If body.path is empty: auto-generate filename from title.
       slug = body.title.lower().replace(" ", "_")
       full_path = vault_root / f"{slug}.md"
       ALSO validate the auto-generated slug path (SEC-02):
           resolved_slug = (vault_root / f"{slug}.md").resolve()
           if not resolved_slug.is_relative_to(vault_root):
               raise HTTPException(status_code=400, detail="Title produces invalid path")
    3. If the file already exists: raise HTTP 409 Conflict.
    4. Build frontmatter dict: {"title": body.title, "type": body.type, "tags": body.tags}
    5. write_node_file(str(full_path), frontmatter, body.content)
    6. node = parse_node_file(str(full_path))
    7. Persist UUID: re-build the frontmatter dict from node attributes and add id:
           fm = {"title": node.title, "type": node.type, "tags": node.tags, "id": str(node.id)}
           write_node_file(str(full_path), fm, body.content)
       (prevents UUID churn on re-parse)
    8. db.upsert_node(node)
    9. Return HTTP 201 with node dict from db.get_node(str(node.id)).

       NOTE (applies to EVERY route in this file — referenced below as
       "the create_node record-object note"): the DB read methods
       (get_node, list_nodes, search_fts, get_neighbors, get_backlinks)
       return a small record object — attribute access like node.title,
       NOT a dict (the reference solution names it NodeRecord). It is not
       JSON-serializable directly, and it has NO .content or .frontmatter
       fields (the DB stores metadata only). Build response dicts
       explicitly:
           created = db.get_node(str(node.id))
           return JSONResponse(status_code=201, content={
               "id": created.id, "title": created.title, "type": created.type,
               "tags": created.tags, "path": str(created.path)})
    """
    raise NotImplementedError(
        "Validate path (SEC-02), auto-slug if empty, write_node_file, parse_node_file, "
        "persist UUID, upsert_node, return 201 with node dict."
    )


@router.get("/api/v1/nodes")
def list_nodes(
    query: str = "",
    type: str = "",
    tag: str = "",
    limit: int = 100,
    offset: int = 0,
):
    """WHAT: List nodes with optional FTS search, type filter, tag filter, and pagination.

    WHY: Clients need to discover nodes without knowing their UUIDs.
    FTS5 full-text search enables semantic retrieval; filters narrow results.

    HOW:
    1. db = get_db()
    2. If query or type or tag is non-empty:
       nodes = db.search_fts(query, limit=limit)
       (filter further by type/tag in Python if your DB does not support those params)
    3. Else: nodes = db.list_nodes(limit=limit, offset=offset)
    4. Build explicit dicts before returning (record objects, not dicts —
       see the create_node record-object note):
           return [{"id": n.id, "title": n.title, "type": n.type,
                    "tags": n.tags, "path": str(n.path)} for n in nodes]
    """
    raise NotImplementedError(
        "Branch on query/type/tag: call db.search_fts(query, limit=limit) or "
        "db.list_nodes(limit=limit, offset=offset). "
        "Return JSONResponse with list of node dicts."
    )


@router.get("/api/v1/nodes/{node_id}")
def get_node(node_id: str):
    """WHAT: Retrieve a single node by its UUID.

    WHY: Clients resolve a known UUID to full node details (title, type, tags, path).

    HOW:
    1. node = get_db().get_node(node_id)
    2. If node is None: raise HTTPException(status_code=404, detail="Node not found")
    3. Build the dict explicitly before returning (record object, not dict
       — see the create_node record-object note):
           return {"id": node.id, "title": node.title, "type": node.type,
                   "tags": node.tags, "path": str(node.path)}
    """
    raise NotImplementedError(
        "Call db.get_node(node_id). Raise 404 if None. Return JSONResponse."
    )


@router.put("/api/v1/nodes/{node_id}")
def update_node(node_id: str, body: UpdateNodeRequest):
    """WHAT: Update a node's title, content, or tags in both the file and DB.

    WHY: Knowledge evolves. The API lets clients edit nodes without touching
    the vault filesystem directly.

    HOW:
    1. existing = get_db().get_node(node_id)  — raise 404 if None.
       (Record object: existing.path, not existing["path"] — see the
       create_node record-object note.)
    2. path = str(existing.path)
    3. SEC-02: Before writing, verify the node's stored path is still within the vault:
       vault_root = Path(_app_state["vault"]).resolve()
       if not Path(path).resolve().is_relative_to(vault_root): raise HTTPException(400)
    4. current = parse_node_file(path)  — read current frontmatter + content from disk.
       (existing from db.get_node has no .content field — the DB does not store body content.
       You MUST read from disk to preserve the body when the client did not send new content.)
    5. Build updated frontmatter dict from the DB record and request body
       (the record has no .frontmatter field — build the dict explicitly):
           fm = {
               "id": str(existing.id),
               "title": body.title if body.title is not None else existing.title,
               "type": existing.type,  # type is not updatable via this endpoint
               "tags": body.tags if body.tags is not None else existing.tags,
           }
       Always keep fm["id"] = str(existing.id)  (don't lose the UUID)
    6. new_content = body.content if body.content is not None else current.content
       (current came from parse_node_file above, which DOES expose .content)
    7. write_node_file(path, fm, new_content)
    8. node = parse_node_file(path)
    9. get_db().upsert_node(node)
    10. Return JSONResponse with the updated node dict, built explicitly
        from get_db().get_node(node_id) (see the create_node record-object
        note).
    """
    raise NotImplementedError(
        "get_node → parse_node_file → update fm fields → write_node_file → "
        "parse again → upsert_node → return updated dict."
    )


@router.delete("/api/v1/nodes/{node_id}", status_code=204)
def delete_node(node_id: str):
    """WHAT: Delete a node's file from the vault and remove it from the DB.

    WHY: Users need to remove outdated knowledge without leaving orphan DB rows.

    HOW:
    1. existing = get_db().get_node(node_id)  — raise 404 if None.
       (Record object: existing.path, not existing["path"] — see the
       create_node record-object note.)
    2. path = str(existing.path)
    3. SEC-02: Before removing, verify path:
       vault_root = Path(_app_state["vault"]).resolve()
       if not Path(path).resolve().is_relative_to(vault_root): raise HTTPException(400)
    4. If os.path.exists(path): os.remove(path)
    5. get_db().delete_node(node_id)
       Note: no separate edge-cleanup step — your Phase 2 delete_node already
       removes ALL touching edges (outgoing via ON DELETE CASCADE, incoming
       via its explicit target_id cleanup). Edge SQL stays in db.py; route
       handlers never reach into db.conn with hand-written queries.
    6. Return HTTP 204 No Content (no body)
    """
    raise NotImplementedError(
        "Raise 404 if missing. os.remove file, delete_node from DB "
        "(it cleans up touching edges itself). Return 204."
    )


@router.get("/api/v1/nodes/{node_id}/edges")
def get_node_edges(node_id: str):
    """WHAT: Return all edges where the node is source or target.

    WHY: Clients need the raw edge list (with relation types and IDs) to
    render the graph or compute statistics.

    HOW:
    1. existing = get_db().get_node(node_id)  — raise 404 if None
    2. edges = get_db().get_edges_touching(node_id)
       Note: GraphDatabase does not have a get_edges_touching method by
       default. Add one to your db.py as part of this phase's deliverable —
       the query belongs behind the DB's lock, never hand-written in a
       route handler:
           def get_edges_touching(self, node_id: str) -> list[dict]:
               with self._lock:
                   rows = self.conn.execute(
                       "SELECT * FROM edges WHERE source_id = ? OR target_id = ?",
                       (node_id, node_id)
                   ).fetchall()
               return [dict(row) for row in rows]
    3. Return JSONResponse(content=edges)
    """
    raise NotImplementedError(
        "Raise 404 if node missing. Call db.get_edges_touching(node_id). "
        "Return JSONResponse."
    )


@router.get("/api/v1/nodes/{node_id}/neighbors")
def get_node_neighbors(node_id: str):
    """WHAT: Return the immediate neighbor nodes reachable via outgoing edges.

    WHY: The TUI ego-graph view needs neighbor nodes to render one hop
    around the selected node.

    HOW:
    1. existing = get_db().get_node(node_id)  — raise 404 if None
    2. neighbors = get_db().get_neighbors(node_id)
       (Record objects, not dicts — see the create_node record-object
       note.) Build explicit dicts:
           return [{"id": n.id, "title": n.title, "type": n.type,
                    "tags": n.tags, "path": str(n.path)} for n in neighbors]
    """
    raise NotImplementedError(
        "Raise 404 if node missing. Call db.get_neighbors(node_id). "
        "Return JSONResponse."
    )


@router.get("/api/v1/nodes/{node_id}/backlinks")
def get_node_backlinks(node_id: str):
    """WHAT: Return nodes that link TO this node (incoming edges / backlinks).

    WHY: Backlinks reveal which notes reference the current node — essential
    for bidirectional navigation in a knowledge graph (like Obsidian backlinks).

    HOW:
    1. existing = get_db().get_node(node_id)  — raise 404 if None
    2. backlinks = get_db().get_backlinks(node_id)
       (Record objects, not dicts — see the create_node record-object
       note.) Build explicit dicts:
           return [{"id": n.id, "title": n.title, "type": n.type,
                    "tags": n.tags, "path": str(n.path)} for n in backlinks]
    """
    raise NotImplementedError(
        "Raise 404 if node missing. Call db.get_backlinks(node_id). "
        "Return JSONResponse."
    )


@router.post("/api/v1/edges", status_code=201)
def create_edge(body: CreateEdgeRequest):
    """WHAT: Create a manual directed edge — FILE-FIRST.

    WHY: A naive handler that only calls db.upsert_edge writes the edge to the
    DB and nowhere else. Phase 2's doctrine is that the DB is EXPENDABLE: the
    next time the source file is re-indexed (delete-then-rederive) the manual
    edge vanishes, and `rm *.db && scan` loses it outright. The fix is to write
    the edge into the SOURCE node's frontmatter `edges:` block (the source of
    truth, Phase 1A) and then re-index — so the row is DERIVED from the file
    like every other edge and survives a rebuild.

    HOW:
    1. source = get_db().get_node(body.source_id) — raise HTTP 400 if None
    2. target = get_db().get_node(body.target_id) — raise HTTP 400 if None
    3. Reject 400 if body.source_id == body.target_id (self-edge), and reject
       400 if (body.relation or "") is a RESERVED_RELATION ({"wikilink"}) — a
       manual wikilink edge is indistinguishable from a prose-derived one.
    4. full_path = _safe_disk_path(str(source.path)) (SEC-02).
    5. Append a frontmatter `edges:` entry — UNDERSCORE keys, the write_back
       convention: {"relation", "relation_id", "target": target.title,
       "target_id": body.target_id}. Refuse with 409 if a matching entry
       already exists. NOTE: a typed inline edge folds to an entry with
       target_id="" — so duplicate detection must match by target_id OR by the
       target node's title (case-insensitive, like resolve_wikilink).
    6. index_file(str(full_path), get_db(), str(_vault_root())) — the fold
       pipeline derives the DB row from the new entry.
    7. edge_id = get_db().upsert_edge(...) returns that row's id (INSERT OR
       IGNORE → the existing id). Return 201 with the edge dict.
    """
    raise NotImplementedError(
        "File-first: validate (400 self-edge / reserved wikilink / missing), "
        "append a frontmatter edges entry (409 on duplicate, matched by "
        "target_id OR title), index_file the source, upsert_edge for the id, 201."
    )


@router.get("/api/v1/templates")
def list_templates():
    """WHAT: Return available node templates by name.

    HOW:
    1. Return a list of template name strings.
       The templates are: "note", "active-http", "active-tcp", "active-service",
       "virtual", "diagram".
    2. Return as JSON: {"templates": ["note", "active-http", ...]}
    """
    raise NotImplementedError(
        "Return list of template names: note, active-http, active-tcp, "
        "active-service, virtual, diagram."
    )


@router.delete("/api/v1/edges/{edge_id}", status_code=204)
def delete_edge(edge_id: str):
    """WHAT: Delete a manual edge by its UUID — FILE-FIRST; 404 if unknown.

    WHY: Deleting only the DB row is not a real delete: the frontmatter entry
    (or, for a typed inline edge, the `[[Target | relation]]` prose) re-folds
    the edge back on the next index. A real delete removes the entry AND
    de-types the originating shorthand, so re-indexing cannot resurrect it.

    HOW:
    1. edge = get_db().get_edge(edge_id) — 404 if None. (Add get_edge to your
       db.py: a sanctioned read returning the row as a dict.)
    2. If edge["relation"] is NOT a RESERVED_RELATION and the source node
       exists: full_path = _safe_disk_path(str(source.path)); remove the
       matching frontmatter `edges:` entry (by target_id OR target title) AND
       rewrite the body's `[[Target | relation]]` -> `[[Target]]`; then
       index_file(...) the source.
    3. get_db().delete_edge(edge_id) (ignore the return — the reindex may have
       already dropped the row). Return 204. A prose-derived `wikilink` edge
       has no frontmatter entry: 204, but it resurrects on rescan (edit the
       prose to remove it).

       Add delete_edge to your db.py — it owns the SQL and returns whether a
       row died:
           def delete_edge(self, edge_id: str) -> bool:
               with self._lock, self.conn:
                   cursor = self.conn.execute(
                       "DELETE FROM edges WHERE id = ?", (edge_id,)
                   )
               return cursor.rowcount > 0
    """
    raise NotImplementedError(
        "File-first: get_edge → 404 if None; remove the frontmatter entry and "
        "de-type the inline shorthand, index_file the source, delete_edge, 204."
    )
