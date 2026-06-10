"""FastAPI HTTP layer over the knowledge graph (Phase 6, carried forward).

Node prose is read from disk at request time (BUG-01) — the database serves
metadata only. Run via run_api.py, which binds uvicorn to 127.0.0.1.
"""
from __future__ import annotations

from dataclasses import asdict

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect

from .app import AkangaApp
from .graph import build_ego_graph
from .parser import parse_node_file


def create_app(akanga_app: AkangaApp) -> FastAPI:
    """Build the FastAPI application around an :class:`AkangaApp` instance."""
    app = FastAPI(title="Akanga Mirin API")

    @app.get("/nodes")
    async def list_nodes(limit: int = 100, offset: int = 0) -> list[dict]:
        return [asdict(node) for node in akanga_app.db.get_all_nodes(limit, offset)]

    @app.get("/nodes/{node_id}")
    async def get_node(node_id: str) -> dict:
        node = akanga_app.db.get_node(node_id)
        if node is None:
            raise HTTPException(status_code=404, detail="Node not found")
        payload = asdict(node)
        try:
            # BUG-01: prose lives on disk, not in the database.
            payload["body"] = parse_node_file(node.path).content
        except OSError:
            payload["body"] = ""
        return payload

    @app.get("/graph/{node_id}")
    async def get_graph(node_id: str, depth: int = 2) -> dict:
        try:
            ego = build_ego_graph(node_id, akanga_app.db, max_depth=depth)
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return {
            "root": ego.root.id,
            "nodes": [asdict(node) for node in ego.nodes.values()],
            "edges": [
                {
                    "source": edge.source_id,
                    "target": edge.target_id,
                    "relation": edge.relation,
                }
                for edge in ego.edges
            ],
        }

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        async def on_update(node_id: str) -> None:
            await websocket.send_json({"event": "node_updated", "id": node_id})

        akanga_app.events.subscribe("node_updated", on_update)
        try:
            while True:
                await websocket.receive_text()
        except WebSocketDisconnect:
            pass
        finally:
            akanga_app.events.unsubscribe("node_updated", on_update)

    return app
