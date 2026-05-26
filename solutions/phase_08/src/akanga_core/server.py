from fastapi import FastAPI, WebSocket, HTTPException
from .app import AkangaApp
from .graph import build_ego_graph

def create_app(akanga_app: AkangaApp):
    app = FastAPI(title="Akanga Mirin API")

    @app.get("/nodes")
    async def list_nodes(limit: int = 100, offset: int = 0):
        # Assumes db has get_all_nodes
        return akanga_app.db.get_all_nodes(limit, offset)

    @app.get("/nodes/{node_id}")
    async def get_node(node_id: str):
        # Assumes db has get_node
        node = akanga_app.db.get_node(node_id)
        if not node:
            raise HTTPException(status_code=404, detail="Node not found")
        return node

    @app.get("/graph/{node_id}")
    async def get_graph(node_id: str, depth: int = 2):
        try:
            return build_ego_graph(node_id, akanga_app.db, max_depth=depth)
        except ValueError as e:
            raise HTTPException(status_code=404, detail=str(e))

    @app.websocket("/ws")
    async def websocket_endpoint(websocket: WebSocket):
        await websocket.accept()
        
        async def on_update(node_id: str):
            await websocket.send_json({"event": "node_updated", "id": node_id})
        
        akanga_app.events.subscribe("node_updated", on_update)
        try:
            while True:
                await websocket.receive_text()
        except:
            akanga_app.events.unsubscribe("node_updated", on_update)

    return app
