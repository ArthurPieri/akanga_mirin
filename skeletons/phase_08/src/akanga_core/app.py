"""Application composition root: database + watcher + events + git.

Phase 8 INTRODUCES this file — there is no earlier-phase app.py to copy.
``AkangaApp`` owns every long-lived component and wires them together:
the REST server, TUI, and MCP server receive an AkangaApp and never
construct their own bus/db/watcher. (See ``solutions/phase_08`` for the
reference implementation — after attempting your own.)

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

# Seconds of vault inactivity before the dirty set becomes one commit.
COMMIT_IDLE_S = 5.0


class AkangaApp:
    """Wires the vault watcher, database, event bus, and git manager together."""

    def __init__(
        self,
        vault_path: str,
        db_path: str,
        commit_idle_s: float = COMMIT_IDLE_S,
    ) -> None:
        """WHAT: Construct every long-lived component and subscribe the handlers.

        WHY: One composition root means one place where lifetimes and wiring
        live. Components built ad hoc by each entry point drift apart (the
        TUI's watcher debounce differs from the server's, two EventBus
        instances never see each other's events, ...).

        HOW:
        1. Store the absolute vault path: Path(vault_path).absolute()
        2. self.db = GraphDatabase(db_path)            (from .db)
        3. self.events = EventBus()                    (from .eventbus)
        4. self.watcher = VaultWatcher(self.vault_path, self.events)  (from .watcher)
        5. self.git = GitManager(self.vault_path)      (from .gitmgr —
           degrades to no-ops when the vault is not a git repo)
        6. Commit-batching state: a threading.Lock, a set of dirty node
           labels (for the commit message), an optional idle deadline
           (monotonic float), a threading.Event to stop the batcher, and
           a slot for the batcher Thread (created in start_all, NOT here —
           restartability).
        7. Subscribe the handlers:
               self.events.subscribe("file_changed", self._on_file_changed)
               self.events.subscribe("file_deleted", self._on_file_deleted)
           file_changed → index_file the path, publish "node_updated", mark
           the batch dirty. file_deleted → db.delete_node, publish
           "node_deleted", mark dirty.
        """
        raise NotImplementedError(
            "Build db/events/watcher/git, init commit-batching state, and "
            "subscribe _on_file_changed/_on_file_deleted to the event bus."
        )

    def start_all(self) -> None:
        """WHAT: Index the vault, then start the watcher and the commit batcher.

        WHY: The initial full scan makes the database reflect the vault as it
        is NOW — the watcher only reports changes from this moment on. The
        scan is idempotent (hash-first skip + UNIQUE edge constraint), so
        restarting the app never duplicates anything.

        HOW:
        1. count = full_scan_and_index(str(self.vault_path), self.db)
           (from .indexer)
        2. self.watcher.start()
        3. Create a FRESH stop Event (restartable after stop_all), then
           start a daemon Thread running the commit-batcher loop: every
           ~0.5 s, flush the dirty set into one git commit if the idle
           deadline (commit_idle_s seconds after the LAST change) expired.
        4. Log "AkangaApp started: {count} node(s) indexed, watching {vault}".
        """
        raise NotImplementedError(
            "full_scan_and_index, watcher.start(), then start the commit-"
            "batcher daemon thread (fresh stop Event each start)."
        )

    def stop_all(self) -> None:
        """WHAT: Shut down in source-first order, flushing one final commit.

        WHY: Stopping consumers before producers loses events; skipping the
        final flush loses every edit made inside the last idle window.

        HOW:
        1. self.watcher.stop()        — the event source goes FIRST.
        2. Set the batcher's stop Event and join the thread (timeout — a
           wedged thread must not hang shutdown; it is a daemon anyway).
        3. Force-flush the dirty set into one last commit (ignore the idle
           deadline — these edits must not be lost).
        4. self.db.close()
        """
        raise NotImplementedError(
            "watcher.stop(), stop+join the batcher thread, force-flush the "
            "final batched commit, db.close()."
        )
