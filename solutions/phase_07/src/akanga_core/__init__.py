"""akanga_core — Phase 7 reference solution.

Layers, in dependency order:

- ``models``      — the monotonic ``Node`` and ``Edge`` dataclasses (Phases 0/1A)
- ``parser``      — file ⇄ Node boundary + inline-edge write-back (Phases 0/1A/1B)
- ``sync_queue``  — pending rename-propagation jobs over raw SQL (Phase 1B)
- ``db``          — ``GraphDatabase``: WAL SQLite + FTS5 derived index (Phase 2)
- ``links``       — wikilink extraction and title → UUID resolution (Phase 2)
- ``indexer``     — two-pass vault scan that rebuilds the DB from files (Phase 2)
- ``graph``       — BFS ego-graph + ASCII rendering (Phase 3)
- ``eventbus``    — thread-safe pub/sub with the async bridge + buffer (Phase 4)
- ``watcher``     — watchdog observer with single-worker debounce (Phase 4)
- ``sync_worker`` — drains the rename queue against current disk truth (Phase 4)
- ``server``      — FastAPI REST API with SEC-02 path protection (Phase 6)
- ``gitmgr``      — optional, non-fatal git integration via GitPython (Phase 7)

The Phase 5 Textual TUI lives in the sibling ``akanga_tui`` package.
"""
