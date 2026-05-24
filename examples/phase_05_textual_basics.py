"""Phase 5 — Minimal Textual application.

Run: python examples/phase_05_textual_basics.py

Shows the Textual lifecycle: compose → mount → key events.
Press Q to quit.
"""
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Label, ListView, ListItem

SAMPLE_NODES = ["Graph Theory", "BFS Algorithm", "Atomic Write", "Event Bus"]


class MinimalTUI(App):
    BINDINGS = [("q", "quit", "Quit")]

    def compose(self) -> ComposeResult:
        yield Header()
        yield ListView(*[ListItem(Label(name)) for name in SAMPLE_NODES])
        yield Footer()

    def on_mount(self) -> None:
        self.title = "Akanga — Phase 5 Demo"

    def action_quit(self) -> None:
        self.exit()


if __name__ == "__main__":
    MinimalTUI().run()
