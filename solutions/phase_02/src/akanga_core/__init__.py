"""akanga_core — Phase 2 reference solution.

Layers, in dependency order:

- ``models``     — the monotonic ``Node`` and ``Edge`` dataclasses (Phases 0/1A)
- ``parser``     — file ⇄ Node boundary + inline-edge write-back (Phases 0/1A/1B)
- ``sync_queue`` — pending rename-propagation jobs over raw SQL (Phase 1B)
- ``db``         — ``GraphDatabase``: WAL SQLite + FTS5 derived index (Phase 2)
- ``links``      — wikilink extraction and title → UUID resolution (Phase 2)
- ``indexer``    — two-pass vault scan that rebuilds the DB from files (Phase 2)
"""
