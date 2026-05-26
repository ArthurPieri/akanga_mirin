from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Header, Input, ListItem, ListView, Markdown, Static, Label

from akanga_core.db import Database
from akanga_core.eventbus import EventBus
from akanga_core.graph import build_ego_graph
from akanga_core.models import Node

class NodeItem(ListItem):
    """Custom ListItem to store node metadata."""
    def __init__(self, node_id: str, title: str) -> None:
        super().__init__()
        self.node_id = node_id
        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(self.title)

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

    def __init__(self, db_path: str, vault_path: Path, event_bus: EventBus) -> None:
        super().__init__()
        self.db = Database(db_path)
        self.vault_path = vault_path
        self.event_bus = event_bus
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
        self.event_bus.subscribe("node_updated", self._on_node_updated)
        self.event_bus.set_loop(asyncio.get_running_loop())
        self._refresh_node_list()

    def _refresh_node_list(self) -> None:
        """Load all nodes from the database and update the sidebar."""
        # Simple implementation
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

    def _show_node(self, node_id: str) -> None:
        """Display node content and ego-graph."""
        node = self.db.get_node(node_id)
        if node:
            self.query_one("#node-markdown", Markdown).update(node.body)
            try:
                ego = build_ego_graph(node_id, self.db)
                # Simplified display
                lines = [f"Ego-graph for: [bold]{node.title}[/bold]"]
                # ... graph rendering logic ...
                self.query_one("#ego-graph-panel", Static).update("\n".join(lines))
            except Exception as e:
                self.query_one("#ego-graph-panel", Static).update(f"Error: {e}")

    async def _on_node_updated(self, **kwargs: Any) -> None:
        self.call_from_thread(self._refresh_node_list)
