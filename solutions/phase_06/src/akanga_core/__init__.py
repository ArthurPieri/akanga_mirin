"""akanga_core — Phase 6 reference solution (cumulative through Phase 6).

Layers, in dependency order:

- ``models``      — the monotonic ``Node`` and ``Edge`` dataclasses (Phases 0/1A)
- ``parser``      — file ⇄ Node boundary + inline-edge write-back (Phases 0/1A/1B)
- ``sync_queue``  — pending rename-propagation jobs over raw SQL (Phase 1B)
- ``db``          — ``GraphDatabase``: WAL SQLite + FTS5 derived index (Phase 2)
- ``links``       — wikilink extraction and title → UUID resolution (Phase 2)
- ``indexer``     — two-pass vault scan that rebuilds the DB from files (Phase 2)
- ``graph``       — BFS ego-graphs + ASCII rendering (Phase 3)
- ``eventbus``    — thread-safe pub/sub with the async-loop bridge (Phase 4)
- ``watcher``     — debounced watchdog filesystem monitoring (Phase 4)
- ``sync_worker`` — lazy rename propagation across vault files (Phase 4)
- ``server``      — FastAPI REST API over the vault + index (Phase 6)

The Phase 5 Textual TUI lives in the sibling ``akanga_tui`` package.
"""
