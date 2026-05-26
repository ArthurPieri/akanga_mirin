# Phase 5 — Terminal UI

**Core concept:** The TUI is the face of Akanga — the thing you open every day.
Everything built in Phases 0–4 was infrastructure. Phase 5 is where that
infrastructure becomes a tool you interact with. The design challenge is unusual:
the terminal is the canvas, the keyboard is the primary input, and yet the experience
should feel fast, navigable, and visually good — not like a throwback to 1990.

Modern terminals (Ghostty, Kitty, WezTerm, iTerm2) support true color, mouse events,
and even pixel-perfect image rendering. The ceiling is much higher than ASCII art.

> **Why this phase is worth the effort:** Phases 0–4 gave you a knowledge graph in a
> file. Phase 5 gives it a face. The TUI is the primary daily interface — the thing
> you'll actually open to navigate your notes. The implementation time (12–20h estimated)
> reflects that this is a full application, not a function. Budget accordingly.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Build a multi-panel Textual TUI application with keyboard-driven navigation
- Understand the Textual App lifecycle: compose → mount → event loop → action handlers
- Wire the TUI to akanga_core directly (single process, no HTTP) using EventBus for live updates
- Implement at least 6 keyboard actions (quit, new, edit, delete, search, ego-graph)
- Write Textual pilot tests using `async with app.run_test() as pilot`

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the linked foundation doc before proceeding.

- [ ] I understand asyncio coroutines and `await` → See `docs/foundations/asyncio-primer.md`
- [ ] I've completed Phases 0–4 and can use GraphDatabase
- [ ] I know how to run Textual's test pilot (`async with app.run_test()`)
- [ ] I've read the Textual quickstart (textual.textualize.io)

---

## Quick Start

```bash
make skeleton PHASE=5    # copy the starting code into ./src/
make test PHASE=5        # run the tests (they will fail initially)
make study PHASE=5       # open the tmux study session
make run                 # launch the Textual TUI (after implementation)
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### Reactive TUI

Textual's programming model: widgets declare reactive state variables; when state
changes, Textual automatically re-renders the affected widgets. Instead of manually
tracking what to redraw ("now repaint the right panel"), you declare "this panel's
content depends on `selected_node_id`" — when that variable changes, Textual handles
the rest. The same mental model as React or SwiftUI, applied to a character-cell
terminal. This is what enables live updates: a file-watcher event changes a reactive
variable, the widget re-renders without any imperative draw calls.

> Akanga node: `Reactive TUI`

→ Foundation doc: `docs/foundations/asyncio-primer.md` (async event loop section)

### Widget Composition

Building complex UIs by nesting simpler, reusable components. The Akanga layout
is three widgets composed inside a horizontal container: `NodeTree` (left),
`ContentView` (center), `DetailPanel` (right). Each widget manages its own state and
event handling independently. Neither widget knows anything about its siblings.
Composition over inheritance: you build a richer UI by combining small focused
widgets, not by subclassing a monolith.

> Akanga node: `Widget Composition`

### Event-Driven UI

UI components communicate through events rather than direct function calls. A key
press fires a `Key` event. Selecting a node fires a `NodeSelected` message. A
file-watcher notification fires a `NodeUpdated` message. Each widget handles the
events it cares about and ignores the rest. This decoupling means the TUI can receive
live updates from the file watcher (Phase 4) without the watcher knowing anything
about the TUI — they share only the EventBus.

> Akanga node: `Event-Driven UI`

→ Foundation doc: `docs/foundations/design-patterns.md` (Observer pattern)

### Keyboard-First, Mouse-Aware

Terminal UIs are keyboard-primary: every action has a keybinding, navigation works
without touching the mouse. But modern terminal emulators (Ghostty, Kitty, WezTerm,
iTerm2) expose full mouse events through the Kitty Mouse Protocol — Textual handles
click, scroll, and hover natively. The design principle: keyboard-first means every
action is *reachable* by keyboard; mouse-aware means clicking a node in the tree or
the graph view also works. Neither is the fallback — both are first-class.

> Akanga node: `Keyboard-First Mouse-Aware`

### Two-Layer Graph Renderer

The ego-graph is not rendered as ASCII art. Two layers, chosen at runtime based on
terminal capability:

**Layer 1 — Pixel-perfect (Kitty, Ghostty, WezTerm, iTerm2):** `textual-kitty` renders
the graph as a PNG image inside a Textual widget using the Kitty Terminal Graphics
Protocol. NetworkX computes a force-directed layout; matplotlib renders it (dark
background, colored nodes by type, styled edges by direction). The result is
indistinguishable from a desktop graph view. Falls back to Layer 2 if the protocol
is unsupported.

**Layer 2 — Universal half-block (every terminal):** `textual-canvas` uses half-block
Unicode characters (`▀ ▄ █`) to simulate a pixel grid at 2x vertical resolution.
Nodes are colored rounded boxes; edges are Bresenham lines terminated with Unicode
arrow characters (`→`, `⟵`). Significantly better than ASCII art and works anywhere.

The ASCII-art approach is not used — it has a hard ~12-node ceiling and is not worth
building as an end state.

> Akanga node: `Two-Layer Graph Renderer`

### Suspend / Resume

When a user presses `e` (edit), the TUI can optionally hand the terminal to an
external editor (v1 feature). Textual provides `app.suspend()` as a context manager:
the TUI pauses all rendering and input handling, the OS terminal is restored, the
external editor runs, and on exit Textual reclaims the terminal and resumes. During
suspension, the file watcher continues running — any changes the user makes in the
editor will be detected and indexed when the TUI resumes, triggering a live refresh.

> Akanga node: `Suspend/Resume`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Reactive TUI` | note | `is_applied_in` → `Akanga TUI`; `is_analogous_to` → `React`; `uses` → `Textual` |
| `Widget Composition` | note | `is_applied_in` → `Akanga TUI`; `subtype_of` → `UI Design Pattern` |
| `Event-Driven UI` | note | `uses` → `Event Bus`; `enables` → `Live Updates`; `is_applied_in` → `Akanga TUI` |
| `Keyboard-First Mouse-Aware` | note | `qualifies` → `Terminal UI`; `is_applied_in` → `Akanga TUI` |
| `Two-Layer Graph Renderer` | note | `uses` → `textual-kitty`; `uses` → `textual-canvas`; `solves` → `Graph Density Ceiling` |
| `Suspend/Resume` | note | `enables` → `External Editor Integration`; `is_applied_in` → `Akanga TUI`; `is_part_of` → `Textual` |
| `Textual` | reference | `implements` → `Reactive TUI`; `is_applied_in` → `Akanga TUI` |
| `textual-kitty` | reference | `implements` → `Two-Layer Graph Renderer`; `uses` → `Kitty Terminal Graphics Protocol` |
| `Kitty Terminal Graphics Protocol` | reference | `enables` → `Pixel Images in Terminal`; `is_applied_in` → `Two-Layer Graph Renderer` |

---

## Layout

```
┌─────────────────────────────────────────────────────────────────────┐
│  Akanga — Nhamandu                                      [?]  [q]   │
├─────────────────┬────────────────────────┬──────────────────────────┤
│ Nodes           │ Content                │ Detail                   │
│                 │                        │                          │
│ ▸ note          │ # Fast Thinking is     │ type:  note              │
│   Fast Thinking │   Unreliable           │ tags:  cognition         │
│   Kahneman S1S2 │                        │ graph: Nhamandu          │
│   Blink Gladwell│ Prose body here...     │        ProjectX          │
│                 │                        │                          │
│ ▸ reference     │                        │ Edges ──────────────     │
│   Thinking Fast │ [[Blink | contradicts]]│ ──[EP-002]──> Blink      │
│                 │                        │                          │
│                 │                        │ Backlinks ···────────    │
│                 │                        │ <··[EP-001]··· Kahneman  │
│ [/] filter...   │                        │                          │
└─────────────────┴────────────────────────┴──────────────────────────┘
  j/k:nav  Enter:open  n:new  e:edit  d:del  g:graph  /:search  ?:help
```

---

## Keybindings

Following vim and ranger conventions. Domain wins where vim and Akanga conflict.

| Key | Action | Convention |
|---|---|---|
| `j` / `k` | Navigate list down / up | Universal vim |
| `h` | Go back / close panel | ranger |
| `l` / `Enter` | Select node / open | ranger + universal |
| `gg` | Jump to top of list | Universal vim |
| `G` | Jump to bottom of list | Universal vim |
| `/` | Open search / filter | Universal vim |
| `Tab` | Next search result / switch panel focus | Avoids `n` conflict |
| `Ctrl+d` / `Ctrl+u` | Scroll half-page | Universal vim |
| `n` | New note (prompt for title) | Domain wins — lazygit does the same |
| `e` | Edit inline (TextArea, Ctrl+S to save) | ranger convention |
| `d` | Delete selected node (+ confirm) | lazygit / ranger |
| `g` | Ego-graph view (current node) | Mnemonic |
| `Ctrl+g` | Vault graph view (all nodes) | Disambiguates from `G` |
| `o` | Open URL in browser (reference nodes only) | ranger: open-with |
| `r` | Refresh — re-query DB, redraw tree | TUI convention |
| `?` | Keybinding cheatsheet overlay | lazygit convention |
| `q` | Quit / close current screen | Universal |
| Mouse click | Select node in tree or graph | Textual native |
| Mouse scroll | Scroll content / tree | Textual native |

---

## Graph View Design

The ego-graph screen is a separate Textual `Screen` pushed onto the stack:

```
┌─────────────────────────────────────────────────────────────────────┐
│  Graph: Fast Thinking is Unreliable          depth: 1  [+] [-] [q] │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│          ┌──────────────────┐                                       │
│          │ Kahneman S1 / S2 │                                       │
│          │    (note)        │                                       │
│          └────────┬─────────┘                                       │
│          EP-001 ··│·· supports (incoming)                           │
│                   ▼                                                 │
│          ┌──────────────────────────────┐                           │
│          │ Fast Thinking is Unreliable  │  ← root node              │
│          │         (note)               │                           │
│          └──────────┬───────────────────┘                           │
│          EP-002 ────│──── contradicts (outgoing)                    │
│                     ▼                                               │
│          ┌──────────────────┐                                       │
│          │  Blink — Gladwell│                                       │
│          │  (reference)     │                                       │
│          └──────────────────┘                                       │
│                                                                     │
│  [+]/[-]: depth   click: navigate to node   Esc: back              │
└─────────────────────────────────────────────────────────────────────┘
```

Layer 1 (Kitty/Ghostty/WezTerm): this is a pixel-rendered force-directed graph.
Layer 2 (everywhere else): Unicode half-block canvas with colored node boxes.

Clicking a node in the graph navigates to it (sets it as selected, pops back to
main screen with that node focused).

---

## What You Build

**`tui.py`** — `AkangaTUI(App)`:

Three main widgets:

| Widget | Responsibility |
|---|---|
| `NodeTree` | Nodes grouped by type, sorted by title. Tag hint. Workspace filter. Responds to `/` search. |
| `ContentView` | Renders selected node's markdown body. Switches to `TextArea` in edit mode (Ctrl+S saves). |
| `DetailPanel` | Type, tags, graph memberships, edges (outgoing with relation ID), backlinks (incoming), last 5 active results. |

Key reactive variables:
```python
selected_node_id: reactive[str | None] = reactive(None)
search_query:     reactive[str]         = reactive("")
edit_mode:        reactive[bool]        = reactive(False)
active_workspace: reactive[str]         = reactive("nhamandu-uuid")
```

**`graph_screen.py`** — `EgoGraphScreen(Screen)`:
```python
class EgoGraphScreen(Screen):
    depth: reactive[int] = reactive(1)
    # calls build_ego_graph() from Phase 3
    # detects terminal capability → Layer 1 or Layer 2 renderer
    # +/- keys adjust depth and re-render
    # click on node → navigate_to(node_id)
    # Esc → app.pop_screen()
```

**`graph_renderer.py`** — two render paths:
```python
def render_graph_kitty(ego: EgoGraph) -> Image:
    # NetworkX spring layout → matplotlib figure → PIL Image
    # Nodes: colored circles by type, labeled
    # Edges: solid for outgoing, dashed for incoming, labeled with relation

def render_graph_canvas(ego: EgoGraph, canvas: Canvas):
    # textual-canvas Bresenham lines for edges
    # Half-block colored rounded boxes for nodes
    # Unicode arrows at edge endpoints
    # Falls back to simple list if > 30 nodes
```

**Live update wiring:**
```python
def on_mount(self):
    self.eventbus.subscribe("node_updated", self._handle_node_updated)
    self.eventbus.subscribe("node_deleted", self._handle_node_deleted)
    self.sync_worker.drain(self.db, self.vault)

async def _handle_node_updated(self, node_id: str):
    await self.query_one(NodeTree).refresh_node(node_id)
    if self.selected_node_id == node_id:
        await self.query_one(ContentView).reload()
        await self.query_one(DetailPanel).reload()
```

---

## Common Pitfalls

**Loading data in compose() instead of on_mount():** `compose()` runs before widgets exist — database queries here can cause errors. Always load data in `on_mount()`.

**Blocking the event loop:** Textual is async. Any blocking operation (slow DB query, file read) on the main thread freezes the UI. Use `asyncio.to_thread()` for heavy work.

**Forgetting to refresh after mutations:** After create/delete/update, call `load_node_list()` explicitly — Textual doesn't auto-refresh.

**Hardcoding widget IDs:** Use CSS selectors (`app.query_one("#node-list")`) with explicit IDs for testability with Pilot.

---

## Deliverable

```python
async def test_node_tree_populated(app):
    async with app.run_test() as pilot:
        tree = app.query_one(NodeTree)
        assert len(tree._nodes) > 0

async def test_search_filters_tree(app):
    async with app.run_test() as pilot:
        await pilot.press("/")
        await pilot.type("cognition")
        await pilot.pause()
        visible = app.query_one(NodeTree).visible_nodes
        assert all("cognition" in n.tags for n in visible)

async def test_j_k_navigation(app):
    async with app.run_test() as pilot:
        await pilot.press("j")
        first = app.selected_node_id
        await pilot.press("j")
        second = app.selected_node_id
        assert first != second

async def test_edit_save_roundtrip(app, tmp_vault):
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("e")
        await pilot.type(" appended")
        await pilot.press("ctrl+s")
        content = app.selected_node_path.read_text()
        assert "appended" in content

async def test_live_update_adds_node(app, tmp_vault):
    async with app.run_test() as pilot:
        initial = len(app.query_one(NodeTree)._nodes)
        create(title="External Note", type="note", vault=tmp_vault)
        await asyncio.sleep(0.6)   # debounce + re-index
        assert len(app.query_one(NodeTree)._nodes) == initial + 1

async def test_graph_screen_opens(app):
    async with app.run_test() as pilot:
        await pilot.press("enter")
        await pilot.press("g")
        assert isinstance(app.screen, EgoGraphScreen)
        await pilot.press("escape")
        assert isinstance(app.screen, AkangaTUI)
```

Plus 9 vault nodes with typed edges. The `test_live_update_adds_node` test proves
the full pipeline from file change to TUI refresh. The graph screen tests prove
navigation works end-to-end.

---

## Reflect

> **Solo:** Sketch the full event flow when a user saves a file in an external editor while the TUI is open: file change → watcher → EventBus → TUI refresh. Which components are running in which threads?

> **Group:** Compare the TUI's approach (single process, direct DB access) with a web app approach (browser + HTTP API). What does each gain? What does each give up?
