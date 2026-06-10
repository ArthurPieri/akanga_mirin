"""Application composition root: database + watcher + events + git."""
from __future__ import annotations

import logging
from pathlib import Path

from .db import GraphDatabase
from .eventbus import EventBus
from .gitmgr import GitManager
from .indexer import index_file
from .watcher import VaultWatcher

logger = logging.getLogger(__name__)


class AkangaApp:
    """Wires the vault watcher, database, event bus, and git manager together."""

    def __init__(self, vault_path: str, db_path: str) -> None:
        self.vault_path = Path(vault_path).absolute()
        self.db = GraphDatabase(db_path)
        self.events = EventBus()
        self.watcher = VaultWatcher(self.vault_path, self.events)
        self.git = GitManager(self.vault_path)

        self.events.subscribe("file_changed", self._on_file_changed)
        self.events.subscribe("file_deleted", self._on_file_deleted)

    def start_all(self) -> None:
        """Start the filesystem watcher."""
        self.watcher.start()
        logger.info("AkangaApp started, watching %s", self.vault_path)

    def _on_file_changed(self, path: Path) -> None:
        try:
            node_id = index_file(self.db, self.vault_path, Path(path))
            self.events.publish("node_updated", node_id=node_id)
            self.git.stage_and_commit([str(path)], f"Update node: {Path(path).stem}")
        except Exception:
            logger.exception("Error processing change for %s", path)

    def _on_file_deleted(self, path: Path) -> None:
        logger.info("File deleted: %s", path)
