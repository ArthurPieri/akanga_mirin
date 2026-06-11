"""Application composition root: database + watcher + events + git.

``AkangaApp`` owns every long-lived component and wires them together —
the rest of the codebase (server, TUI, MCP) receives an AkangaApp and
never constructs its own bus/db/watcher.

Two design points worth reading twice:

- COMMIT BATCHING. One git commit per save is how a vault history rots:
  a burst of edits becomes dozens of micro-commits and (because GitPython
  never auto-packs) gigabytes of loose objects. Changed paths are instead
  collected into a dirty set and committed as ONE commit after
  ``COMMIT_IDLE_S`` seconds of vault inactivity — every new event pushes
  the deadline back, exactly like the watcher's per-file debounce, one
  level up. The commit message lists the affected nodes.

- DELETIONS ARE REAL EVENTS. ``file_deleted`` removes the node (and its
  edges) from the database and lands in the same batched commit —
  otherwise deleted notes haunt search results and ego-graphs forever.
"""
from __future__ import annotations

import logging
import threading
import time
from pathlib import Path

from .db import GraphDatabase
from .eventbus import EventBus
from .gitmgr import GitManager
from .indexer import index_file, index_vault
from .watcher import VaultWatcher

logger = logging.getLogger(__name__)

# Seconds of vault inactivity before the dirty set becomes one commit.
COMMIT_IDLE_S = 5.0
# At most this many node names are spelled out in a commit message.
_MAX_NAMES_IN_MESSAGE = 10


class AkangaApp:
    """Wires the vault watcher, database, event bus, and git manager together."""

    def __init__(
        self,
        vault_path: str,
        db_path: str,
        commit_idle_s: float = COMMIT_IDLE_S,
    ) -> None:
        self.vault_path = Path(vault_path).absolute()
        self.db = GraphDatabase(db_path)
        self.events = EventBus()
        self.watcher = VaultWatcher(self.vault_path, self.events)
        self.git = GitManager(self.vault_path)  # degrades to no-ops if not a repo
        self.commit_idle_s = commit_idle_s

        # --- commit batching state (see module docstring) ---------------
        self._commit_lock = threading.Lock()
        self._dirty_labels: set[str] = set()      # node names for the message
        self._commit_deadline: float | None = None
        self._commit_stop = threading.Event()
        self._committer: threading.Thread | None = None

        # path -> node id memo, fed by _on_file_changed, so a later
        # deletion can find its node without a table scan.
        self._node_ids: dict[str, str] = {}

        self.events.subscribe("file_changed", self._on_file_changed)
        self.events.subscribe("file_deleted", self._on_file_deleted)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start_all(self) -> None:
        """Index the vault, then start the watcher and the commit batcher.

        The initial full scan makes the database reflect the vault as it
        is NOW — the watcher only reports changes from this moment on.
        The scan is idempotent (``UNIQUE`` edge constraint +
        ``INSERT OR IGNORE``), so restarting the app never duplicates
        anything.
        """
        count = index_vault(self.db, self.vault_path)
        self.watcher.start()
        self._commit_stop = threading.Event()  # fresh event — restartable
        self._committer = threading.Thread(
            target=self._commit_loop, name="akanga-git-batcher", daemon=True
        )
        self._committer.start()
        logger.info(
            "AkangaApp started: %d node(s) indexed, watching %s", count, self.vault_path
        )

    def stop_all(self) -> None:
        """Shut down in source-first order, flushing one final commit.

        Watcher first (it feeds everything), then the batcher thread,
        then a forced flush so edits made in the last idle window are
        committed rather than lost, then the database connection.
        """
        self.watcher.stop()
        self._commit_stop.set()
        if self._committer is not None:
            self._committer.join(timeout=5.0)
            self._committer = None
        self._flush_commit(force=True)
        self.db.close()
        logger.info("AkangaApp stopped")

    # ------------------------------------------------------------------
    # Event handlers (run on the watcher's debounce worker thread)
    # ------------------------------------------------------------------

    def _on_file_changed(self, path: Path, **_: object) -> None:
        """Re-index a changed file, announce it, and mark the batch dirty."""
        try:
            file_path = Path(path)
            node_id = index_file(self.db, self.vault_path, file_path)
            self._node_ids[self._path_key(file_path)] = node_id
            self.events.publish("node_updated", node_id=node_id)
            self._mark_dirty(file_path.stem)
        except Exception:
            logger.exception("Error processing change for %s", path)

    def _on_file_deleted(self, path: Path, **_: object) -> None:
        """Remove the deleted file's node from the graph and batch the commit.

        The watcher already debounced this with a create-cancels-delete
        grace window, so by the time it arrives the file is genuinely
        gone — evict the node (cascading its edges), tell subscribers,
        and let the batched commit record the removal in git.
        """
        try:
            file_path = Path(path)
            node_id = self._node_ids.pop(self._path_key(file_path), None)
            if node_id is None:
                node_id = self._find_node_id(file_path)
            if node_id is not None:
                self.db.delete_node(node_id)
                self.events.publish("node_deleted", node_id=node_id)
            self._mark_dirty(f"{file_path.stem} (deleted)")
        except Exception:
            logger.exception("Error processing deletion for %s", path)

    # ------------------------------------------------------------------
    # Commit batching
    # ------------------------------------------------------------------

    def _mark_dirty(self, label: str) -> None:
        """Add *label* to the pending commit and push the idle deadline back.

        Every change RESETS the deadline — the commit fires only after
        ``commit_idle_s`` of silence, so a 20-file editing burst becomes
        one commit, not twenty.
        """
        with self._commit_lock:
            self._dirty_labels.add(label)
            self._commit_deadline = time.time() + self.commit_idle_s

    def _commit_loop(self) -> None:
        """Poll for an expired idle deadline; one thread, ``Event.wait`` paced.

        Same single-worker pattern as the watcher's debounce loop: the
        poll interval only bounds extra latency on top of the idle
        window, and ``Event.wait`` makes stop_all() take effect at once.
        """
        while not self._commit_stop.wait(timeout=0.5):
            self._flush_commit()

    def _flush_commit(self, force: bool = False) -> None:
        """Turn the dirty set into one git commit if the idle window elapsed.

        State is swapped out under the lock; the (potentially slow) git
        call runs outside it so event handlers are never blocked on git.
        With *force* the deadline is ignored — used by stop_all() so the
        final window's edits are never lost.
        """
        with self._commit_lock:
            if not self._dirty_labels:
                return
            deadline = self._commit_deadline
            if not force and (deadline is None or time.time() < deadline):
                return
            labels = sorted(self._dirty_labels)
            self._dirty_labels.clear()
            self._commit_deadline = None

        shown = ", ".join(labels[:_MAX_NAMES_IN_MESSAGE])
        if len(labels) > _MAX_NAMES_IN_MESSAGE:
            shown += f", +{len(labels) - _MAX_NAMES_IN_MESSAGE} more"
        message = f"auto: update {len(labels)} node(s): {shown}"
        sha = self.git.commit(message)  # None when not a repo / clean tree
        if sha is not None:
            logger.info("Batched commit %s covering %d node(s)", sha[:7], len(labels))

    # ------------------------------------------------------------------
    # Path → node lookup
    # ------------------------------------------------------------------

    def _path_key(self, path: Path) -> str:
        """Canonical dictionary key for a vault file path.

        Watcher payloads are absolute; node rows may store relative paths
        (the taught convention) or absolute ones — anchoring relatives at
        the vault root and resolving both sides makes the two spellings
        compare equal.
        """
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.vault_path / candidate
        return str(candidate.resolve())

    def _find_node_id(self, path: Path) -> str | None:
        """Fallback path lookup: page through nodes comparing canonical paths.

        Only reached for files indexed before this process started (the
        memo dict covers everything else), so the linear scan is rare —
        and it uses the public ``get_all_nodes`` API instead of reaching
        into the database's connection with hand-written SQL.
        """
        wanted = self._path_key(path)
        page_size = 500
        offset = 0
        while True:
            batch = self.db.get_all_nodes(limit=page_size, offset=offset)
            if not batch:
                return None
            for node in batch:
                if node.path and self._path_key(Path(node.path)) == wanted:
                    return node.id
            offset += page_size
