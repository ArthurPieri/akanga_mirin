"""Phase 6 — Minimal FastAPI knowledge graph API.

Run: uvicorn examples.phase_06_fastapi_basics:app --reload
     curl http://localhost:8000/nodes

Shows FastAPI route definition, Pydantic validation, and proper HTTP status codes.
"""
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uuid

app = FastAPI(title="Akanga Phase 6 Demo")
_store: dict[str, dict] = {}


class CreateNode(BaseModel):
    title: str
    type: str = "note"


@app.get("/nodes")
def list_nodes():
    return {"nodes": list(_store.values())}


@app.post("/nodes", status_code=201)
def create_node(body: CreateNode):
    node_id = str(uuid.uuid4())
    _store[node_id] = {"id": node_id, "title": body.title, "type": body.type}
    return _store[node_id]


@app.get("/nodes/{node_id}")
def get_node(node_id: str):
    if node_id not in _store:
        raise HTTPException(status_code=404, detail="Node not found")
    return _store[node_id]


@app.delete("/nodes/{node_id}", status_code=204)
def delete_node(node_id: str):
    if node_id not in _store:
        raise HTTPException(status_code=404, detail="Node not found")
    del _store[node_id]
