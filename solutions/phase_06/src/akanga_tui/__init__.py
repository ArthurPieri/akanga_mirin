"""akanga_tui — Phase 5 Textual terminal interface for the Akanga graph.

Single-process design: the TUI imports ``akanga_core`` directly (no HTTP
round-trips). ``app.AkangaTUI`` is the entry point; run it with
``python -m akanga_tui.app --vault ./vault --db ./.akanga.db``.
"""
