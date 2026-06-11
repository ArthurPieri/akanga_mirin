"""akanga_core — Phase 5 reference solution.

Layers, in dependency order:

- ``models``      — the monotonic ``Node`` and ``Edge`` dataclasses (Phases 0/1A)
- ``parser``      — file ⇄ Node boundary + inline-edge write-back (Phases 0/1A/1B)
- ``sync_queue``  — pending rename-propagation jobs over raw SQL (Phase 1B)
- ``db``          — ``GraphDatabase``: WAL SQLite + FTS5 derived index (Phase 2)
- ``links``       — wikilink extraction and title → UUID resolution (Phase 2)
- ``indexer``     — two-pass vault scan that rebuilds the DB from files (Phase 2)
- ``graph``       — BFS ego-graph construction + ASCII rendering (Phase 3)
- ``eventbus``    — thread-safe pub/sub with an asyncio bridge (Phase 4)
- ``watcher``     — debounced filesystem monitoring via watchdog (Phase 4)
- ``sync_worker`` — drains rename-propagation jobs onto disk (Phase 4)

The Phase 0–2 layers are byte-identical to the Phase 2 reference solution;
Phase 5 adds nothing to them — the TUI (``akanga_tui``) only consumes them.
"""
