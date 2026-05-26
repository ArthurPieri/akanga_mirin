from __future__ import annotations
import logging
from pathlib import Path
from .db import Database
from .eventbus import EventBus
from .watcher import VaultWatcher
from .gitmgr import GitManager
from .parser import parse_node_file

logger = logging.getLogger(__name__)

class AkangaApp:
    def __init__(self, vault_path: str, db_path: str = "akanga.db"):
        self.vault_path = Path(vault_path).absolute()
        self.db = Database(db_path)
        self.events = EventBus()
        self.watcher = VaultWatcher(self.vault_path, self.events)
        self.git = GitManager(self.vault_path)
        
        self.events.subscribe("file_changed", self._on_file_changed)
        self.events.subscribe("file_deleted", self._on_file_deleted)

    def start_all(self):
        self.events.set_loop(None) # Will be set by server or TUI if needed
        self.watcher.start()
        logger.info("AkangaApp started, watching %s", self.vault_path)

    def _on_file_changed(self, path: Path):
        try:
            node = parse_node_file(str(path))
            self.db.upsert_node(node)
            self.events.publish("node_updated", node_id=node.id)
            self.git.stage_and_commit([str(path)], f"Update node: {node.title}")
        except Exception as e:
            logger.error("Error processing change for %s: %s", path, e)

    def _on_file_deleted(self, path: Path):
        # In a real app, you'd map path to ID and delete from DB
        logger.info("File deleted: %s", path)
