"""Phase 06 test suite — REST API (FastAPI).

Tests the learner's FastAPI server.  The server must export a ``create_app``
factory (see conftest for resolution order).

All tests are synchronous and use Starlette's ``TestClient``, which is the
idiomatic approach for FastAPI testing and does not require an event loop.

Node-create payload schema expected by the server::

    {
        "path": "some-node.md",   # relative path within vault (required)
        "title": "...",           # optional (defaults to path)
        "type":  "note",          # optional
        "tags":  [],              # optional
        "content": "..."          # optional
    }

Edge-create payload::

    {
        "source_id": "<uuid>",
        "target_id": "<uuid>",
        "relation":  "links_to"   # optional
    }
"""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_node(client, *, title: str, node_type: str = "note", content: str = "") -> dict:
    """POST a new node and assert 201.  Returns the response JSON body."""
    slug = title.lower().replace(" ", "-")
    resp = client.post(
        "/api/v1/nodes",
        json={
            "path": f"{slug}.md",
            "title": title,
            "type": node_type,
            "content": content,
        },
    )
    assert resp.status_code == 201, (
        f"Expected 201 when creating node {title!r}, got {resp.status_code}.\n"
        f"Response body: {resp.text}"
    )
    data = resp.json()
    assert "id" in data, (
        f"Create response must contain an 'id' field.  Got: {data!r}"
    )
    return data


def _node_id(node_data: dict) -> str:
    return node_data["id"]


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------


def test_list_nodes_empty(test_client):
    """GET /api/v1/nodes on a fresh vault must return 200 and an empty list."""
    resp = test_client.get("/api/v1/nodes")
    assert resp.status_code == 200, (
        f"Expected 200 from GET /api/v1/nodes, got {resp.status_code}"
    )
    body = resp.json()
    # Accept both {"nodes": []} and [] as valid empty responses.
    nodes = body.get("nodes", body) if isinstance(body, dict) else body
    assert isinstance(nodes, list), f"Expected a list of nodes, got {type(nodes)}: {body!r}"
    assert len(nodes) == 0, f"Expected 0 nodes on fresh vault, got {len(nodes)}: {nodes}"


def test_create_node(test_client):
    """POST /api/v1/nodes must return 201 and a body with an 'id' field."""
    data = _create_node(test_client, title="My First Node")
    assert "id" in data, f"Response missing 'id': {data!r}"
    # Basic UUID format check
    import uuid as _uuid
    try:
        _uuid.UUID(data["id"])
    except ValueError:
        pytest.fail(f"'id' in response is not a valid UUID: {data['id']!r}")


def test_get_node_by_id(test_client):
    """Create a node, then GET it by id — must return 200 with matching title."""
    created = _create_node(test_client, title="Fetchable Node")
    node_id = _node_id(created)

    resp = test_client.get(f"/api/v1/nodes/{node_id}")
    assert resp.status_code == 200, (
        f"Expected 200 fetching node {node_id!r}, got {resp.status_code}"
    )
    data = resp.json()
    assert data.get("title") == "Fetchable Node", (
        f"Title mismatch: expected 'Fetchable Node', got {data.get('title')!r}"
    )


def test_get_node_not_found(test_client):
    """GET /api/v1/nodes/{id} with a non-existent id must return 404."""
    resp = test_client.get("/api/v1/nodes/00000000-dead-beef-cafe-000000000000")
    assert resp.status_code == 404, (
        f"Expected 404 for non-existent node, got {resp.status_code}"
    )


def test_update_node(test_client):
    """Create a node, PUT a new title, then GET — must return the updated title."""
    created = _create_node(test_client, title="Original Title")
    node_id = _node_id(created)

    resp = test_client.put(
        f"/api/v1/nodes/{node_id}",
        json={"title": "Updated Title"},
    )
    assert resp.status_code in (200, 204), (
        f"Expected 200 or 204 from PUT, got {resp.status_code}.\n"
        f"Body: {resp.text}"
    )

    fetch = test_client.get(f"/api/v1/nodes/{node_id}")
    assert fetch.status_code == 200
    data = fetch.json()
    assert data.get("title") == "Updated Title", (
        f"After PUT, expected title 'Updated Title', got {data.get('title')!r}"
    )


def test_delete_node(test_client):
    """Create a node, DELETE it, then GET — must return 404."""
    created = _create_node(test_client, title="Doomed Node")
    node_id = _node_id(created)

    del_resp = test_client.delete(f"/api/v1/nodes/{node_id}")
    assert del_resp.status_code in (200, 204), (
        f"Expected 200 or 204 from DELETE, got {del_resp.status_code}"
    )

    fetch = test_client.get(f"/api/v1/nodes/{node_id}")
    assert fetch.status_code == 404, (
        f"After DELETE, expected 404, got {fetch.status_code}"
    )


def test_list_nodes_search(test_client):
    """Create two nodes with distinct titles; search must return only the matching one."""
    _create_node(test_client, title="Unique Pineapple Note")
    _create_node(test_client, title="Completely Different Thing")

    resp = test_client.get("/api/v1/nodes", params={"query": "Pineapple"})
    assert resp.status_code == 200

    body = resp.json()
    nodes = body.get("nodes", body) if isinstance(body, dict) else body
    assert isinstance(nodes, list)

    titles = [n.get("title", "") for n in nodes]
    assert any("Pineapple" in t for t in titles), (
        f"Search for 'Pineapple' returned no matching node.\n"
        f"Titles in response: {titles!r}\n"
        "Implement full-text search with FTS5 or a LIKE fallback."
    )
    assert all("Pineapple" in t or "pineapple" in t.lower() for t in titles), (
        f"Search for 'Pineapple' returned unrelated nodes: {titles!r}\n"
        "Filter results to only include matches."
    )


def test_list_nodes_pagination(test_client):
    """Create 5 nodes; GET with limit=2&offset=2 must return exactly 2 results."""
    for i in range(5):
        _create_node(test_client, title=f"Pagination Node {i}")

    resp = test_client.get("/api/v1/nodes", params={"limit": 2, "offset": 2})
    assert resp.status_code == 200

    body = resp.json()
    nodes = body.get("nodes", body) if isinstance(body, dict) else body
    assert isinstance(nodes, list)
    assert len(nodes) == 2, (
        f"Expected exactly 2 nodes with limit=2&offset=2, got {len(nodes)}.\n"
        "Implement LIMIT/OFFSET in your list_nodes handler."
    )


def test_create_and_get_edge(test_client):
    """Create two nodes, create an edge, then GET edges for source — edge must appear."""
    node_a = _create_node(test_client, title="Edge Source Node")
    node_b = _create_node(test_client, title="Edge Target Node")

    edge_resp = test_client.post(
        "/api/v1/edges",
        json={
            "source_id": _node_id(node_a),
            "target_id": _node_id(node_b),
            "relation": "links_to",
        },
    )
    assert edge_resp.status_code == 201, (
        f"Expected 201 from POST /api/v1/edges, got {edge_resp.status_code}.\n"
        f"Body: {edge_resp.text}"
    )
    edge_data = edge_resp.json()
    assert "id" in edge_data, f"Edge response missing 'id': {edge_data!r}"

    edges_resp = test_client.get(f"/api/v1/nodes/{_node_id(node_a)}/edges")
    assert edges_resp.status_code == 200

    edges = edges_resp.json()
    edges = edges.get("edges", edges) if isinstance(edges, dict) else edges
    assert isinstance(edges, list)

    target_ids = [e.get("target_id") for e in edges]
    assert _node_id(node_b) in target_ids, (
        f"Edge to {_node_id(node_b)!r} not found in edges response: {edges!r}"
    )


def test_get_neighbors(test_client):
    """Create edge A→B; GET neighbors of A — B must be in the result."""
    node_a = _create_node(test_client, title="Neighbor Source")
    node_b = _create_node(test_client, title="Neighbor Target")

    test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "links_to"},
    )

    resp = test_client.get(f"/api/v1/nodes/{_node_id(node_a)}/neighbors")
    assert resp.status_code == 200

    body = resp.json()
    neighbors = body.get("neighbors", body) if isinstance(body, dict) else body
    assert isinstance(neighbors, list)

    neighbor_ids = [n.get("id") for n in neighbors]
    assert _node_id(node_b) in neighbor_ids, (
        f"Node B ({_node_id(node_b)!r}) not in neighbors of A.\n"
        f"neighbors response: {neighbors!r}"
    )


def test_get_backlinks(test_client):
    """Create edge A→B; GET backlinks of B — A must be in the result."""
    node_a = _create_node(test_client, title="Backlink Source")
    node_b = _create_node(test_client, title="Backlink Target")

    test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "links_to"},
    )

    resp = test_client.get(f"/api/v1/nodes/{_node_id(node_b)}/backlinks")
    assert resp.status_code == 200

    body = resp.json()
    backlinks = body.get("backlinks", body) if isinstance(body, dict) else body
    assert isinstance(backlinks, list)

    backlink_ids = [n.get("id") for n in backlinks]
    assert _node_id(node_a) in backlink_ids, (
        f"Node A ({_node_id(node_a)!r}) not in backlinks of B.\n"
        f"backlinks response: {backlinks!r}"
    )


def test_list_templates(test_client):
    """GET /api/v1/templates must return 200 and a non-empty list of template names."""
    resp = test_client.get("/api/v1/templates")
    assert resp.status_code == 200, (
        f"Expected 200 from GET /api/v1/templates, got {resp.status_code}"
    )
    body = resp.json()
    templates = body.get("templates", body) if isinstance(body, dict) else body
    assert isinstance(templates, list), f"Expected list of templates, got: {body!r}"
    assert len(templates) > 0, (
        "GET /api/v1/templates returned an empty list.\n"
        "Implement at least one built-in template (e.g. 'note')."
    )


# ---------------------------------------------------------------------------
# Runtime-entry contract  (adversarial-analysis-v4 finding #2)
# ---------------------------------------------------------------------------


def test_lifespan_indexes_existing_vault(tmp_path):
    """A server started over a vault that ALREADY contains nodes must serve them.

    Every other test in this suite creates nodes through the API, so a server
    that never looks at the vault on startup still passes — that is exactly
    how v4 finding #2 shipped: `make serve` over a 50-node vault returned []
    from /api/v1/nodes unless some OTHER process had indexed the same .db
    first. This test writes the node files BEFORE create_app and asserts the
    lifespan indexes them.
    """
    pytest.importorskip("fastapi", reason="fastapi not installed — skipping server tests")
    pytest.importorskip("httpx", reason="httpx not installed — skipping server tests")

    from starlette.testclient import TestClient

    from tests.phase_06.conftest import _load_create_app, _write_node

    vault = tmp_path / "vault"
    vault.mkdir()
    _write_node(vault, "alpha.md", title="Pre-Existing Alpha")
    _write_node(vault, "beta.md", title="Pre-Existing Beta")

    create_app = _load_create_app()
    app = create_app(vault=str(vault), db_path=str(tmp_path / "server_test.db"))

    # TestClient runs the ASGI lifespan — startup happens entering the block.
    with TestClient(app, raise_server_exceptions=True) as client:
        resp = client.get("/api/v1/nodes")
        assert resp.status_code == 200, (
            f"Expected 200 from GET /api/v1/nodes, got {resp.status_code}"
        )
        body = resp.json()
        nodes = body.get("nodes", body) if isinstance(body, dict) else body
        assert isinstance(nodes, list), f"Expected a list of nodes, got {type(nodes)}: {body!r}"

        titles = {n.get("title") for n in nodes}
        missing = {"Pre-Existing Alpha", "Pre-Existing Beta"} - titles
        assert not missing, (
            f"GET /api/v1/nodes is missing {sorted(missing)!r} — it returned "
            f"titles {sorted(t for t in titles if t)!r}.\n"
            "create_app's lifespan must full_scan_and_index the vault — a "
            "server over an existing vault must not start empty. The scan is "
            "hash-first idempotent, so indexing on every startup is cheap; "
            "log 'serving N indexed nodes' so a misconfigured vault path is "
            "loud instead of silently empty."
        )


# ---------------------------------------------------------------------------
# Error-path tests  (CCR-9 requirement — at least one per phase)
# ---------------------------------------------------------------------------


def test_create_node_path_traversal_blocked(test_client):
    """POST with a path that escapes the vault must be rejected with 400 (SEC-02)."""
    resp = test_client.post(
        "/api/v1/nodes",
        json={
            "path": "../../etc/passwd",
            "title": "Evil Node",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for path traversal attempt '../../etc/passwd', got {resp.status_code}.\n"
        f"Body: {resp.text}\n"
        "Implement SEC-02 path traversal protection:\n"
        "  full_path = vault_root.joinpath(body.path).resolve()\n"
        "  if not full_path.is_relative_to(vault_root):\n"
        "      raise HTTPException(status_code=400, ...)"
    )


def test_create_node_absolute_path_blocked(test_client):
    """POST with an absolute path must be rejected with 400 (SEC-02).

    A '..'-substring check does not catch this case: '/etc/passwd' contains
    no '..' at all, yet Path.joinpath with an absolute path REPLACES the
    vault root entirely. Only resolve() + is_relative_to() defeats it.
    """
    resp = test_client.post(
        "/api/v1/nodes",
        json={
            "path": "/etc/passwd",
            "title": "Absolute Path Node",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for absolute path '/etc/passwd', got {resp.status_code}.\n"
        f"Body: {resp.text}\n"
        "vault_root.joinpath('/etc/passwd') silently DISCARDS the vault root "
        "(pathlib semantics for absolute paths). The doc-banned '..'-in-path "
        "check cannot catch this. Implement SEC-02 properly:\n"
        "  full_path = vault_root.joinpath(body.path).resolve()\n"
        "  if not full_path.is_relative_to(vault_root.resolve()):\n"
        "      raise HTTPException(status_code=400, ...)"
    )


def test_create_node_symlink_escape_blocked(test_client, tmp_vault, tmp_path_factory):
    """POST through a symlink that points outside the vault must return 400 (SEC-02).

    SECURITY.md lists symlink escape as in-scope: a 'link' inside the vault
    pointing at an outside directory makes 'link/x.md' lexically inside the
    vault but physically outside it. Only Path.resolve() (which follows
    symlinks) catches this — string/'..' checks pass it straight through.
    """
    import os

    outside_dir = tmp_path_factory.mktemp("outside-vault")
    link = tmp_vault / "link"
    try:
        os.symlink(outside_dir, link, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("Platform does not support creating symlinks.")

    resp = test_client.post(
        "/api/v1/nodes",
        json={
            "path": "link/x.md",
            "title": "Symlink Escape Node",
        },
    )
    assert resp.status_code == 400, (
        f"Expected 400 for symlink-escape path 'link/x.md', got {resp.status_code}.\n"
        f"Body: {resp.text}\n"
        "'link/x.md' contains no '..' and looks vault-relative, but resolves "
        "outside the vault through the symlink. resolve() follows symlinks:\n"
        "  full_path = vault_root.joinpath(body.path).resolve()\n"
        "  if not full_path.is_relative_to(vault_root.resolve()):\n"
        "      raise HTTPException(status_code=400, ...)"
    )
    escaped_file = outside_dir / "x.md"
    assert not escaped_file.exists(), (
        f"The server WROTE {escaped_file} outside the vault — the symlink "
        "escape succeeded. Validate the resolved path BEFORE writing."
    )


def test_create_node_missing_title_returns_422(test_client):
    """POST /api/v1/nodes without a 'title' field must return 422 (FastAPI validation).

    'title' is required in the CreateNodeRequest model — omitting it triggers
    FastAPI/Pydantic validation and returns HTTP 422 Unprocessable Entity automatically.
    """
    # 'title' is required in CreateNodeRequest — omitting it triggers FastAPI validation.
    resp = test_client.post(
        "/api/v1/nodes",
        json={"type": "note", "content": "No title here"},
    )
    assert resp.status_code == 422, (
        f"Expected 422 (Unprocessable Entity) when 'title' is missing, got {resp.status_code}.\n"
        f"Body: {resp.text}\n"
        "FastAPI raises 422 automatically for missing required fields when using Pydantic models."
    )


def test_delete_nonexistent_node(test_client):
    """DELETE /api/v1/nodes/{id} for a node that does not exist must return 404."""
    resp = test_client.delete("/api/v1/nodes/00000000-dead-beef-cafe-000000000001")
    assert resp.status_code == 404, (
        f"Expected 404 when deleting a non-existent node, got {resp.status_code}"
    )


# ---------------------------------------------------------------------------
# File-first manual edges (N1) — the API must persist edges to the source
# node's frontmatter and stay rebuildable from the files (Phase 2 doctrine).
# ---------------------------------------------------------------------------

def _read_fm(path):
    """Return (frontmatter_dict, body) for a node file written by the server."""
    import yaml

    text = path.read_text(encoding="utf-8")
    assert text.startswith("---"), f"not a frontmatter file: {path}"
    _, fm_block, body = text.split("---", 2)
    return (yaml.safe_load(fm_block) or {}), body


def _edges_of(client, node_id):
    resp = client.get(f"/api/v1/nodes/{node_id}/edges")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    return body.get("edges", body) if isinstance(body, dict) else body


def test_post_edge_writes_frontmatter_entry(test_client, tmp_vault):
    """POST /edges must write a typed entry into the SOURCE node's frontmatter."""
    node_a = _create_node(test_client, title="FM Source")
    node_b = _create_node(test_client, title="FM Target")
    resp = test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "supports"},
    )
    assert resp.status_code == 201, resp.text

    fm, _body = _read_fm(tmp_vault / "fm-source.md")
    entries = fm.get("edges") or []
    assert any(
        e.get("relation") == "supports" and e.get("target_id") == _node_id(node_b)
        for e in entries
    ), f"frontmatter edges must carry the manual edge; got: {entries!r}"


def test_post_self_edge_returns_400(test_client):
    """A self-edge is rejected with 400."""
    node_a = _create_node(test_client, title="Self Edge Node")
    resp = test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_a), "relation": "supports"},
    )
    assert resp.status_code == 400, resp.text


def test_post_reserved_relation_returns_400(test_client):
    """A manual edge using the reserved `wikilink` relation is rejected with 400."""
    node_a = _create_node(test_client, title="Reserved Source")
    node_b = _create_node(test_client, title="Reserved Target")
    resp = test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "wikilink"},
    )
    assert resp.status_code == 400, resp.text


def test_post_duplicate_edge_returns_409(test_client):
    """POSTing the same (source, target, relation) twice returns 409."""
    node_a = _create_node(test_client, title="Dup Source")
    node_b = _create_node(test_client, title="Dup Target")
    payload = {"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "supports"}
    assert test_client.post("/api/v1/edges", json=payload).status_code == 201
    assert test_client.post("/api/v1/edges", json=payload).status_code == 409


def test_reindex_after_post_does_not_duplicate(test_client):
    """A second POST re-indexes the source; the first edge stays a single row."""
    node_a = _create_node(test_client, title="Reindex Source")
    node_b = _create_node(test_client, title="Reindex Target B")
    node_c = _create_node(test_client, title="Reindex Target C")
    test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "supports"},
    )
    # This POST re-derives ALL of A's edges from frontmatter; A->B must not double.
    test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_c), "relation": "supports"},
    )
    edges = _edges_of(test_client, _node_id(node_a))
    ab = [e for e in edges if e.get("target_id") == _node_id(node_b) and e.get("relation") == "supports"]
    assert len(ab) == 1, f"A->B must be exactly one row after reindex; got {ab!r}"


def test_delete_edge_removes_frontmatter_entry(test_client, tmp_vault):
    """DELETE /edges removes the frontmatter entry (not just the DB row)."""
    node_a = _create_node(test_client, title="Del Source")
    node_b = _create_node(test_client, title="Del Target")
    edge = test_client.post(
        "/api/v1/edges",
        json={"source_id": _node_id(node_a), "target_id": _node_id(node_b), "relation": "supports"},
    ).json()

    assert test_client.delete(f"/api/v1/edges/{edge['id']}").status_code == 204
    fm, _body = _read_fm(tmp_vault / "del-source.md")
    entries = fm.get("edges") or []
    assert not any(e.get("relation") == "supports" for e in entries), (
        f"the deleted edge's frontmatter entry must be gone; got {entries!r}"
    )


def test_manual_edge_survives_db_rebuild(tmp_path):
    """The doctrine test: a manual edge survives `rm *.db && rescan`."""
    from starlette.testclient import TestClient

    from tests.phase_06.conftest import _load_create_app

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "rebuild.db"
    create_app = _load_create_app()

    with TestClient(create_app(vault=str(vault), db_path=str(db_path))) as client:
        a = client.post("/api/v1/nodes", json={"path": "a.md", "title": "Rebuild A"}).json()
        b = client.post("/api/v1/nodes", json={"path": "b.md", "title": "Rebuild B"}).json()
        assert client.post(
            "/api/v1/edges",
            json={"source_id": a["id"], "target_id": b["id"], "relation": "supports"},
        ).status_code == 201

    # Nuke the derived index entirely.
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"rebuild.db{suffix}"
        if p.exists():
            p.unlink()

    with TestClient(create_app(vault=str(vault), db_path=str(db_path))) as client:
        edges = _edges_of(client, a["id"])
        ab = [e for e in edges if e.get("target_id") == b["id"] and e.get("relation") == "supports"]
        assert len(ab) == 1, (
            f"manual edge must rebuild from the file exactly once after rm *.db; got {ab!r}"
        )


def test_delete_folded_typed_edge_stays_dead(tmp_path):
    """Deleting a FOLDED typed edge must remove it for good — no resurrection.

    A typed inline `[[Target | relation]]` folds to a frontmatter entry with
    target_id="". DELETE must remove the entry AND de-type the shorthand, so a
    full rebuild cannot re-fold it. A plain wikilink edge legitimately remains.
    """
    import uuid

    from starlette.testclient import TestClient

    from tests.phase_06.conftest import _load_create_app

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "folded.db"
    (vault / "b-target.md").write_text(
        "---\nid: %s\ntitle: Target Note\ntype: note\ntags: []\n---\n\nbody\n" % uuid.uuid4(),
        encoding="utf-8",
    )
    (vault / "a-source.md").write_text(
        "---\nid: %s\ntitle: Source Note\ntype: note\ntags: []\n---\n\n"
        "Links to [[Target Note | supports]] in prose.\n" % uuid.uuid4(),
        encoding="utf-8",
    )
    create_app = _load_create_app()

    with TestClient(create_app(vault=str(vault), db_path=str(db_path))) as client:
        nodes = client.get("/api/v1/nodes").json()
        a_id = next(n["id"] for n in nodes if n["title"] == "Source Note")
        b_id = next(n["id"] for n in nodes if n["title"] == "Target Note")
        edges = _edges_of(client, a_id)
        supports = [e for e in edges if e.get("relation") == "supports"]
        assert len(supports) == 1, f"lifespan must fold the typed inline edge; got {edges!r}"
        assert client.delete(f"/api/v1/edges/{supports[0]['id']}").status_code == 204

    # Rebuild from the files: the de-typed body must NOT re-fold a supports edge.
    for suffix in ("", "-wal", "-shm"):
        p = tmp_path / f"folded.db{suffix}"
        if p.exists():
            p.unlink()
    with TestClient(create_app(vault=str(vault), db_path=str(db_path))) as client:
        edges = _edges_of(client, a_id)
        assert not any(e.get("relation") == "supports" for e in edges), (
            f"a deleted folded edge must not resurrect on rebuild; got {edges!r}"
        )
        # The prose reference survives as a plain wikilink edge — that's expected.
        assert any(
            e.get("relation") == "wikilink" and e.get("target_id") == b_id for e in edges
        ), f"de-typed [[Target Note]] should re-derive an untyped wikilink edge; got {edges!r}"

    fm, body = _read_fm(vault / "a-source.md")
    assert not (fm.get("edges") or []), f"frontmatter edge entry must be gone; got {fm.get('edges')!r}"
    assert "[[Target Note]]" in body and "[[Target Note | supports]]" not in body, (
        f"body must be de-typed to a plain wikilink; got: {body!r}"
    )


def test_post_duplicate_of_folded_edge_returns_409(tmp_path):
    """POSTing an edge that already exists as a FOLDED entry (target_id='') → 409."""
    import uuid

    from starlette.testclient import TestClient

    from tests.phase_06.conftest import _load_create_app

    vault = tmp_path / "vault"
    vault.mkdir()
    (vault / "b-target.md").write_text(
        "---\nid: %s\ntitle: Target Note\ntype: note\ntags: []\n---\n\nbody\n" % uuid.uuid4(),
        encoding="utf-8",
    )
    (vault / "a-source.md").write_text(
        "---\nid: %s\ntitle: Source Note\ntype: note\ntags: []\n---\n\n"
        "Links to [[Target Note | supports]] in prose.\n" % uuid.uuid4(),
        encoding="utf-8",
    )
    create_app = _load_create_app()
    with TestClient(create_app(vault=str(vault), db_path=str(tmp_path / "dup.db"))) as client:
        nodes = client.get("/api/v1/nodes").json()
        a_id = next(n["id"] for n in nodes if n["title"] == "Source Note")
        b_id = next(n["id"] for n in nodes if n["title"] == "Target Note")
        resp = client.post(
            "/api/v1/edges",
            json={"source_id": a_id, "target_id": b_id, "relation": "supports"},
        )
        assert resp.status_code == 409, (
            f"a folded edge (target_id='') must be detected as a duplicate; got {resp.status_code}"
        )
