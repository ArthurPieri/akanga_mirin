# Phase 05 — Terminal UI

## Goal

Build a keyboard-driven, three-panel terminal interface for the Akanga
knowledge graph using the [Textual](https://textual.textualize.io/) framework.

## Panel layout

```
┌─────────────────┬──────────────────┬────────────────┐
│  Node List      │  Content         │  Detail        │
│  (left, ~25%)   │  (center, ~50%)  │  (right, ~25%) │
└─────────────────┴──────────────────┴────────────────┘
```

- **Left**: `ListView` — all nodes, filterable via `/` search.
- **Center**: `Markdown` widget — body content of the selected node.
- **Right**: `Label` / custom widget — edges, backlinks, active-check results.

## What you will build

| File | Purpose |
|---|---|
| `src/akanga_tui/__init__.py` | Package marker |
| `src/akanga_tui/app.py` | Main `AkangaTUI` app — layout, bindings, actions |

## Key bindings

| Key | Action |
|---|---|
| `/` | Search nodes |
| `n` | Create new note |
| `e` | Edit in `$EDITOR` |
| `d` | Delete selected node |
| `g` | Ego-graph of selected node |
| `G` | Vault-wide graph overview |
| `?` | Keyboard shortcut cheatsheet |
| `r` | Full re-index and refresh |
| `q` | Quit |

## Key concepts

### Textual lifecycle
1. `compose()` — pure, declarative; yield widgets.
2. `on_mount()` — imperative; open DB, load data, start watcher.
3. `on_unmount()` — cleanup; close DB, stop watcher.

### Single-process, no HTTP
Import `akanga_core` directly.  No server process needed.

### Cross-thread updates
The `VaultWatcher` runs on a daemon thread.  To update the UI from the
watcher callback, use `self.call_from_thread(self.load_node_list)` — never
call Textual widget methods directly from a non-Textual thread.

### CSS sizing
Use fractional widths (`1fr`, `2fr`) rather than fixed pixel/character
counts — they adapt to any terminal width.

### `$EDITOR` integration
Suspend Textual with `with self.suspend():`, run the editor via
`subprocess.run([editor, path])`, then resume.  Re-parse and re-index
the file after the editor exits.

## Running the TUI

```bash
PYTHONPATH=src uv run python -m akanga_tui.app --vault ./vault --db ./.akanga.db
```

Or add a `__main__.py` entry point:

```python
# src/akanga_tui/__main__.py
import typer
from pathlib import Path
from akanga_tui.app import AkangaTUI

def main(vault: Path = Path("./vault"), db: str = "./.akanga.db"):
    AkangaTUI(vault=vault, db_path=db).run()

if __name__ == "__main__":
    typer.run(main)
```

## Running the tests

```bash
PYTHONPATH=src pytest tests/phase_05/ -v
```

Textual has a built-in test harness (`textual.testing.AppTest`) — use it
to simulate key presses and assert widget state without a real terminal.

## Suggested order

1. Implement `__init__` and `compose()` — get the three panels rendering.
2. Implement `on_mount()` and `load_node_list()` — see nodes in the left panel.
3. Implement `on_list_view_selected` and `show_node()` — center/right update on click.
4. Implement the edit/new/delete actions.
5. Implement search, ego-graph, vault-graph, help, refresh.
