"""AkangaTUI — three-panel Textual terminal interface for the knowledge graph.

Panel layout::

    ┌─────────────────┬──────────────────┬────────────────┐
    │  Node List      │  Content         │  Detail        │
    │  (left, ~25%)   │  (center, ~50%)  │  (right, ~25%) │
    └─────────────────┴──────────────────┴────────────────┘

Imports ``akanga_core`` directly — single process, no HTTP round-trips.
The ``GraphDatabase`` is initialised in ``on_mount`` after the Textual
widget tree is fully built (``compose`` must stay side-effect free).

This is the minimal-but-complete Phase 5 contract implementation used by
the Phase 6 cumulative tree: node list, content/detail panels, FTS
search (``/``), confirm-before-delete (``d`` pushes a ModalScreen — a
single keypress must NEVER destroy a file), and the ``?`` keybinding
cheatsheet built from ``BINDINGS`` itself.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Input, Label, ListItem, ListView, Markdown, Static

from akanga_core.db import GraphDatabase
from akanga_core.indexer import full_scan_and_index


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Modal "Delete '<title>'?" confirmation — dismisses with True/False.

    Deleting a node destroys a real file on disk, so a bare ``d`` press
    must never do it directly (the lazygit anti-pattern this phase
    avoids). An explicit modal is also visible to screen readers, unlike
    a bell + second-keypress scheme.
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    def __init__(self, title: str) -> None:
        super().__init__()
        self._title = title

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-dialog"):
            yield Label(f"Delete '{self._title}'?  (y/n)")

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HelpScreen(ModalScreen[None]):
    """The ``?`` keybinding cheatsheet, generated from the app's BINDINGS.

    Building the table from ``BINDINGS`` (instead of hand-writing it)
    means the cheatsheet can never drift out of sync with the real keymap.
    """

    BINDINGS = [Binding("escape", "close", "Close")]

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self._rows = rows

    def compose(self) -> ComposeResult:
        lines = ["Keybindings", ""]
        lines += [f"  {key:<10} {description}" for key, description in self._rows]
        lines += ["", "(escape to close)"]
        with Vertical(id="help-dialog"):
            yield Static("\n".join(lines))

    def action_close(self) -> None:
        self.dismiss(None)


class AkangaTUI(App):
    """Three-panel Textual terminal application for the Akanga knowledge graph.

    Single-process: the app owns its own ``GraphDatabase`` handle and
    talks to the vault files directly through ``akanga_core`` — no server
    round-trips, no serialization layer.
    """

    # Focus the node list on startup — NOT the hidden search Input. A focused
    # (even invisible) Input consumes printable keys, so app-level bindings
    # like "/" would never fire (the focus-discipline trap — see the phase-5
    # doc's Interaction States section).
    AUTO_FOCUS = "#left-panel"

    TITLE = "Akanga"
    SUB_TITLE = "Knowledge Graph"

    CSS = """
    Screen {
        background: $surface;
    }
    #main-layout {
        height: 1fr;
    }
    #left-panel {
        width: 1fr;
        min-width: 20;
        max-width: 50;
        border-right: solid $primary;
    }
    #center-panel {
        width: 2fr;
        min-width: 30;
    }
    #right-panel {
        width: 1fr;
        min-width: 20;
        max-width: 40;
        border-left: solid $primary;
    }
    #search-input.hidden {
        display: none;
    }
    #search-input {
        dock: bottom;
    }
    #confirm-dialog, #help-dialog {
        background: $panel;
        border: thick $primary;
        padding: 1 2;
        width: auto;
        height: auto;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_node", "Delete"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("question_mark", "help_cheatsheet", "Help", key_display="?"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "focus_next_node", "Next node"),
        Binding("k", "focus_prev_node", "Prev node"),
        Binding("shift+g", "focus_last_node", "Bottom", key_display="G"),
        Binding("escape", "dismiss_search", "Dismiss", show=False),
    ]

    def __init__(self, vault: Path | str, db_path: str, **kwargs: Any) -> None:
        """Store paths only — the DB opens in ``on_mount``, never here.

        ``__init__`` runs before the Textual screen exists; opening
        resources here would leak them if mounting fails.
        """
        super().__init__(**kwargs)
        self.vault = Path(vault)
        self.db_path = db_path
        self.db: GraphDatabase | None = None
        self._selected_id: str | None = None
        self._node_ids: list[str] = []

    # ------------------------------------------------------------------
    # Widget tree
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Declarative widget tree — no data loading here (see on_mount)."""
        yield Header()
        with Horizontal(id="main-layout"):
            yield ListView(id="left-panel")
            yield Markdown("", id="center-panel")
            yield Label("Select a node", id="right-panel")
        yield Input(placeholder="Search…", id="search-input", classes="hidden")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """Open the DB and populate the node list once widgets exist."""
        self.db = GraphDatabase(self.db_path)
        self.load_node_list()

    def on_unmount(self) -> None:
        """Close the DB so the next launch never hits a stale WAL lock."""
        if self.db is not None:
            self.db.close()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_node_list(self, nodes: list[Any] | None = None) -> None:
        """(Re)populate the left panel — one ListItem per node.

        Accepts an explicit node list so search results reuse the same
        rendering path as the full listing. ``_node_ids`` is the parallel
        index → UUID mapping the highlight handler reads; the ListView
        index alone cannot carry identity.
        """
        if self.db is None:
            return
        if nodes is None:
            nodes = self.db.list_nodes(limit=10_000)

        node_list = self.query_one("#left-panel", ListView)
        node_list.clear()
        self._node_ids = []
        for node in nodes:
            self._node_ids.append(node.id)
            node_list.append(ListItem(Label(node.title)))
        self.sub_title = f"Knowledge Graph ({len(nodes)} nodes)"

    def show_node(self, node_id: str) -> None:
        """Render the node's body (center) and edge summary (right)."""
        if self.db is None:
            return
        node = self.db.get_node(node_id)
        if node is None:
            return

        content = self._read_body(node)
        self.query_one("#center-panel", Markdown).update(content)

        neighbors = self.db.get_neighbors(node_id)
        backlinks = self.db.get_backlinks(node_id)
        summary = "\n".join(
            [
                f"[b]{node.title}[/b]  ({node.type})",
                "",
                f"→ links to {len(neighbors)}:",
                *[f"   {n.title}" for n in neighbors],
                f"← linked from {len(backlinks)}:",
                *[f"   {n.title}" for n in backlinks],
            ]
        )
        self.query_one("#right-panel", Label).update(summary)

    def _disk_path(self, node: Any) -> Path:
        """DB paths are vault-relative (indexer convention) — rebuild them."""
        path = Path(str(node.path))
        return path if path.is_absolute() else self.vault / path

    def _read_body(self, node: Any) -> str:
        """Read the Markdown body from disk; the DB never stores prose."""
        try:
            import frontmatter

            return frontmatter.load(self._disk_path(node)).content
        except OSError:
            return "*file missing on disk — press r to re-index*"

    # ------------------------------------------------------------------
    # Actions (Textual auto-dispatches from BINDINGS)
    # ------------------------------------------------------------------

    def action_search(self) -> None:
        """``/`` — reveal and focus the bottom search input."""
        search = self.query_one("#search-input", Input)
        search.remove_class("hidden")  # class toggle — reliable vs CSS specificity
        search.focus()

    def action_dismiss_search(self) -> None:
        """``escape`` — hide the search bar and return focus to the list."""
        search = self.query_one("#search-input", Input)
        if search.display:
            search.add_class("hidden")
            search.value = ""
            self.query_one("#left-panel", ListView).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Run FTS search and show the matches; empty query restores all."""
        if self.db is None:
            return
        term = event.value.strip()
        results = self.db.search_fts(term, limit=100) if term else None
        self.load_node_list(results)
        self.action_dismiss_search()

    def action_delete_node(self) -> None:
        """``d`` — confirm via ModalScreen, only then touch disk and DB."""
        node_id = self._selected_id or self._highlighted_id()
        if node_id is None or self.db is None:
            self.notify("No node selected", severity="warning")
            return
        node = self.db.get_node(node_id)
        if node is None:
            return

        def _on_confirm(confirmed: bool | None) -> None:
            if not confirmed:
                return
            disk_path = self._disk_path(node)
            if disk_path.exists():
                os.remove(disk_path)
            self.db.delete_node(node_id)  # also removes all touching edges
            self._selected_id = None
            self.query_one("#center-panel", Markdown).update("")
            self.query_one("#right-panel", Label).update("Select a node")
            self.load_node_list()
            self.notify(f"Deleted: {node.title}")

        self.push_screen(ConfirmDeleteScreen(node.title), _on_confirm)

    def action_help_cheatsheet(self) -> None:
        """``?`` — push the cheatsheet modal built from BINDINGS."""
        rows = [
            (binding.key_display or binding.key, binding.description)
            for binding in self.BINDINGS
            if binding.show
        ]
        self.push_screen(HelpScreen(rows))

    def action_refresh(self) -> None:
        """``r`` — full re-scan for changes made outside the watcher."""
        if self.db is None:
            return
        full_scan_and_index(str(self.vault), self.db)
        self.load_node_list()
        if self._selected_id:
            self.show_node(self._selected_id)
        self.notify("Refreshed")

    def action_focus_next_node(self) -> None:
        """``j`` — vim-style move down the node list."""
        self.query_one("#left-panel", ListView).action_cursor_down()

    def action_focus_prev_node(self) -> None:
        """``k`` — vim-style move up the node list."""
        self.query_one("#left-panel", ListView).action_cursor_up()

    def action_focus_last_node(self) -> None:
        """``G`` — jump to the bottom of the node list."""
        if self._node_ids:
            self.query_one("#left-panel", ListView).index = len(self._node_ids) - 1

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def _highlighted_id(self) -> str | None:
        """UUID of the currently highlighted list row, if any."""
        index = self.query_one("#left-panel", ListView).index
        if index is None or not (0 <= index < len(self._node_ids)):
            return None
        return self._node_ids[index]

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Track the cursor so actions know which node they apply to."""
        node_id = self._highlighted_id()
        if node_id is not None:
            self._selected_id = node_id
            self.show_node(node_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a row — same routing as a highlight."""
        self.on_list_view_highlighted(event)  # type: ignore[arg-type]


# Alternate name accepted by the test loader.
AkangaApp = AkangaTUI


if __name__ == "__main__":
    # Boilerplate launcher so `python -m akanga_tui.app` works.
    import argparse

    _parser = argparse.ArgumentParser(description="Akanga TUI")
    _parser.add_argument("--vault", default="./vault")
    _parser.add_argument("--db", default="./.akanga.db")
    _args = _parser.parse_args()
    AkangaTUI(vault=_args.vault, db_path=_args.db).run()
