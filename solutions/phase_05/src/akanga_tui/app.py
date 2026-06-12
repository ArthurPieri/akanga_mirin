"""AkangaTUI — three-panel Textual terminal interface for the knowledge graph.

Panel layout::

    ┌─────────────────┬──────────────────┬────────────────┐
    │  Node List      │  Content         │  Detail        │
    │  (left, ~25%)   │  (center, ~50%)  │  (right, ~25%) │
    └─────────────────┴──────────────────┴────────────────┘

Imports ``akanga_core`` directly — single process, no HTTP round-trips.
The ``GraphDatabase`` and ``VaultWatcher`` are initialised in ``on_mount``
after the Textual widget tree is fully built.

Key design decisions (phase doc §Interaction States):

- ``compose()`` is declarative and side-effect free; all data loading and
  resource acquisition happens in ``on_mount()``.
- The node-list query runs off the UI thread (``asyncio.to_thread``) so a
  cold cache or WAL checkpoint can never freeze a keystroke. Per-node
  content reads stay synchronous — the doc's state table sanctions that
  ("reads are fast") and threading them would race rapid j/k navigation.
- Letter bindings are NON-priority: while the search ``Input`` is focused
  it rightly consumes ``j``/``k``/``n`` as text; ``escape`` hands focus
  back to the list. Only the editor's ``ctrl+s`` chord gets priority.
- ``d`` never deletes directly — it pushes ``ConfirmDeleteScreen``
  (``ModalScreen[bool]``) and destroys the file/rows only on a ``True``
  dismissal. The same modal pattern serves the ``?`` help cheatsheet.
- Live updates: a ``VaultWatcher`` publishes onto an ``EventBus``; the
  (sync) subscriber hops from the watchdog thread onto the Textual
  message loop with ``call_from_thread``.
- The graph screens (checkpoint 5.3) ship in their BASELINE form here:
  ``render_ascii(build_ego_graph(...))`` inside a scrollable ``Static``.
  The Kitty/canvas renderer is the stretch goal (``--extra graph``).
"""
from __future__ import annotations

import asyncio
import logging
import os
import webbrowser
from pathlib import Path
from typing import Any

import frontmatter as fm_io
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
    TextArea,
)

from akanga_core.db import GraphDatabase
from akanga_core.eventbus import EventBus
from akanga_core.graph import build_ego_graph, render_ascii
from akanga_core.indexer import full_scan_and_index, index_file
from akanga_core.parser import create, write_node_file
from akanga_core.sync_worker import SyncWorker
from akanga_core.watcher import VaultWatcher

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Modal screens — the ModalScreen pattern, built once and parameterised
# ---------------------------------------------------------------------------


class _DismissOnce:
    """Route every modal exit through ``_finish`` so a queued duplicate
    event can never dismiss the screen twice.

    WHY this exists: key auto-repeat — or a second close event queued
    behind the first (``q`` bouncing while ``escape`` is still in flight) —
    can deliver another dismissal after the screen has already left the
    stack. The second ``dismiss()`` then pops the screen BELOW it, and the
    next pop crashes the app on an empty stack (``ScreenStackError``).
    The guard makes dismissal idempotent: the first call wins, every later
    one is a no-op (phase doc §Interaction States, "Dismiss exactly once").
    """

    _finished = False

    def _finish(self, result=None) -> None:
        if self._finished:
            return  # duplicate event — the screen is already gone
        self._finished = True
        self.dismiss(result)


class ConfirmDeleteScreen(_DismissOnce, ModalScreen[bool]):
    """Ask before destroying anything — dismisses with True only on confirm.

    WHY a modal and not a bell + second keypress: a silent two-step ``d``
    is invisible to screen readers and indistinguishable from a stuck key
    (phase doc §Interaction States). The caller's ``push_screen`` callback
    receives the boolean and performs the destructive work only on True.
    """

    BINDINGS = [
        Binding("y", "confirm", "Yes"),
        Binding("n", "cancel", "No"),
        Binding("escape", "cancel", "Cancel"),
    ]

    DEFAULT_CSS = """
    ConfirmDeleteScreen {
        align: center middle;
    }
    ConfirmDeleteScreen > Vertical {
        width: auto;
        max-width: 60;
        height: auto;
        padding: 1 2;
        border: thick $error;
        background: $surface;
    }
    ConfirmDeleteScreen Horizontal {
        height: auto;
        align-horizontal: center;
    }
    ConfirmDeleteScreen Button {
        margin: 1 2 0 2;
    }
    """

    def __init__(self, node_title: str) -> None:
        super().__init__()
        self._node_title = node_title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static(f"Delete '{self._node_title}'?  (y/n)", id="confirm-question")
            with Horizontal():
                yield Button("Delete", variant="error", id="confirm-yes")
                yield Button("Cancel", variant="primary", id="confirm-no")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        event.stop()
        self._finish(event.button.id == "confirm-yes")

    def action_confirm(self) -> None:
        self._finish(True)

    def action_cancel(self) -> None:
        self._finish(False)


class HelpScreen(_DismissOnce, ModalScreen[None]):
    """The ``?`` keybinding cheatsheet overlay — any key dismisses it."""

    DEFAULT_CSS = """
    HelpScreen {
        align: center middle;
    }
    HelpScreen > VerticalScroll {
        width: auto;
        max-width: 70;
        height: auto;
        max-height: 80%;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def __init__(self, rows: list[tuple[str, str]]) -> None:
        super().__init__()
        self._rows = rows

    def compose(self) -> ComposeResult:
        lines = ["Keybinding cheatsheet", ""]
        lines += [f"  {key:<10} {description}" for key, description in self._rows]
        lines += ["", "(press any key to close)"]
        with VerticalScroll():
            yield Static("\n".join(lines), id="help-table")

    def on_key(self, event: events.Key) -> None:
        """Dismiss on ANY key press — a cheatsheet must never trap the user.

        Any-key close is also the easiest double-dismiss to trigger (hold a
        key and auto-repeat queues a second event) — hence ``_finish``.
        """
        event.stop()
        self._finish(None)


class GraphScreen(_DismissOnce, ModalScreen[None]):
    """Baseline graph view (checkpoint 5.3): pre-rendered ASCII in a Static.

    Both ``g`` (ego graph) and ``ctrl+g`` (vault graph) reuse this screen —
    only the heading and the body text differ. The pixel/canvas renderer
    described in the phase doc replaces the body widget, not the screen.
    """

    BINDINGS = [
        Binding("escape", "close", "Back"),
        Binding("q", "close", "Back"),
    ]

    DEFAULT_CSS = """
    GraphScreen {
        align: center middle;
    }
    GraphScreen > VerticalScroll {
        width: 80%;
        height: 80%;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    #graph-heading {
        text-style: bold;
        margin-bottom: 1;
    }
    """

    def __init__(self, heading: str, body: str) -> None:
        super().__init__()
        self._heading = heading
        self._body = body

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            yield Static(self._heading, id="graph-heading")
            yield Static(self._body, id="graph-art")

    def action_close(self) -> None:
        # esc and q BOTH close — the duplicate-event case _finish guards.
        self._finish(None)


class NewNodeScreen(_DismissOnce, ModalScreen[str | None]):
    """Prompt for a new node title; dismisses with the title or None."""

    BINDINGS = [Binding("escape", "cancel", "Cancel")]

    DEFAULT_CSS = """
    NewNodeScreen {
        align: center middle;
    }
    NewNodeScreen > Vertical {
        width: 60;
        height: auto;
        padding: 1 2;
        border: round $primary;
        background: $surface;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Static("New note title (Enter to create, Escape to cancel):")
            yield Input(placeholder="Title…", id="new-node-title")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        event.stop()  # keep this submit from reaching the app's search handler
        self._finish(event.value.strip() or None)

    def action_cancel(self) -> None:
        self._finish(None)


class EditorTextArea(TextArea):
    """Inline body editor mounted over the content view by ``e``.

    ``ctrl+s`` saves, ``escape`` discards. Both are PRIORITY bindings —
    chords (unlike printable letters) are safe to grab while typing, and
    saving must work even though the TextArea consumes ordinary keys.
    """

    BINDINGS = [
        Binding("ctrl+s", "save_note", "Save", priority=True),
        Binding("escape", "cancel_edit", "Cancel", priority=True),
    ]

    def action_save_note(self) -> None:
        app = self.app
        if isinstance(app, AkangaTUI):
            app._save_editor()

    def action_cancel_edit(self) -> None:
        app = self.app
        if isinstance(app, AkangaTUI):
            app._close_editor()


# ---------------------------------------------------------------------------
# The application
# ---------------------------------------------------------------------------


class AkangaTUI(App):
    """Three-panel Textual terminal application for the Akanga knowledge graph.

    WHY: a rich, keyboard-driven interface without requiring a web browser.
    Single-process operation (imports akanga_core directly) keeps latency
    low and eliminates the need for a running server.

    HOW: ``BINDINGS`` map 1-to-1 onto ``action_*`` methods; ``compose()``
    builds the widget tree behind stable CSS IDs; ``on_mount()`` opens the
    DB, drains the sync queue, populates the list, and starts the watcher.
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
    #content-view {
        height: 1fr;
    }
    #editor {
        height: 1fr;
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
    }
    """

    # Keymap is canonical per docs/learning/phase-05-terminal-ui.md §Keybindings:
    #   e      = inline TextArea edit (Ctrl+S saves)   — NOT $EDITOR
    #   g      = ego-graph screen (selected node)
    #   ctrl+g = vault-wide graph screen
    #   G      = jump to bottom of the node list (vim)
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
        Binding("j", "focus_next_node", "Next node"),
        Binding("k", "focus_prev_node", "Prev node"),
        Binding("shift+g", "focus_last_node", "Bottom", key_display="G"),
        Binding("o", "open_url", "Open URL"),
        # escape backs out of the search input; hidden from the footer.
        Binding("escape", "hide_search", "Back", show=False),
    ]

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, vault: Path | str, db_path: str, **kwargs: Any) -> None:
        """Store the vault directory and database path; defer all IO.

        The DB and watcher are NOT started here — ``on_mount()`` does that
        once the widget tree exists and can be queried.
        """
        super().__init__(**kwargs)
        self.vault = Path(vault)
        self.db_path = str(db_path)
        self.db: GraphDatabase | None = None
        self._selected_id: str | None = None
        self._filter_active = False                    # a search result is showing
        self._watcher: VaultWatcher | None = None
        self._eventbus: EventBus | None = None
        self._edit_path: str | None = None             # disk path under inline edit
        self._edit_metadata: dict[str, Any] = {}       # frontmatter preserved across edit

    # ------------------------------------------------------------------
    # Widget tree
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """Declarative widget tree — stable IDs, no data loading here."""
        yield Header()
        with Horizontal(id="main-layout"):
            yield ListView(id="left-panel")
            with Vertical(id="center-panel"):
                yield Markdown("", id="content-view")
            yield Label("Select a node", id="right-panel")
        yield Input(placeholder="Search nodes…", id="search-input", classes="hidden")
        yield Footer()

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    async def on_mount(self) -> None:
        """Open the DB, drain pending renames, load data, start live updates.

        Initial focus goes to the node list — an app that starts with
        nothing focused silently eats every keypress (phase doc).
        """
        self.db = GraphDatabase(self.db_path)
        # Stale rename-propagation jobs are patched before the first paint
        # so the list never shows display names the queue already retired.
        await asyncio.to_thread(SyncWorker().drain, self.db, self.vault)
        await self.load_node_list()
        self._start_live_updates()
        self.query_one("#left-panel", ListView).focus()

    def on_unmount(self) -> None:
        """Release the watcher thread and the DB connection on exit."""
        if self._watcher is not None:
            self._watcher.stop()
            self._watcher = None
        if self.db is not None:
            self.db.close()
            self.db = None

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    async def load_node_list(self, nodes: list[Any] | None = None) -> None:
        """Populate the left panel from the DB (or a pre-fetched node list).

        The DB query runs in a thread (``asyncio.to_thread``) — never
        synchronously on the UI thread, where a slow query would freeze
        every keystroke. Widget mutations happen back on the loop after
        the ``await``.
        """
        if self.db is None:
            return
        if nodes is None:
            nodes = await asyncio.to_thread(self.db.list_nodes, 10_000)

        node_list = self.query_one("#left-panel", ListView)
        await node_list.clear()
        await node_list.extend(
            ListItem(Label(node.title), name=node.id) for node in nodes
        )
        if nodes:
            node_list.index = 0  # highlight the first item if one exists
        self.sub_title = f"Knowledge Graph ({len(nodes)} nodes)"

    def show_node(self, node_id: str) -> None:
        """Render the selected node into the center and right panels.

        The body is re-read from DISK — the DB stores frontmatter metadata
        and never the prose (the files are the source of truth). A missing
        file degrades to an error message in the panel; the app stays up.
        """
        if self.db is None:
            return
        node = self.db.get_node(node_id)
        if node is None:
            return

        disk_path = self._disk_path(node.path)
        try:
            content = fm_io.load(disk_path).content
        except OSError:
            content = f"File not found: {disk_path}"

        self.query_one("#content-view", Markdown).update(content or "*(empty note)*")

        lines = [f"Type: {node.type}", f"Tags: {', '.join(node.tags) or '—'}", "", "Edges:"]
        edges_out = self.db.get_edges_from(node_id)
        if not edges_out:
            lines.append("  (no connections)")
        for target, relation, relation_id in edges_out:
            label = relation or "links"
            if relation_id:
                label = f"{label} ({relation_id})"
            lines.append(f"  --[{label}]--> {target.title}")
        lines += ["", "Backlinks:"]
        backlinks = self.db.get_backlinks(node_id)
        if not backlinks:
            lines.append("  (none)")
        lines += [f"  <-- {source.title}" for source in backlinks]

        self.query_one("#right-panel", Label).update("\n".join(lines))

    # ------------------------------------------------------------------
    # Actions — invoked automatically by Textual from BINDINGS
    # ------------------------------------------------------------------

    def action_quit(self) -> None:
        """Exit cleanly; ``on_unmount`` closes the DB and stops the watcher."""
        self.exit()

    def action_search(self) -> None:
        """Reveal and focus the search input (vim ``/``).

        While the Input has focus it consumes letter keys as text — that is
        correct (typing "node" must not create a node). ``escape`` hands
        focus back to the list via ``action_hide_search``.
        """
        search = self.query_one("#search-input", Input)
        search.remove_class("hidden")  # class toggle — reliable vs CSS specificity
        search.focus()

    async def action_hide_search(self) -> None:
        """Escape: hide the search bar and restore the unfiltered list."""
        search = self.query_one("#search-input", Input)
        if not search.display:
            return
        search.add_class("hidden")
        search.value = ""
        if self._filter_active:
            self._filter_active = False
            await self.load_node_list()
        self.query_one("#left-panel", ListView).focus()

    def action_new_node(self) -> None:
        """Prompt for a title, then create + index a new note node."""
        self.push_screen(NewNodeScreen(), callback=self._on_new_node_title)

    async def action_edit_node(self) -> None:
        """Swap the content view for an inline ``TextArea`` (``ctrl+s`` saves).

        The frontmatter dict is held aside untouched — the editor only ever
        rewrites the BODY, so ids, edges, and tags survive every save.
        """
        if self._selected_id is None:
            self.notify("No node selected", severity="warning")
            return
        if self.query("#editor"):
            return  # already editing
        node = self.db.get_node(self._selected_id) if self.db else None
        if node is None:
            return

        disk_path = self._disk_path(node.path)
        try:
            post = fm_io.load(disk_path)
        except OSError:
            self.notify(f"File not found: {disk_path}", severity="error")
            return

        self._edit_path = disk_path
        self._edit_metadata = dict(post.metadata)
        self.query_one("#content-view", Markdown).display = False
        editor = EditorTextArea(post.content, id="editor")
        await self.query_one("#center-panel", Vertical).mount(editor)
        editor.focus()

    def action_delete_node(self) -> None:
        """Push the confirmation modal; destruction happens only on True.

        A single ``d`` keypress must NEVER touch the filesystem or the DB —
        the lazygit anti-pattern this phase explicitly avoids.
        """
        if self._selected_id is None:
            self.notify("No node selected", severity="warning")
            return
        node = self.db.get_node(self._selected_id) if self.db else None
        if node is None:
            return
        self.push_screen(ConfirmDeleteScreen(node.title), callback=self._on_delete_confirmed)

    def action_ego_graph(self) -> None:
        """``g``: baseline ego-graph screen for the selected node (depth 2)."""
        if self._selected_id is None or self.db is None:
            self.notify("No node selected", severity="warning")
            return
        try:
            ego = build_ego_graph(self._selected_id, self.db, max_depth=2)
        except ValueError as exc:
            self.notify(str(exc), severity="error")
            return
        self.push_screen(GraphScreen(f"Ego graph: {ego.root.title}", render_ascii(ego)))

    def action_vault_graph(self) -> None:
        """``ctrl+g``: vault-wide edge overview.

        Outgoing edges only — every edge has exactly one source, so
        iterating sources covers the whole vault exactly once.
        """
        if self.db is None:
            return
        lines: list[str] = []
        for node in self.db.list_nodes(limit=10_000):
            edges = self.db.get_edges_from(node.id)
            if not edges:
                lines.append(f"{node.title}  (no outgoing edges)")
            for target, relation, _relation_id in edges:
                lines.append(f"{node.title} --[{relation or 'links'}]--> {target.title}")
        self.push_screen(GraphScreen("Vault graph", "\n".join(lines) or "(empty vault)"))

    def action_help_cheatsheet(self) -> None:
        """``?``: modal cheatsheet built from this class's own BINDINGS."""
        rows = [
            (binding.key_display or binding.key, binding.description)
            for binding in self.BINDINGS
            if isinstance(binding, Binding) and binding.show
        ]
        self.push_screen(HelpScreen(rows))

    def action_focus_next_node(self) -> None:
        """``j``: move the node-list cursor down (vim)."""
        self.query_one("#left-panel", ListView).action_cursor_down()

    def action_focus_prev_node(self) -> None:
        """``k``: move the node-list cursor up (vim)."""
        self.query_one("#left-panel", ListView).action_cursor_up()

    def action_focus_last_node(self) -> None:
        """``G``: jump to the bottom of the node list (vim)."""
        node_list = self.query_one("#left-panel", ListView)
        count = len(node_list.children)
        if count:
            node_list.index = count - 1

    def action_open_url(self) -> None:
        """``o``: open a reference node's ``url`` frontmatter field."""
        if self._selected_id is None or self.db is None:
            return
        node = self.db.get_node(self._selected_id)
        if node is None or node.type != "reference":
            return  # only reference nodes carry a URL
        try:
            url = fm_io.load(self._disk_path(node.path)).metadata.get("url", "")
        except OSError:
            return
        if url:
            webbrowser.open(url)

    async def action_refresh(self) -> None:
        """``r``: full re-scan for changes made outside the watcher."""
        if self.db is None:
            return
        await asyncio.to_thread(full_scan_and_index, str(self.vault), self.db)
        await self.load_node_list()
        if self._selected_id is not None:
            self.show_node(self._selected_id)
        self.notify("Refreshed")

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Track the cursor: the highlighted node drives the other panels."""
        item = event.item
        if item is None or not item.name:
            return
        self._selected_id = item.name
        self.show_node(item.name)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter on an item: same as highlight (panels already follow)."""
        if event.item is not None and event.item.name:
            self._selected_id = event.item.name
            self.show_node(event.item.name)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Search submit: FTS5 over title + tags, repopulating the list."""
        if event.input.id != "search-input" or self.db is None:
            return
        term = event.value.strip()
        if term:
            nodes = await asyncio.to_thread(self.db.search_fts, term, 100)
            self._filter_active = True
        else:
            nodes = await asyncio.to_thread(self.db.list_nodes, 10_000)
            self._filter_active = False
        await self.load_node_list(nodes)
        self.query_one("#left-panel", ListView).focus()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _disk_path(self, stored: str) -> str:
        """Resolve a DB-stored (vault-relative) node path to a disk path."""
        return stored if os.path.isabs(stored) else str(self.vault / stored)

    def _start_live_updates(self) -> None:
        """Watcher → EventBus → ``call_from_thread`` → reload the list.

        The subscriber runs on the watcher's daemon thread; widget work
        must hop onto the Textual message loop. Failure to start the
        watcher (exotic filesystems, sandboxes) degrades to manual ``r``
        refresh rather than crashing the app.
        """
        try:
            bus = EventBus()
            bus.subscribe("file_changed", self._on_vault_event)
            bus.subscribe("file_deleted", self._on_vault_event)
            watcher = VaultWatcher(self.vault, bus, debounce_ms=500)
            watcher.start()
            self._eventbus = bus
            self._watcher = watcher
        except Exception:  # noqa: BLE001 — live updates are an enhancement, not a dependency
            logger.warning("VaultWatcher unavailable; falling back to manual refresh (r)")

    def _on_vault_event(self, **kwargs: Any) -> None:
        """EventBus subscriber (watchdog thread) — forward to the UI loop."""
        try:
            self.call_from_thread(self.load_node_list)
        except Exception:  # noqa: BLE001 — app may be mid-shutdown
            pass

    def _on_new_node_title(self, title: str | None) -> None:
        """NewNodeScreen callback: create the file, index it, refresh."""
        if not title or self.db is None:
            return
        node = create(title, "note", self.vault)        # atomic write + re-parse
        index_file(node.path, self.db, str(self.vault))  # sets hash + relative path
        self.call_later(self.load_node_list)
        self.notify(f"Created: {title}")

    def _on_delete_confirmed(self, confirmed: bool | None) -> None:
        """ConfirmDeleteScreen callback — the ONLY place deletion happens.

        ``db.delete_node`` removes the node row, its FTS entry, and edges
        in BOTH directions (Phase 2 contract), so no extra SQL is needed.
        """
        if not confirmed or self._selected_id is None or self.db is None:
            return
        node_id = self._selected_id
        node = self.db.get_node(node_id)
        if node is not None:
            disk_path = self._disk_path(node.path)
            if os.path.exists(disk_path):
                os.remove(disk_path)
        self.db.delete_node(node_id)
        self._selected_id = None
        self.query_one("#content-view", Markdown).update("")
        self.query_one("#right-panel", Label).update("Select a node")
        self.call_later(self.load_node_list)
        self.notify("Deleted")

    def _save_editor(self) -> None:
        """``ctrl+s`` inside the editor: atomic write → re-index → re-render."""
        if self._edit_path is None or self.db is None:
            return
        editor = self.query_one("#editor", TextArea)
        write_node_file(self._edit_path, self._edit_metadata, editor.text)
        index_file(self._edit_path, self.db, str(self.vault))
        self._close_editor()
        if self._selected_id is not None:
            self.show_node(self._selected_id)
        self.notify("Saved")

    def _close_editor(self) -> None:
        """Remove the inline editor and restore the Markdown content view."""
        for editor in self.query("#editor"):
            editor.remove()
        self._edit_path = None
        self._edit_metadata = {}
        self.query_one("#content-view", Markdown).display = True
        self.query_one("#left-panel", ListView).focus()


# Alternate name accepted by the test loader.
AkangaApp = AkangaTUI


if __name__ == "__main__":
    # Boilerplate launcher so `make run` / `python -m akanga_tui.app` works.
    import argparse

    _parser = argparse.ArgumentParser(description="Akanga TUI")
    _parser.add_argument("--vault", default="./vault")
    _parser.add_argument("--db", default="./.akanga.db")
    _args = _parser.parse_args()
    AkangaTUI(vault=_args.vault, db_path=_args.db).run()
