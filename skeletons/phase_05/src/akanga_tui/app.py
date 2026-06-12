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
        Do NOT call the DB synchronously on the UI thread — a slow query
        (cold cache, large vault, WAL checkpoint) freezes every keystroke.
        Run the query in a worker and apply widget updates back on the UI
        thread:

        1. Fetch off the UI thread — either decorate this method with
           ``@work(thread=True)`` (``from textual import work``) and call
           ``nodes = self.db.list_nodes(limit=10_000)`` inside it, or from
           an async context use
           ``nodes = await asyncio.to_thread(self.db.list_nodes, limit=10_000)``.
        2. Apply the UI updates on the UI thread. Inside a thread worker
           that means wrapping steps 3–6 with
           ``self.call_from_thread(...)``; in the asyncio variant you are
           already back on the loop after the ``await``.
        3. Get the ListView: ``node_list = self.query_one("#left-panel", ListView)``.
        4. Clear it: ``node_list.clear()``.
        5. For each node, create a ``ListItem(Label(node.title))``
           and append it to the list view.  Store ``node.id`` somewhere
           accessible (e.g. as a custom attribute on the ListItem, or by
           keeping a parallel list ``self._node_ids``).
        6. Update ``self.sub_title`` with the node count, e.g.
           ``f"Knowledge Graph ({len(nodes)} nodes)"``.
        """
        raise NotImplementedError(
            "Fetch db.list_nodes(limit=10_000) in a worker (@work(thread=True) or "
            "asyncio.to_thread) — never synchronously on the UI thread. Then, back "
            "on the UI thread (call_from_thread), clear the ListView, append "
            "ListItem(Label(node.title)) per node, update self.sub_title with count"
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
        """WHAT: Edit the selected node's Markdown body INLINE in a
        ``TextArea`` widget in the center panel; ``Ctrl+S`` saves.

        WHY: Inline editing keeps the user inside the TUI — no terminal
        suspend, no external process, and the edit→save→re-index loop stays
        observable. This is the canonical Phase 5 design (see the phase doc
        keybindings: ``e`` = inline TextArea, ``Ctrl+S`` = save).

        HOW:
        1. Guard: if ``self._selected_id`` is None, call
           ``self.notify("No node selected", severity="warning")`` and return.
        2. Look up the node: ``node = self.db.get_node(self._selected_id)``,
           then read the current body from disk::

               import frontmatter
               post = frontmatter.load(node.path)

        3. Swap the center panel into edit mode: hide (or remove) the
           ``Markdown`` widget and mount a ``TextArea`` in its place,
           pre-loaded with ``post.content``::

               from textual.widgets import TextArea
               editor = TextArea(post.content, id="editor")
               # mount into the center container, then editor.focus()

        4. Bind the save key on the TextArea (e.g. a small ``TextArea``
           subclass with ``BINDINGS = [Binding("ctrl+s", "save", "Save")]``,
           or handle the key event). On ``Ctrl+S``:

           a. ``write_node_file(node.path, dict(post.metadata), editor.text)``
              (from ``akanga_core.parser`` — atomic write).
           b. Re-parse and re-index::

                  node = parse_node_file(node.path)
                  self.db.upsert_node(node)

           c. Remove the TextArea, restore the ``Markdown`` widget, and call
              ``self.show_node(self._selected_id)`` to refresh the panels.
           d. ``self.notify("Saved")``.
        5. (Optional) Escape cancels: discard the TextArea without writing.

        Optional v1 extra (not required, do AFTER inline editing works):
        a second binding that suspends to ``$EDITOR``
        (``with self.suspend(): subprocess.run([editor, node.path])``) for
        users who want their full editor. Note it does not survive every
        terminal/tmux combination — that is why it is the extra, not the
        default.
        """
        raise NotImplementedError(
            "Guard no-selection, load body with frontmatter.load(node.path), "
            "mount a TextArea over the center panel pre-filled with the body, "
            "on ctrl+s: write_node_file → parse_node_file → upsert_node → "
            "restore Markdown widget → show_node → notify('Saved')"
        )

    def action_delete_node(self) -> None:
        """WHAT: Delete the selected node (file on disk + DB entry).

        WHY: Nodes must be removable.  The operation must clean up both the
        physical file and the DB rows (node + its edges) to keep the graph
        consistent.

        HOW:
        1. Guard: if ``self._selected_id`` is None, notify and return.
        2. Look up the node: ``node = self.db.get_node(self._selected_id)``.
        3. Ask for confirmation with a ``ModalScreen`` — the same pattern as
           the help cheatsheet (action_help_cheatsheet): define a
           ``ConfirmDeleteScreen(ModalScreen[bool])`` showing
           "Delete '<title>'? (y/n)" with Yes/No buttons (or y/n keys), then::

               self.push_screen(ConfirmDeleteScreen(node.title), callback=...)

           Dismiss-once guard: do NOT call ``self.dismiss(True/False)``
           directly from the y/n/escape handlers. Key auto-repeat (or a
           second close event queued behind the first) can deliver another
           dismissal after the screen has already been popped — the second
           ``dismiss()`` then pops the screen BELOW it and the app dies with
           ``ScreenStackError``. Write a tiny mixin once and let EVERY modal
           in this file inherit it::

               class _DismissOnce:
                   _finished = False

                   def _finish(self, result=None) -> None:
                       if self._finished:
                           return  # duplicate event — already closed
                       self._finished = True
                       self.dismiss(result)

           then route every exit path through it — ``self._finish(True)`` /
           ``self._finish(False)`` here, ``self._finish(None)`` in the help
           and graph screens (``test_modal_double_dismiss_is_safe`` pins
           this guard).

           Run steps 4a–4g in the callback only when the result is True.
           Do NOT use a bell + second-keypress pattern — it is invisible to
           screen readers and indistinguishable from a stuck key.
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
            "Guard no-selection, push a ConfirmDeleteScreen(ModalScreen[bool]) and in "
            "its callback (result True): node_id = self._selected_id, "
            "with db._lock, db.conn: db.conn.execute('DELETE FROM edges WHERE target_id=?', (node_id,)), "
            "os.remove, db.delete_node(node_id), clear panels, load_node_list, notify"
        )

    def action_ego_graph(self) -> None:
        """WHAT: Push an ``EgoGraphScreen`` showing the selected node's
        neighbourhood as a Textual ``Tree`` widget.

        WHY: Visualising a node's direct connections helps users understand
        the local structure of the knowledge graph without rendering the
        entire vault. A dedicated ``Screen`` with a ``Tree`` gives free
        keyboard navigation, folding, and scrolling — do NOT hand-draw an
        ASCII-art graph in the content panel (the phase doc forbids it; the
        Phase 3 ``render_ascii`` helper is a debugging tool, not a UI).

        HOW:
        1. Guard: if ``self._selected_id`` is None, notify and return.
        2. Build the ego-graph with your Phase 3 deliverable::

               from akanga_core.graph import build_ego_graph
               ego = build_ego_graph(self._selected_id, self.db, max_depth=2)

        3. Define an ``EgoGraphScreen(Screen)`` whose ``compose()`` yields a
           ``Tree`` (``from textual.widgets import Tree``):

           - Tree root label: the ego root's title.
           - For each edge in ``ego.edges``, add a child labelled in the
             edge's natural direction, e.g.
             ``f"--[{edge.relation or 'links'}]--> {target.title}"`` under
             its source node (look titles up in ``ego.nodes``).
           - Bind ``q`` / ``escape`` to a single close action that routes
             through the ``_DismissOnce._finish`` guard (see
             action_delete_node step 3) — with TWO close keys a queued
             duplicate can arrive after the screen is already popped, and a
             bare ``self.app.pop_screen()`` would then pop the main screen.

        4. ``self.push_screen(EgoGraphScreen(ego))``.
        """
        raise NotImplementedError(
            "Guard no-selection, ego = build_ego_graph(self._selected_id, self.db, "
            "max_depth=2), push an EgoGraphScreen(Screen) rendering ego as a "
            "Textual Tree widget (no ASCII art)"
        )

    def action_vault_graph(self) -> None:
        """WHAT: Push a ``VaultGraphScreen`` (bound to ``Ctrl+g``) showing a
        vault-wide overview as a Textual ``Tree`` widget.

        WHY: A high-level overview helps users spot clusters, isolated nodes,
        and over-connected hubs.

        HOW:
        1. ``nodes = self.db.list_nodes(limit=10_000)``
        2. Collect all edges: iterate nodes and call ``get_edges_from`` on
           each (outgoing only is sufficient — every edge has exactly one
           source, so iterating sources covers the whole vault exactly once).
        3. Define a ``VaultGraphScreen(Screen)`` with a ``Tree``: one branch
           per node, children labelled ``--[relation]--> target_title``.
           Reuse the EgoGraphScreen rendering helper if you wrote one.
        4. ``self.push_screen(VaultGraphScreen(...))``.

        Performance note: for large vaults (> 500 nodes) a full graph render
        can be slow.  Consider limiting to the top N nodes by edge count.
        """
        raise NotImplementedError(
            "list_nodes(limit=10_000), collect edges via get_edges_from per node, "
            "push a VaultGraphScreen(Screen) rendering them as a Textual Tree widget"
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
           and dismisses on any key press — through the ``_DismissOnce``
           guard (action_delete_node step 3): any-key close is the easiest
           double-dismiss to trigger, since holding a key auto-repeats and
           queues a second event behind the first.

        Note: this ModalScreen is the pattern the delete confirmation
        (action_delete_node) reuses — build it once, parameterise twice.
        """
        raise NotImplementedError(
            "Build a table from self.BINDINGS, push a ModalScreen showing the table. "
            "Dismiss on any key press via the _DismissOnce._finish guard."
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

    def action_focus_last_node(self) -> None:
        """WHAT: Jump selection to the LAST node in the list (vim ``G``).

        HOW:
        1. Get the node list widget: node_list = self.query_one("#left-panel", ListView)
        2. Move the cursor to the last item — e.g. set
           ``node_list.index = len(node_list) - 1`` (guard the empty list),
           or call the equivalent Textual cursor method.
        """
        raise NotImplementedError(
            "Move selection to the last item in the node list (vim G)."
        )

    def action_open_url(self) -> None:
        """WHAT: Open the selected reference node's URL in the system browser.

        WHY: Reference nodes (type "reference", Phase 1B) point at external
        resources (web pages, papers, GitHub repos) via a top-level `url`
        frontmatter field. The `o` key launches the URL without leaving the TUI.

        HOW:
        1. Get selected node: node = self.db.get_node(self._selected_id)
           (guard self._selected_id is None first).
        2. If node is None or node.type != "reference": return
           (only reference nodes carry a URL).
        3. Read the top-level `url` frontmatter field::

               import webbrowser, frontmatter
               fm = frontmatter.load(node.path).metadata
               url = fm.get("url", "")

        4. If url: webbrowser.open(url)
        """
        raise NotImplementedError(
            "Guard selection; only for node.type == 'reference'. Read the top-level "
            "frontmatter 'url' field and open it with webbrowser.open()."
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
