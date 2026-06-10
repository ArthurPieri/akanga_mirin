"""AkangaTUI — three-panel Textual terminal interface for the knowledge graph.

Panel layout::

    ┌─────────────────┬──────────────────┬────────────────┐
    │  Node List      │  Content         │  Detail        │
    │  (left, ~25%)   │  (center, ~50%)  │  (right, ~25%) │
    └─────────────────┴──────────────────┴────────────────┘

Imports ``akanga_core`` directly — single process, no HTTP round-trips.
The ``GraphDatabase`` and ``VaultWatcher`` are initialised in ``on_mount``
after the Textual widget tree is fully built.

Key design decisions:
- ``compose()``  — declarative widget tree, called once by Textual.
- ``on_mount()`` — side-effectful initialisation (DB, data load).
- Actions map 1-to-1 with BINDINGS entries; Textual calls them automatically.
- Live updates arrive via the EventBus (watcher thread) and are forwarded
  to the Textual message loop with ``call_from_thread``.

Reference implementation:
  ``akanga_tui/app.py`` and ``akanga_tui/screens/main.py`` in the main repo.
"""
from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ListView


class AkangaTUI(App):
    """WHAT: Three-panel Textual terminal application for the Akanga knowledge graph.

    WHY: Provides a rich, keyboard-driven interface without requiring a web
    browser.  Single-process operation (imports akanga_core directly) keeps
    latency low and eliminates the need for a running server.

    HOW:
    - Subclass ``textual.app.App``.
    - Declare ``BINDINGS`` as a class attribute — Textual auto-maps each
      ``(key, action, description)`` tuple to ``action_<action>()``.
    - Build the widget tree in ``compose()`` using ``yield``.
    - Load data in ``on_mount()`` (widgets exist by then).
    - Subscribe to the EventBus in ``on_mount()`` and forward events to the
      Textual message loop via ``self.call_from_thread()``.
    """

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
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("n", "new_node", "New"),
        Binding("e", "edit_node", "Edit"),
        Binding("d", "delete_node", "Delete"),
        Binding("slash", "search", "Search", key_display="/"),
        Binding("g", "ego_graph", "Ego Graph"),
        Binding("shift+g", "vault_graph", "Vault Graph", key_display="G"),
        Binding("question_mark", "help_cheatsheet", "Help", key_display="?"),
        Binding("r", "refresh", "Refresh"),
        Binding("j", "focus_next_node", "Next node"),
        Binding("k", "focus_prev_node", "Prev node"),
        Binding("o", "open_url", "Open URL"),
    ]

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    def __init__(self, vault: Path, db_path: str, **kwargs) -> None:
        """WHAT: Initialise with the vault directory and database path.

        WHY: The TUI needs to know where the vault is for file operations
        (create, edit, delete) and where the DB is for fast graph queries.
        The DB and watcher are **not** started here — that happens in
        ``on_mount()`` after the widget tree is ready.

        HOW:
        1. Call ``super().__init__(**kwargs)`` to initialise the Textual App.
        2. Store ``self.vault = Path(vault)``.
        3. Store ``self.db_path = db_path``.
        4. Set ``self.db = None`` (will be set to a ``GraphDatabase`` in
           ``on_mount()``).
        5. Set ``self._selected_id: str | None = None`` (tracks the
           currently highlighted node for action methods).

        Args:
            vault:   Path to the vault root directory.
            db_path: Path to the SQLite database file.
            **kwargs: Forwarded to ``textual.app.App.__init__``.
        """
        raise NotImplementedError(
            "Call super().__init__(**kwargs), store vault and db_path as instance attributes, "
            "initialise self.db = None and self._selected_id = None"
        )

    # ------------------------------------------------------------------
    # Widget tree
    # ------------------------------------------------------------------

    def compose(self) -> ComposeResult:
        """WHAT: Build the widget tree — called once by Textual during mount.

        WHY: ``compose()`` is Textual's declarative UI builder.  Yielding
        widgets in order defines the visual hierarchy.  Panels must be
        given stable CSS IDs so action methods can query them later with
        ``self.query_one("#left-panel", ListView)``.

        HOW:
        1. ``yield Header()`` — top bar with app title.
        2. Open a ``Horizontal`` context manager with ``id="main-layout"``
           and inside yield three child containers:

           - ``ListView(id="left-panel")`` — scrollable node list.
           - ``Markdown("", id="center-panel")`` — content viewer.
           - ``Label("Select a node", id="right-panel")`` — detail panel
             (edges, backlinks, active results). You may replace this with
             a richer widget later.

        3. ``yield Footer()`` — bottom bar showing active key bindings.

        Note: do **not** load data here — widgets may not yet be mounted.
        Data loading belongs in ``on_mount()``.

        Yields:
            Widget instances in top-to-bottom, left-to-right order.
        """
        raise NotImplementedError(
            "yield Header(), then a Horizontal() with id='main-layout' containing "
            "ListView(id='left-panel'), Markdown(id='center-panel'), Label(id='right-panel'), "
            "then yield Footer()"
        )

    # ------------------------------------------------------------------
    # Lifecycle hooks
    # ------------------------------------------------------------------

    def on_mount(self) -> None:
        """WHAT: Called after all widgets are mounted — load initial data here.

        WHY: Data loading must happen after ``compose()`` so all widgets
        exist and can be queried.  Starting the file watcher here also
        ensures the widget tree is ready to receive live update calls.

        HOW:
        1. Import ``GraphDatabase`` from ``akanga_core.db``.
        2. Initialise ``self.db = GraphDatabase(self.db_path)``.
        3. Call ``self.load_node_list()`` to populate the left panel.
        4. (Optional) Start a ``VaultWatcher`` and subscribe a handler that
           calls ``self.call_from_thread(self.load_node_list)`` on
           ``file_changed`` and ``file_deleted`` events.
        """
        raise NotImplementedError(
            "Import and initialise GraphDatabase(self.db_path), store as self.db, "
            "then call self.load_node_list()"
        )

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def load_node_list(self) -> None:
        """WHAT: Query the DB for all nodes and populate the left panel ListView.

        WHY: The node list is the primary navigation mechanism.  It must be
        populated on mount and refreshed after any create / delete / rename
        operation so the display stays consistent with the vault on disk.

        HOW:
        1. Call ``self.db.list_nodes(limit=10_000)`` → list of Node objects.
        2. Get the ListView: ``node_list = self.query_one("#left-panel", ListView)``.
        3. Clear it: ``node_list.clear()``.
        4. For each node, create a ``ListItem(Label(node.title))``
           and append it to the list view.  Store ``node.id`` somewhere
           accessible (e.g. as a custom attribute on the ListItem, or by
           keeping a parallel list ``self._node_ids``).
        5. Update ``self.sub_title`` with the node count, e.g.
           ``f"Knowledge Graph ({len(nodes)} nodes)"``.
        """
        raise NotImplementedError(
            "db.list_nodes(limit=10_000) → clear ListView → append ListItem(Label(node.title)) "
            "for each node → update self.sub_title with count"
        )

    def show_node(self, node_id: str) -> None:
        """WHAT: Display the selected node's content and detail in the center/right panels.

        WHY: When the user selects a node in the left panel, the center and
        right panels must update to reflect that node's Markdown content,
        outgoing edges, backlinks, and active-check results.

        HOW:
        1. ``node = self.db.get_node(node_id)`` — returns a Node or None.
           Return early if None.
        2. Read the Markdown body from disk (the DB stores frontmatter
           metadata but not the full content): ``import frontmatter; post =
           frontmatter.load(node.path); content = post.content``.
        3. Update the center panel:
           ``self.query_one("#center-panel", Markdown).update(content)``.
        4. Query edges and backlinks:
           ``neighbors = self.db.get_neighbors(node_id)``   # outgoing edges → target nodes
           ``backlinks = self.db.get_backlinks(node_id)``   # incoming edges → source nodes
        5. Render a summary string and update the right panel Label.

        Args:
            node_id: UUID string of the node to display.
        """
        raise NotImplementedError(
            "db.get_node(node_id) → read body from disk → update #center-panel Markdown "
            "→ db.get_neighbors(node_id) for outgoing, db.get_backlinks(node_id) for incoming "
            "→ update #right-panel Label with summary"
        )

    # ------------------------------------------------------------------
    # Actions — invoked automatically by Textual from BINDINGS
    # ------------------------------------------------------------------

    def action_quit(self) -> None:
        """WHAT: Exit the application cleanly.

        HOW: Call ``self.exit()``.  Textual will call ``on_unmount`` on all
        widgets giving them a chance to clean up (close DB, stop watcher).
        """
        raise NotImplementedError("self.exit()")

    def action_search(self) -> None:
        """WHAT: Activate the search input widget and focus it.

        WHY: Full-text search across all node titles and content lets users
        navigate large vaults without scrolling.

        HOW (two options — pick one):

        Option A — inline search bar (simpler):
        1. Show a hidden ``Input`` widget in the footer area (add it in
           ``compose()`` with ``display: none``).
        2. Toggle its visibility: ``search_bar.display = not search_bar.display``.
        3. If now visible, call ``search_bar.focus()``.
        4. On ``on_input_submitted``: call ``self.db.search_fts(term)`` and
           repopulate the left panel.

        Option B — push a search Screen (more composable):
        1. Define a ``SearchScreen`` (subclass ``textual.screen.Screen``).
        2. Call ``self.push_screen(SearchScreen(), callback=self._on_search_result)``.
        3. In the callback, re-filter the node list with the returned term.
        """
        raise NotImplementedError(
            "Show and focus a search Input widget, or push a SearchScreen. "
            "On submit, call db.search_fts(term) and repopulate the left panel."
        )

    def action_new_node(self) -> None:
        """WHAT: Create a new note node in the vault.

        WHY: The primary creation workflow — learners must understand how
        the parser, DB, and file system interact when adding a node.

        HOW:
        1. Prompt the user for a title (push a small input screen or use
           an inline ``Input`` widget).
        2. On confirmation:

           a. Derive a safe filename from the title::

                  filename = title.lower().replace(" ", "-") + ".md"
                  path = self.vault / filename

           b. Build a frontmatter dict::

                  fm = {"title": title, "type": "note", "tags": [], "id": str(uuid4())}

           c. Write the file: ``write_node_file(path, fm, "")``
              (from ``akanga_core.parser``).
           d. Parse and index: ``node = parse_node_file(path)`` →
              ``self.db.upsert_node(node)``.
           e. Refresh: ``self.load_node_list()``.
           f. Notify: ``self.notify(f"Created: {title}")``.
        """
        raise NotImplementedError(
            "Prompt for title → derive safe filename → write_node_file → "
            "parse_node_file → db.upsert_node → load_node_list → notify"
        )

    def action_edit_node(self) -> None:
        """WHAT: Open the selected node's Markdown file in ``$EDITOR``.

        WHY: Rich text editing belongs in the user's preferred editor, not
        a terminal widget.  The TUI suspends, the editor runs in the
        foreground, and the TUI resumes and re-indexes after the editor exits.

        HOW:
        1. Guard: if ``self._selected_id`` is None, call
           ``self.notify("No node selected", severity="warning")`` and return.
        2. Look up the node: ``node = self.db.get_node(self._selected_id)``
        3. Determine the editor::

               editor = os.environ.get("EDITOR", "nano")

        4. Suspend the Textual app, run the editor, resume::

               with self.suspend():
                   subprocess.run([editor, node.path])

        5. After the editor exits, re-parse and re-index::

               node = parse_node_file(node.path)
               self.db.upsert_node(node)

        6. Call ``self.show_node(self._selected_id)`` to refresh the panels.
        7. ``self.notify("Saved")``.
        """
        raise NotImplementedError(
            "Guard no-selection, get node path, suspend app, run $EDITOR via subprocess, "
            "resume, re-parse and upsert, refresh panels"
        )

    def action_delete_node(self) -> None:
        """WHAT: Delete the selected node (file on disk + DB entry).

        WHY: Nodes must be removable.  The operation must clean up both the
        physical file and the DB rows (node + its edges) to keep the graph
        consistent.

        HOW:
        1. Guard: if ``self._selected_id`` is None, notify and return.
        2. Look up the node: ``node = self.db.get_node(self._selected_id)``.
        3. Ask for confirmation — push a small confirmation screen, or use
           ``self.notify`` with a bell and a second keypress pattern.
        4. On confirmation:

           a. Resolve the id explicitly: ``node_id = self._selected_id``
              (``node_id`` is not automatically in scope — you must assign it).

              Note: The `nodes` table has ON DELETE CASCADE on `source_id`, so
              calling ``db.delete_node(node_id)`` already removes outgoing edges.
              Only incoming edges (where ``target_id = node_id``) need manual
              cleanup::

                  with db._lock, db.conn:
                      db.conn.execute("DELETE FROM edges WHERE target_id = ?", (node_id,))

              Use ``db.conn`` (no underscore) — ``db._conn`` does not exist.

           b. ``os.remove(node.path)`` (only if the file exists)
           c. ``self.db.delete_node(node_id)``
           d. ``self._selected_id = None``
           e. Clear the center and right panels.
           f. ``self.load_node_list()``
           g. ``self.notify("Deleted")``.
        """
        raise NotImplementedError(
            "Guard no-selection, confirm, node_id = self._selected_id, "
            "with db._lock, db.conn: db.conn.execute('DELETE FROM edges WHERE target_id=?', (node_id,)), "
            "os.remove, db.delete_node(node_id), clear panels, load_node_list, notify"
        )

    def action_ego_graph(self) -> None:
        """WHAT: Show the ego-graph (immediate neighbourhood) of the selected node.

        WHY: Visualising a node's direct connections helps users understand
        the local structure of the knowledge graph without rendering the
        entire vault.

        HOW:
        1. Guard: if ``self._selected_id`` is None, notify and return.
        2. Fetch data::

               node = self.db.get_node(self._selected_id)
               neighbors = self.db.get_neighbors(self._selected_id)   # outgoing
               backlinks = self.db.get_backlinks(self._selected_id)   # incoming

        3. Render the ego graph as ASCII art or using Textual's ``Tree`` widget.
        4. Display in the center panel, or push a dedicated ``EgoGraphScreen``.
        """
        raise NotImplementedError(
            "Guard no-selection, fetch node/neighbors/edges, render ASCII or push EgoGraphScreen"
        )

    def action_vault_graph(self) -> None:
        """WHAT: Show a graph view of the entire vault.

        WHY: A high-level overview helps users spot clusters, isolated nodes,
        and over-connected hubs.

        HOW:
        1. ``nodes = self.db.list_nodes(limit=10_000)``
        2. Collect all edges (iterate nodes, call ``get_neighbors`` for outgoing
           and ``get_backlinks`` for incoming on each node, de-duplicate by edge ID).
        3. Render an ASCII overview or push a ``VaultGraphScreen``.

        Performance note: for large vaults (> 500 nodes) a full graph render
        can be slow.  Consider limiting to the top N nodes by edge count.
        """
        raise NotImplementedError(
            "list_nodes(limit=10_000), collect and deduplicate edges via get_neighbors/get_backlinks, "
            "render ASCII or push VaultGraphScreen"
        )

    def action_help_cheatsheet(self) -> None:
        """WHAT: Show the keyboard shortcut cheatsheet in a modal overlay.

        WHY: Users should always be able to discover available commands
        without leaving the app or reading external documentation.

        HOW:
        1. Build a table of all ``BINDINGS`` entries::

               rows = [(b.key_display or b.key, b.description) for b in self.BINDINGS]

        2. Render as a Textual ``DataTable`` or a formatted ``Markdown`` string.
        3. Push a ``ModalScreen`` (or any ``Screen``) that displays the table
           and dismisses on any key press.
        """
        raise NotImplementedError(
            "Build a table from self.BINDINGS, push a ModalScreen showing the table. "
            "Dismiss on any key press."
        )

    def action_focus_next_node(self) -> None:
        """WHAT: Move selection to the next node in the list.

        HOW:
        1. Get the NodeList widget: node_list = self.query_one(NodeList)
        2. Call node_list.action_cursor_down() or equivalent Textual method
        """
        raise NotImplementedError(
            "Move selection to the next item in the NodeList widget."
        )

    def action_focus_prev_node(self) -> None:
        """WHAT: Move selection to the previous node in the list.

        HOW:
        1. Get the NodeList widget: node_list = self.query_one(NodeList)
        2. Call node_list.action_cursor_up() or equivalent Textual method
        """
        raise NotImplementedError(
            "Move selection to the previous item in the NodeList widget."
        )

    def action_open_url(self) -> None:
        """WHAT: Open the selected virtual node's URL in the system browser.

        WHY: Virtual nodes represent external resources (GitHub repos, web pages).
        The `o` key launches the URL without leaving the TUI.

        HOW:
        1. Get selected node: node = self._get_selected_node()
        2. If node is None or node.type != "virtual": return (only for virtual nodes)
        3. import webbrowser, yaml, pathlib
           fm = yaml.safe_load(pathlib.Path(node.path).read_text().split("---")[1])
           url = fm.get("virtual", {}).get("url", "")
        4. If url: webbrowser.open(url)
        """
        raise NotImplementedError(
            "Read the virtual node's frontmatter.virtual.url and open with webbrowser.open()."
        )

    def action_refresh(self) -> None:
        """WHAT: Re-index the vault and refresh the node list.

        WHY: If files were changed outside the watcher (e.g. bulk edits,
        git checkout), the user can force a full re-sync without restarting.

        HOW:
        1. Import and call the full-scan indexer::

               from akanga_core.indexer import full_scan_and_index
               full_scan_and_index(self.vault, self.db)

        2. ``self.load_node_list()``
        3. If a node was selected, refresh its panels:
           ``self.show_node(self._selected_id)``
        4. ``self.notify("Refreshed")``.
        """
        raise NotImplementedError(
            "full_scan_and_index(self.vault, self.db) → load_node_list() → "
            "show_node if selected → notify('Refreshed')"
        )

    # ------------------------------------------------------------------
    # Event handlers
    # ------------------------------------------------------------------

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """WHAT: React to the user selecting an item in the node list.

        WHY: Textual fires this message automatically when the highlighted
        item changes.  This is where the right/center panels are updated.

        HOW:
        1. Get the selected node ID from the item (however you stored it
           during ``load_node_list()``).
        2. ``self._selected_id = node_id``
        3. ``self.show_node(node_id)``

        Args:
            event: Textual ``ListView.Selected`` message.
        """
        raise NotImplementedError(
            "Extract node_id from event.item, set self._selected_id, call self.show_node(node_id)"
        )

    def on_unmount(self) -> None:
        """WHAT: Clean up resources when the app exits.

        WHY: The DB connection and watcher thread must be closed gracefully
        to avoid SQLite locking errors on next launch.

        HOW:
        1. If ``self.db`` is not None: ``self.db.close()``.
        2. If you started a VaultWatcher in ``on_mount``, call ``watcher.stop()``.
        """
        raise NotImplementedError(
            "self.db.close() if self.db is not None; watcher.stop() if watcher was started"
        )


if __name__ == "__main__":
    # Boilerplate launcher so `make run` / `python -m akanga_tui.app` works.
    # Not part of the learning deliverable — no need to modify this block.
    import argparse

    _parser = argparse.ArgumentParser(description="Akanga TUI")
    _parser.add_argument("--vault", default="./vault")
    _parser.add_argument("--db", default="./.akanga.db")
    _args = _parser.parse_args()
    AkangaTUI(vault=_args.vault, db_path=_args.db).run()
