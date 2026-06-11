"""akanga_tui — Phase 5 Textual terminal interface for the Akanga graph.

One module, one process: ``app.py`` imports ``akanga_core`` directly —
no HTTP round-trips, no running server. Launch with::

    python -m akanga_tui.app --vault ./vault --db ./.akanga.db
"""
