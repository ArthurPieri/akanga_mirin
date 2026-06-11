"""AkangaTUI — three-panel Textual terminal interface for the knowledge graph.

Panel layout::

    ┌─────────────────┬──────────────────┬────────────────┐
    │  Node List      │  Content         │  Detail        │
    │  (left, ~25%)   │  (center, ~50%)  │  (right, ~25%) │
    └─────────────────┴──────────────────┴────────────────┘

Imports ``akanga_core`` directly — single process, no HTTP round-trips.
The ``GraphDatabase`` is initialised in ``on_mount`` after the Textual
widget tree is fully built; ``compose()`` stays purely declarative.

Key design decisions:

- ``compose()``  — declarative widget tree, called once by Textual.
- ``on_mount()`` — side-effectful initialisation (DB open, data load).
- Actions map 1-to-1 with BINDINGS entries; Textual calls them
  automatically.
- Destructive operations (delete) ALWAYS go through a confirmation
  ``ModalScreen`` — a single keypress that destroys a file is the
  lazygit anti-pattern this phase explicitly avoids.
"""
from __future__ import annotations

import os
import webbrowser
from pathlib import Path
from uuid import uuid4

import frontmatter
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen, Screen
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TextArea,
    Tree,
)

from akanga_core.db import GraphDatabase
from akanga_core.graph import EgoGraph, build_ego_graph
from akanga_core.indexer import full_scan_and_index
from akanga_core.parser import content_hash, parse_node_file, write_node_file

# ---------------------------------------------------------------------------
# Modal / overlay screens
# ---------------------------------------------------------------------------


class ConfirmDeleteScreen(ModalScreen[bool]):
    """Yes/no confirmation before a node is deleted.

    Dismisses with True only on an explicit 'y' — escape and 'n' both
    cancel. The pattern is shared with HelpScreen: build the ModalScreen
    once, parameterise twice.
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
        yield Vertical(
            Static(f"Delete '{self._title}'?", id="confirm-question"),
            Static("[y]es  ·  [n]o  ·  Esc cancels", id="confirm-hint"),
            id="confirm-dialog",
        )

    def action_confirm(self) -> None:
        self.dismiss(True)

    def action_cancel(self) -> None:
        self.dismiss(False)


class HelpScreen(ModalScreen[None]):
    """Keybinding cheatsheet built straight from the app's BINDINGS."""

    BINDINGS = [
        Binding("escape", "close", "Close"),
        Binding("q", "close", "Close", show=False),
        Binding("question_mark", "close", "Close", show=False),
    ]

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self._rows = rows

    def compose(self) -> ComposeResult:
        width = max((len(key) for key, _ in self._rows), default=1)
        lines = ["Keyboard shortcuts", ""]
        lines += [f"  {key.ljust(width)}  {description}" for key, description in self._rows]
        lines += ["", "Press Esc to close"]
        yield Vertical(Static("\n".join(lines)), id="help-dialog")

    def action_close(self) -> None:
        self.dismiss(None)


class TitlePromptScreen(ModalScreen[str | None]):
    """Single-line prompt for a new node title; escape cancels."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("New node title:"),
            Input(placeholder="Title…", id="title-input"),
            id="prompt-dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#title-input", Input).focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self.dismiss(event.value.strip() or None)

    def action_cancel(self) -> None:
        self.dismiss(None)


class EditorScreen(ModalScreen[str | None]):
    """Inline TextArea editor — Ctrl+S saves, Escape discards.

    Editing stays inside the TUI (no terminal suspend, no external
    process) so the edit→save→re-index loop remains observable.
    """

    BINDINGS = [
        Binding("ctrl+s", "save", "Save"),
        Binding("escape", "cancel", "Discard"),
    ]

    def __init__(self, body: str) -> None:
        super().__init__()
        self._body = body

    def compose(self) -> ComposeResult:
        yield Vertical(
            Static("Editing — Ctrl+S saves, Esc discards"),
            TextArea(self._body, id="editor"),
            id="editor-dialog",
        )

    def on_mount(self) -> None:
        self.query_one("#editor", TextArea).focus()

    def action_save(self) -> None:
        self.dismiss(self.query_one("#editor", TextArea).text)

    def action_cancel(self) -> None:
        self.dismiss(None)


class GraphScreen(Screen):
    """A Textual Tree rendering of edges — used for ego and vault graphs.

    A Tree gives free keyboard navigation, folding, and scrolling; the
    Phase 3 ``render_ascii`` helper is a debugging tool, not a UI.
    """

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("q", "close", "Back", show=False),
    ]

    def __init__(self, heading: str, branches: dict[str, list[str]]) -> None:
        super().__init__()
        self._heading = heading
        self._branches = branches

    def compose(self) -> ComposeResult:
        tree: Tree[None] = Tree(self._heading)
        tree.root.expand()
        for label, children in self._branches.items():
            branch = tree.root.add(label, expand=True)
            for child in children:
                branch.add_leaf(child)
        yield tree
        yield Footer()

    def action_close(self) -> None:
        self.app.pop_screen()


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------


class AkangaTUI(App):
    """Three-panel Textual terminal application for the Akanga graph.

    Single-process operation (imports akanga_core directly) keeps latency
    low and eliminates the need for a running server. BINDINGS map 1-to-1
    onto ``action_*`` methods; the canonical keymap comes from
    docs/learning/phase-05-terminal-ui.md §Keybindings.
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
    #confirm-dialog, #help-dialog, #prompt-dialog, #editor-dialog {
        width: 60;
        max-height: 80%;
        padding: 1 2;
        background: $panel;
        border: thick $primary;
    }
    #editor-dialog {
        width: 80%;
        height: 80%;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_node", "New"),
        Binding("e", "edit_node", "Edit"),
        Binding("d", "delete_node", "Delete"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("g", "ego_graph", "Ego Graph"),
        Binding("ctrl+g", "vault_graph", "Vault Graph"),
        Binding("question_mark", "help_cheatsheet", "Help", key_display="?"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "focus_next_node", "Next node", show=False),
        Binding("k", "focus_prev_node", "Prev node", show=False),
        Binding("G", "focus_last_node", "Bottom", show=False),
        Binding("o", "open_url", "Open URL", show=False),
        Binding("escape", "hide_search", "Close search", show=False),
    ]

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, vault: Path | str, db_path: str, **kwargs) -> None:
        """Store the vault and DB locations; defer all side effects.

        The DB is NOT opened here — ``on_mount()`` does that once the
        widget tree exists, so a construction failure can never leave a
        half-built app holding an open connection.
        """
        super().__init__(**kwargs)
        self.vault = Path(vault)
        self.db_path = db_path
        self.db: GraphDatabase | None = None
        self._selected_id: str | None = None

    # ------------------------------------------------------------------
    # Widget tree
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Declarative widget tree — no data loading here.

        Stable CSS IDs let every action query its panel later with
        ``self.query_one("#left-panel", ListView)``. The search input is
        composed hidden and toggled by ``action_search``.
        """
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
        """Open the DB and load initial data — widgets exist by now.

        When the DB is empty but the vault has files (first launch), a
        full scan rebuilds the derived index from the source of truth.
        Loading is synchronous: test vaults and personal vaults are small
        enough that the deterministic startup beats a worker hand-off.
        """
        self.db = GraphDatabase(self.db_path)
        if not self.db.list_nodes(limit=1):
            full_scan_and_index(str(self.vault), self.db)
        self.load_node_list()

    def on_unmount(self) -> None:
        """Close the DB so the next launch never hits a stale WAL lock."""
        if self.db is not None:
            self.db.close()
            self.db = None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_node_list(self) -> None:
        """Repopulate the left panel from the database."""
        if self.db is None:
            return
        self._populate_list(self.db.list_nodes(limit=10_000))

    def _populate_list(self, nodes: list) -> None:
        """Render *nodes* into the ListView, one ListItem per node.

        Each item carries its ``node_id`` as an attribute so selection
        handlers can map UI rows back to graph nodes without a parallel
        index list.
        """
        node_list = self.query_one("#left-panel", ListView)
        node_list.clear()
        for node in nodes:
            item = ListItem(Label(node.title))
            item.node_id = node.id
            node_list.append(item)
        self.sub_title = f"Knowledge Graph ({len(nodes)} nodes)"

    def show_node(self, node_id: str) -> None:
        """Render the node's body (center) and edge summary (right).

        The body is re-read from DISK — the DB stores frontmatter
        metadata only, never prose; the file is the source of truth.
        """
        if self.db is None:
            return
        node = self.db.get_node(node_id)
        if node is None:
            return

        path = self._node_path(node)
        try:
            content = frontmatter.load(str(path)).content
        except (OSError, ValueError):
            content = "*(file missing or unreadable)*"
        self.query_one("#center-panel", Markdown).update(content or "*(empty note)*")

        neighbors = self.db.get_neighbors(node_id)
        backlinks = self.db.get_backlinks(node_id)
        lines = [node.title, ""]
        lines.append(f"Links to ({len(neighbors)}):")
        lines += [f"  → {n.title}" for n in neighbors] or ["  (none)"]
        lines.append(f"Linked from ({len(backlinks)}):")
        lines += [f"  ← {n.title}" for n in backlinks] or ["  (none)"]
        self.query_one("#right-panel", Label).update("\n".join(lines))

    def _node_path(self, node) -> Path:
        """Resolve a node's stored path (vault-relative or absolute) to disk."""
        path = Path(str(node.path))
        return path if path.is_absolute() else self.vault / path

    # ------------------------------------------------------------------
    # Actions — invoked automatically by Textual from BINDINGS
    # ------------------------------------------------------------------

    def action_search(self) -> None:
        """Reveal and focus the search input (bound to '/')."""
        search = self.query_one("#search-input", Input)
        search.remove_class("hidden")  # class toggle — reliable vs CSS specificity
        search.focus()

    def action_hide_search(self) -> None:
        """Hide the search bar again (Escape) and return focus to the list."""
        search = self.query_one("#search-input", Input)
        if search.display:
            search.add_class("hidden")
            search.value = ""
            self.query_one("#left-panel", ListView).focus()

    def action_new_node(self) -> None:
        """Prompt for a title, then create + index the new note."""

        def _create(title: str | None) -> None:
            if not title or self.db is None:
                return
            filename = title.lower().replace(" ", "-") + ".md"
            path = self.vault / filename
            if path.exists():
                self.notify(f"File already exists: {filename}", severity="warning")
                return
            fm = {"id": str(uuid4()), "title": title, "type": "note", "tags": []}
            write_node_file(str(path), fm, "")
            node = parse_node_file(str(path))
            node.content_hash = content_hash(str(path))
            self.db.upsert_node(node)
            self.load_node_list()
            self.notify(f"Created: {title}")

        self.push_screen(TitlePromptScreen(), callback=_create)

    def action_edit_node(self) -> None:
        """Edit the selected node's body inline; Ctrl+S saves atomically."""
        if self.db is None or self._selected_id is None:
            self.notify("No node selected", severity="warning")
            return
        node = self.db.get_node(self._selected_id)
        if node is None:
            return
        path = self._node_path(node)
        try:
            post = frontmatter.load(str(path))
        except (OSError, ValueError):
            self.notify("Cannot read node file", severity="error")
            return

        def _save(text: str | None) -> None:
            if text is None or self.db is None:
                return  # discarded with Escape — file untouched
            write_node_file(str(path), dict(post.metadata), text)
            updated = parse_node_file(str(path))
            updated.content_hash = content_hash(str(path))
            self.db.upsert_node(updated)
            if self._selected_id:
                self.show_node(self._selected_id)
            self.notify("Saved")

        self.push_screen(EditorScreen(post.content), callback=_save)

    def action_delete_node(self) -> None:
        """Delete the selected node — ONLY after modal confirmation.

        Nothing is touched (no DB row, no file) until the user answers
        'y' on the ConfirmDeleteScreen. ``db.delete_node`` already cleans
        up edges in both directions plus the FTS row.
        """
        if self.db is None or self._selected_id is None:
            self.notify("No node selected", severity="warning")
            return
        node = self.db.get_node(self._selected_id)
        if node is None:
            return

        def _confirmed(result: bool | None) -> None:
            if not result or self.db is None or self._selected_id is None:
                return
            node_id = self._selected_id
            path = self._node_path(node)
            if path.exists():
                os.remove(path)
            self.db.delete_node(node_id)
            self._selected_id = None
            self.query_one("#center-panel", Markdown).update("")
            self.query_one("#right-panel", Label).update("Select a node")
            self.load_node_list()
            self.notify(f"Deleted: {node.title}")

        self.push_screen(ConfirmDeleteScreen(node.title), callback=_confirmed)

    def action_ego_graph(self) -> None:
        """Push a Tree screen of the selected node's depth-2 neighbourhood."""
        if self.db is None or self._selected_id is None:
            self.notify("No node selected", severity="warning")
            return
        try:
            ego = build_ego_graph(self._selected_id, self.db, max_depth=2)
        except ValueError:
            self.notify("Node not found in the graph", severity="error")
            return
        self.push_screen(self._graph_screen(f"Ego graph: {ego.root.title}", ego))

    def action_vault_graph(self) -> None:
        """Push a Tree screen of every node's outgoing edges (Ctrl+G).

        Outgoing-only is sufficient: every edge has exactly one source,
        so iterating sources covers the whole vault exactly once.
        """
        if self.db is None:
            return
        branches: dict[str, list[str]] = {}
        for node in self.db.list_nodes(limit=10_000):
            children = [
                f"--[{relation or 'links'}]--> {target.title}"
                for target, relation, _relation_id in self.db.get_edges_from(node.id)
            ]
            branches[node.title] = children
        self.push_screen(GraphScreen("Vault graph", branches))

    def _graph_screen(self, heading: str, ego: EgoGraph) -> GraphScreen:
        """Group an EgoGraph's edges by source title for Tree rendering.

        Edges render in their NATURAL direction — never a reversed arrow.
        """
        def _title(node_id: str) -> str:
            node = ego.nodes.get(node_id)
            return getattr(node, "title", node_id) if node is not None else node_id

        branches: dict[str, list[str]] = {}
        for edge in ego.edges:
            label = f"--[{edge.relation or 'links'}]--> {_title(edge.target_id)}"
            branches.setdefault(_title(edge.source_id), []).append(label)
        return GraphScreen(heading, branches)

    def action_help_cheatsheet(self) -> None:
        """Show the keybinding cheatsheet built from BINDINGS ('?')."""
        rows = [(b.key_display or b.key, b.description) for b in self.BINDINGS]
        self.push_screen(HelpScreen(rows))

    def action_focus_next_node(self) -> None:
        """Move selection down one node (vim 'j')."""
        node_list = self.query_one("#left-panel", ListView)
        node_list.focus()
        node_list.action_cursor_down()

    def action_focus_prev_node(self) -> None:
        """Move selection up one node (vim 'k')."""
        node_list = self.query_one("#left-panel", ListView)
        node_list.focus()
        node_list.action_cursor_up()

    def action_focus_last_node(self) -> None:
        """Jump to the last node in the list (vim 'G')."""
        node_list = self.query_one("#left-panel", ListView)
        items = list(node_list.query(ListItem))
        if items:  # guard the empty list
            node_list.focus()
            node_list.index = len(items) - 1

    def action_open_url(self) -> None:
        """Open the selected reference node's URL in the browser ('o').

        Only reference nodes (Phase 1B) carry a top-level ``url``
        frontmatter field; the field lives in the FILE, never the DB.
        """
        if self.db is None or self._selected_id is None:
            return
        node = self.db.get_node(self._selected_id)
        if node is None or node.type != "reference":
            return
        try:
            url = frontmatter.load(str(self._node_path(node))).metadata.get("url", "")
        except (OSError, ValueError):
            return
        if url:
            webbrowser.open(url)

    def action_refresh(self) -> None:
        """Force a full re-index ('r') — covers out-of-band file edits."""
        if self.db is None:
            return
        full_scan_and_index(str(self.vault), self.db)
        self.load_node_list()
        if self._selected_id:
            self.show_node(self._selected_id)
        self.notify("Refreshed")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Track the cursor as it moves so actions know the current node."""
        node_id = getattr(event.item, "node_id", None) if event.item else None
        if node_id:
            self._selected_id = node_id
            self.show_node(node_id)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on a list row — same routing as a highlight."""
        node_id = getattr(event.item, "node_id", None) if event.item else None
        if node_id:
            self._selected_id = node_id
            self.show_node(node_id)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Run an FTS search from the search bar and show the matches."""
        if event.input.id != "search-input" or self.db is None:
            return
        term = event.value.strip()
        nodes = self.db.search_fts(term, limit=100) if term else self.db.list_nodes(10_000)
        self._populate_list(nodes)
        event.input.add_class("hidden")
        self.query_one("#left-panel", ListView).focus()


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
