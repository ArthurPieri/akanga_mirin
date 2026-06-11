"""akanga_core — Phase 4 reference solution.

Layers, in dependency order:

- ``models``      — the monotonic ``Node`` and ``Edge`` dataclasses (Phases 0/1A)
- ``parser``      — file ⇄ Node boundary + inline-edge write-back (Phases 0/1A/1B)
- ``sync_queue``  — pending rename-propagation jobs over raw SQL (Phase 1B)
- ``db``          — ``GraphDatabase``: WAL SQLite + FTS5 derived index (Phase 2)
- ``links``       — wikilink extraction and title → UUID resolution (Phase 2)
- ``indexer``     — two-pass vault scan that rebuilds the DB from files (Phase 2)
- ``graph``       — BFS ego-graph + ASCII renderer (Phase 3)
- ``eventbus``    — thread-safe pub/sub with the asyncio bridge (Phase 4)
- ``watcher``     — watchdog filesystem monitor with per-path debounce (Phase 4)
- ``sync_worker`` — drains the rename-propagation queue onto disk (Phase 4)
"""
