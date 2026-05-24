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


def test_create_node_missing_title_returns_422(test_client):
    """POST /api/v1/nodes without a 'path' field must return 422 (FastAPI validation)."""
    # 'path' is required in the NodeCreate model — omitting it triggers FastAPI validation.
    resp = test_client.post(
        "/api/v1/nodes",
        json={"title": "No Path Node"},
    )
    assert resp.status_code == 422, (
        f"Expected 422 (Unprocessable Entity) when 'path' is missing, got {resp.status_code}.\n"
        f"Body: {resp.text}\n"
        "FastAPI raises 422 automatically for missing required fields when using Pydantic models."
    )


def test_delete_nonexistent_node(test_client):
    """DELETE /api/v1/nodes/{id} for a node that does not exist must return 404."""
    resp = test_client.delete("/api/v1/nodes/00000000-dead-beef-cafe-000000000001")
    assert resp.status_code == 404, (
        f"Expected 404 when deleting a non-existent node, got {resp.status_code}"
    )
