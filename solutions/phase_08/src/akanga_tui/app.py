"""Textual terminal UI for the Akanga knowledge graph.

The TUI is a CONSUMER, not an owner: it receives a fully wired
:class:`~akanga_core.app.AkangaApp` (database, event bus, watcher, git)
and renders it. ``run_tui.py`` builds the AkangaApp, starts it, and
hands it in — so ``node_updated`` events published by the indexing
pipeline genuinely reach this screen.

Threading rule (the bug this file once shipped): the EventBus calls SYNC
handlers directly on the publishing thread — here, the watcher's debounce
worker. That is exactly the thread Textual's ``call_from_thread`` exists
for. Making the handler ``async`` instead would schedule it onto the
UI loop itself, where ``call_from_thread`` raises — live refresh becomes
dead code. So ``_on_node_updated`` is deliberately synchronous.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
)

from akanga_core.app import AkangaApp
from akanga_core.graph import build_ego_graph
from akanga_core.models import Node
from akanga_core.parser import parse_node_file

# The ego panel is 8 terminal rows tall (see CSS): header line + a few
# edge lines is all that fits before scrolling would be needed.
_EGO_MAX_EDGE_LINES = 5


class NodeItem(ListItem):
    """A sidebar entry that remembers which node it represents."""

    def __init__(self, node_id: str, title: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(escape(self.title))


class AkangaTUI(App):
    """Terminal UI for the Akanga knowledge graph."""

    CSS = """
    #main-layout {
        height: 1fr;
    }
    #sidebar {
        width: 30;
        border-right: tall $primary;
    }
    #content-area {
        width: 1fr;
    }
    #ego-graph-panel {
        height: 8;
        border-top: tall $primary;
        padding: 1;
        background: $surface;
    }
    """

    def __init__(
        self,
        core: AkangaApp | None = None,
        *,
        vault: str | Path | None = None,
        db_path: str | None = None,
    ) -> None:
        """Accept a wired AkangaApp (run_tui.py) OR bare paths (test harnesses).

        The path form builds an un-started AkangaApp — DB only, no watcher,
        no git — which is exactly what the cumulative phase-05 TUI tests need.
        """
        super().__init__()
        if core is None:
            if vault is None or db_path is None:
                raise TypeError("AkangaTUI needs either core= or both vault= and db_path=")
            core = AkangaApp(vault_path=str(vault), db_path=str(db_path))
        self.core = core
        self.db = core.db
        self.vault_path = core.vault_path
        self.event_bus = core.events
        self._all_nodes: list[Node] = []

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-layout"):
            with Vertical(id="sidebar"):
                yield Input(placeholder="Filter nodes...", id="filter-input")
                yield ListView(id="node-list")
            with Vertical(id="content-area"):
                yield Markdown(id="node-markdown")
                yield Static(id="ego-graph-panel")
        yield Footer()

    async def on_mount(self) -> None:
        # Register the UI loop FIRST so any async subscribers elsewhere
        # (e.g. the websocket broadcaster) stop buffering, then hook the
        # live-refresh handlers. Both graph mutations refresh the list:
        # an update may retitle a node, a deletion removes one.
        self.event_bus.set_loop(asyncio.get_running_loop())
        self.event_bus.subscribe("node_updated", self._on_node_updated)
        self.event_bus.subscribe("node_deleted", self._on_node_updated)
        self._refresh_node_list()

    # ------------------------------------------------------------------
    # Sidebar
    # ------------------------------------------------------------------

    def _refresh_node_list(self) -> None:
        """Load all nodes from the database and update the sidebar."""
        self._all_nodes = self.db.get_all_nodes(limit=1000)
        self._update_list_view(self.query_one("#filter-input", Input).value)

    def _update_list_view(self, filter_text: str) -> None:
        """Update the ListView based on the filter text."""
        node_list = self.query_one("#node-list", ListView)
        node_list.clear()
        for node in self._all_nodes:
            if filter_text.lower() in node.title.lower():
                node_list.append(NodeItem(node.id, node.title))

    def on_input_changed(self, event: Input.Changed) -> None:
        """Handle filter input changes."""
        if event.input.id == "filter-input":
            self._update_list_view(event.value)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle node selection in the sidebar."""
        item = event.item
        if isinstance(item, NodeItem):
            self._show_node(item.node_id)

    # ------------------------------------------------------------------
    # Detail + ego-graph panes
    # ------------------------------------------------------------------

    def _show_node(self, node_id: str) -> None:
        """Display node content and its ego-graph."""
        node = self.db.get_node(node_id)
        if node is None:
            return
        try:
            # BUG-01: prose lives on disk, not in the database. Node rows
            # may store vault-relative paths — anchor them before reading.
            file_path = Path(node.path)
            if not file_path.is_absolute():
                file_path = self.vault_path / file_path
            body = parse_node_file(file_path).content
        except OSError:
            body = "*(file missing on disk)*"
        self.query_one("#node-markdown", Markdown).update(body)

        panel = self.query_one("#ego-graph-panel", Static)
        try:
            panel.update(self._render_ego_panel(node))
        except Exception as exc:
            panel.update(f"Ego-graph unavailable: {escape(str(exc))}")

    def _render_ego_panel(self, node: Node) -> str:
        """Render the node's depth-1 ego-graph as markup text.

        Depth 1 (not the Graph-RAG default of 2) because the panel is 8
        rows tall — at depth 1 every edge touches the root, so each line
        reads as "this node →/← neighbor" with the edge's NATURAL stored
        direction preserved (D4/BUG-03: incoming edges are never
        inverted, only rendered with the arrow pointing back at us).
        """
        ego = build_ego_graph(node.id, self.db, max_depth=1)
        neighbor_count = len(ego.nodes) - 1  # nodes includes the root
        lines = [
            f"Ego-graph: [bold]{escape(node.title)}[/bold]"
            f" — {neighbor_count} neighbor(s), {len(ego.edges)} edge(s)"
        ]
        if not ego.edges:
            lines.append("  (no edges — this node is isolated)")
            return "\n".join(lines)

        for edge in ego.edges[:_EGO_MAX_EDGE_LINES]:
            if edge.source_id == node.id:
                other = ego.nodes.get(edge.target_id)
                arrow = "→"  # root --relation--> other
            else:
                other = ego.nodes.get(edge.source_id)
                arrow = "←"  # other --relation--> root
            other_title = escape(other.title) if other is not None else "?"
            lines.append(f"  {arrow} [italic]{escape(edge.relation)}[/italic] {other_title}")
        hidden = len(ego.edges) - _EGO_MAX_EDGE_LINES
        if hidden > 0:
            lines.append(f"  … +{hidden} more edge(s)")
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Live refresh
    # ------------------------------------------------------------------

    def _on_node_updated(self, **kwargs: Any) -> None:
        """Bus handler — runs on the watcher's worker thread, NOT the UI thread.

        SYNC on purpose: the EventBus invokes sync handlers directly on
        the publishing thread, which is precisely where Textual's
        ``call_from_thread`` is legal (it raises when called from the
        app's own thread). An ``async`` handler here would run on the UI
        loop and crash — see the module docstring.
        """
        self.call_from_thread(self._refresh_node_list)
