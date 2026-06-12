# Phase 5 — Terminal UI

**Estimated time: 12–20h + ~1h vault/reflect**

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

> **WARNING — tmux will break the graph renderer; run the TUI in a plain terminal window.**
> The Kitty graphics protocol (the stretch-goal pixel renderer below) degrades or
> silently fails inside tmux: passthrough must be explicitly enabled
> (`set -g allow-passthrough on`), it requires tmux ≥ 3.3, and terminal-capability
> detection *from inside* tmux is unreliable even then — the renderer may wrongly
> conclude your terminal can't do graphics. This is a known trap the author lost
> hours to. For all graph-rendering work, run the TUI in a plain Ghostty or Kitty
> window — **not** inside the `make study` tmux pane. Keep tmux for the docs/tests
> panes; launch the app itself with `make run` from a separate terminal (`make run`
> prints this reminder). Everything else in this phase (list, detail, edit, search)
> works fine inside tmux.

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

> → Foundation doc: `docs/foundations/asyncio-primer.md` (async event loop section)

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

> → Foundation doc: `docs/foundations/design-patterns.md` (Observer pattern)

### Keyboard-First, Mouse-Aware

Terminal UIs are keyboard-primary: every action has a keybinding, navigation works
without touching the mouse. But modern terminal emulators (Ghostty, Kitty, WezTerm,
iTerm2) expose full mouse events through the Kitty Mouse Protocol — Textual handles
click, scroll, and hover natively. The design principle: keyboard-first means every
action is *reachable* by keyboard; mouse-aware means clicking a node in the tree or
the graph view also works. Neither is the fallback — both are first-class.

> Akanga node: `Keyboard-First Mouse-Aware`

### Two-Layer Graph Renderer (STRETCH GOAL)

**This renderer is a stretch goal, not a deliverable.** The baseline graph view in
this phase is the `render_ascii()` ego-graph you already built in Phase 3, displayed
in a Textual screen. It is tested, dependency-free, and good enough up to ~12 nodes.
The two-layer renderer is what you build *after* checkpoints 5.1 and 5.2 are green,
if you want to push further. Be honest with yourself about the costs: it needs extra
dependencies (`uv sync --extra graph` installs the optional `[graph]` group —
textual-image, textual-canvas, NetworkX, matplotlib), and Layer 1 works best in a
plain terminal window (see the tmux warning above).

Two layers, chosen at runtime based on terminal capability:

**Layer 1 — Pixel-perfect (Kitty, Ghostty, WezTerm, iTerm2):** `textual-image` renders
the graph as a PNG image inside a Textual widget using the Kitty Terminal Graphics
Protocol. NetworkX computes a force-directed layout; matplotlib renders it (dark
background, node shape + color by type, styled edges by direction). The result is
indistinguishable from a desktop graph view. Falls back to Layer 2 if the protocol
is unsupported.

**Layer 2 — Universal half-block (every terminal):** `textual-canvas` uses half-block
Unicode characters (`▀ ▄ █`) to simulate a pixel grid at 2x vertical resolution.
Nodes are colored rounded boxes; edges are Bresenham lines terminated with Unicode
arrow characters (`→`, `⟵`). Significantly better than ASCII art and works anywhere.

> **Layer-1 field notes (from the reference build):** terminal-capability
> auto-detection routinely fails under tmux — and `make study` *is* tmux — so
> don't trust detection: when you know the terminal is Ghostty or Kitty, force
> the Kitty graphics protocol explicitly. And render the matplotlib figure at
> 2× the target pixel size, then downscale (supersampling) — node labels stay
> legible at terminal-cell resolutions.

> Akanga node: `Two-Layer Graph Renderer`

### Suspend / Resume (optional upgrade)

The **deliverable** edit model is inline: pressing `e` swaps the content panel to a
`TextArea`, and `Ctrl+S` saves. Suspend/resume is the *optional upgrade* on top:
the TUI hands the terminal to an external `$EDITOR`. Textual provides `app.suspend()`
as a context manager: the TUI pauses all rendering and input handling, the OS terminal
is restored, the external editor runs, and on exit Textual reclaims the terminal and
resumes. During suspension, the file watcher continues running — any changes the user
makes in the editor will be detected and indexed when the TUI resumes, triggering a
live refresh.

> Akanga node: `Suspend/Resume`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Reactive TUI` | note | `is_applied_in` → `Akanga TUI`; `is_analogous_to` → `React`; `uses` → `Textual` |
| `Widget Composition` | note | `is_applied_in` → `Akanga TUI`; `subtype_of` → `UI Design Pattern` |
| `Event-Driven UI` | note | `uses` → `Event Bus`; `enables` → `Live Updates`; `is_applied_in` → `Akanga TUI` |
| `Keyboard-First Mouse-Aware` | note | `qualifies` → `Terminal UI`; `is_applied_in` → `Akanga TUI` |
| `Two-Layer Graph Renderer` | note | `uses` → `textual-image`; `uses` → `textual-canvas`; `solves` → `Graph Density Ceiling` |
| `Suspend/Resume` | note | `enables` → `External Editor Integration`; `is_applied_in` → `Akanga TUI`; `is_part_of` → `Textual` |
| `Textual` | reference | `implements` → `Reactive TUI`; `is_applied_in` → `Akanga TUI` |
| `textual-image` | reference | `implements` → `Two-Layer Graph Renderer`; `uses` → `Kitty Terminal Graphics Protocol` |
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
│   Thinking Fast │ [[Blink | contradicts]]│ this ─[EP-002]→ Blink    │
│                 │                        │                          │
│                 │                        │ Backlinks ──────────     │
│                 │                        │ Kahneman ─[EP-001]→ this │
│ [/] filter...   │                        │                          │
└─────────────────┴────────────────────────┴──────────────────────────┘
  j/k:nav  Enter:open  n:new  e:edit  d:del  g:graph  /:search  ?:help
```

---

## Keybindings

Following vim and ranger conventions. Domain wins where vim and Akanga conflict.

> **This table is canonical** — the skeleton's `BINDINGS` match it. The two keys
> most worth pinning down: `G` is **jump to bottom of list** (universal vim — never
> the graph), and the vault graph lives on `Ctrl+g`. `e` opens the **inline
> TextArea** editor saved with `Ctrl+S`; suspending to `$EDITOR` is an optional
> upgrade, not the binding's deliverable behavior.

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

## Graph View Design (checkpoint 5.3 — stretch)

The ego-graph screen is a separate Textual `Screen` pushed onto the stack. The
**baseline** version renders `render_ascii(build_ego_graph(...))` from Phase 3 inside
a `Static` widget — build that first. The pixel/canvas version sketched below is the
stretch version (see the stretch-goal concept and the tmux warning above):

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

**`akanga_tui/app.py`** — `AkangaTUI(App)` (constructor takes `vault` and `db_path`):

Three main panels:

| Panel | Responsibility |
|---|---|
| `NodeTree` (left) | Nodes grouped by type, sorted by title. Tag hint. Workspace filter. Responds to `/` search. |
| `ContentView` (center) | Renders selected node's markdown body. Switches to `TextArea` in edit mode (Ctrl+S saves). |
| `DetailPanel` (right) | Type, tags, graph memberships, edges (outgoing with relation ID), backlinks (incoming), last 5 active results. |

The skeleton starts you with stock Textual widgets behind stable IDs —
`ListView(id="left-panel")`, `Markdown(id="center-panel")`, `Label(id="right-panel")` —
and the tests only require ListView-compatible behavior. Growing them into the custom
`NodeTree` / `ContentView` / `DetailPanel` widgets described here is the intended
trajectory, not the starting requirement.

> **Optional upgrade — `$EDITOR` suspend.** Once the inline TextArea editor works
> (that is the deliverable the tests certify), you can add a second edit path that
> suspends the TUI and opens the file in `$EDITOR`:
>
> ```python
> with self.suspend():
>     subprocess.run([os.environ.get("EDITOR", "nano"), node.path])
> # re-parse, upsert, refresh panels on resume
> ```
>
> Bind it to a *different* key (e.g. `E`) so `e` keeps its canonical inline meaning.
> This is a v1 extra — skip it entirely and lose nothing this phase depends on.

Key reactive variables:
```python
selected_node_id: reactive[str | None] = reactive(None)
search_query:     reactive[str]         = reactive("")
edit_mode:        reactive[bool]        = reactive(False)
active_workspace: reactive[str]         = reactive("nhamandu-uuid")
```

**`graph_screen.py`** — `EgoGraphScreen(Screen)` (checkpoint 5.3 — baseline part):
```python
class EgoGraphScreen(Screen):
    depth: reactive[int] = reactive(1)
    # calls build_ego_graph() from Phase 3
    # baseline: render_ascii(ego) in a Static widget
    # stretch:  detects terminal capability → Layer 1 or Layer 2 renderer
    # +/- keys adjust depth and re-render
    # click on node → navigate_to(node_id)
    # Esc → app.pop_screen()
```

**`graph_renderer.py`** — two render paths (stretch — see the stretch-goal
concept and the tmux warning above; illustrative sketch, no skeleton ships):
```python
def render_graph_kitty(ego: EgoGraph) -> Image:
    # NetworkX spring layout → matplotlib figure → PIL Image
    # Nodes: shape + color by type, labeled  (never color alone)
    # Edges: solid for outgoing, dashed for incoming, labeled with relation

def render_graph_canvas(ego: EgoGraph, canvas: Canvas):
    # textual-canvas Bresenham lines for edges
    # Half-block colored rounded boxes for nodes (shape varies by type)
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

## Interaction States

A TUI is a state machine, and most "it feels broken" bugs are unhandled states.
Specify these before writing widget code:

**Initial focus.** On mount, focus the node list (`self.query_one("#left-panel").focus()`)
and highlight the first item if one exists. An app that starts with nothing focused
silently eats every keypress — the most common "my bindings don't work" report.

**Binding priority vs Input focus — the j/k-vs-typing problem.** Textual routes a key
to the focused widget first; app-level `BINDINGS` see it only if nothing focused
consumed it. Two failure modes, one per wrong choice:

- If letter keys (`j`, `k`, `n`, `e`...) are plain app bindings, they work — until the
  search `Input` is focused, at which point the Input rightly consumes them as text.
  That is *correct*: while typing a query, `j` must insert "j", not move the cursor.
- If you "fix" navigation by marking letter bindings `Binding(..., priority=True)`,
  they now fire *while the user is typing in the Input* — typing "node" creates a new
  node. Never give priority to printable-character bindings.

The solution is focus discipline, not priority: keep letter bindings non-priority;
let the focused list handle j/k (or forward via `action_focus_next_node`); `escape`
in the search Input returns focus to the list; reserve `priority=True` for chords
that must work everywhere (`ctrl+s` to save in edit mode, `ctrl+g`).

**Per-panel empty / loading / error states.**

| Panel | Empty | Loading | Error |
|---|---|---|---|
| Node list | "No nodes — press n to create one" | populate in `on_mount`; show "Loading…" placeholder if you defer to a worker | DB unreadable → notify + empty list, never a traceback |
| Content | "Select a node" | n/a (reads are fast) | file missing on disk → "File not found: <path>" in the panel, app stays up |
| Detail | "Select a node" | n/a | node with zero edges shows "(no connections)", not a blank panel |

The empty-vault case is a tested deliverable (`test_tui_empty_vault_starts_without_crash`):
guard every `on_mount` query and `list[0]` access against zero nodes.

**Minimum terminal size: 100×28.** The three panels have CSS `min-width`s of
20 + 30 + 20 cells, plus borders, header, and footer — below roughly 100 columns by
28 rows the layout degrades into unusable slivers. Check `self.size` on mount and on
`Resize`, and overlay a "Terminal too small (need 100×28)" message rather than
rendering garbage. (`make study`'s side panes make this easy to hit — another reason
to run the app in its own window.)

**Delete confirmation.** `d` must never delete directly. Push a `ModalScreen[bool]`
("Delete '<title>'? y/n"), and only on a `True` dismissal remove the file, the DB row,
and the incoming edges. Escape or `n` cancels. The confirmation modal is a tested
deliverable, not a nicety.

**Dismiss exactly once.** Modal dismissal is a concurrency problem in disguise:
key events queue. Hold a key and auto-repeat queues a second close event behind
the first — or `escape` lands while `q` is still in flight when both close the
screen — and the duplicate arrives *after* the modal has already left the stack.
An unguarded second `dismiss()` (or `pop_screen()`) then pops the screen *below*
the modal, and the next pop crashes the app with `ScreenStackError`. Make every
exit path — keys, buttons, input-submit — route through one idempotent guard
(illustrative — adapt freely):

```python
class _DismissOnce:
    _finished = False

    def _finish(self, result=None) -> None:
        if self._finished:
            return  # duplicate event — the screen is already gone
        self._finished = True
        self.dismiss(result)
```

Every modal inherits the mixin and calls `self._finish(...)` wherever it would
have called `self.dismiss(...)`. The `d` confirmation, the `?` cheatsheet (its
any-key close is the easiest double-dismiss to trigger), and the graph screens
(two close keys) all need it — `test_modal_double_dismiss_is_safe` pins the
guard.

---

## Checkpoints — 5.1 / 5.2 / 5.3

12–20 hours is too long to fly without landmarks. Mirror the Phase 1A/1B precedent
and treat this phase as three internal checkpoints, each with its own green bar:

**Checkpoint 5.1 — List + detail panels (the current test suite).** App mounts with
the three-panel layout, node list populated from the DB, selection updates the
content/detail panels, `/` opens search, `q` quits, empty vault doesn't crash.
Certified by: `test_tui_app_starts_without_crash`, `test_tui_shows_node_titles`,
`test_tui_quit_on_q`, `test_tui_search_mode_on_slash`, `test_tui_node_count_matches_db`,
`test_tui_empty_vault_starts_without_crash`. (~4–6h)

**Checkpoint 5.2 — Edit + mutations + live updates.** Inline TextArea editing with
`Ctrl+S`, `n` creates, `d` deletes behind the ModalScreen confirmation, `?` shows the
help overlay, and the Phase 4 EventBus pipeline refreshes the list when a file changes
on disk. Certified by: the delete-confirmation, help-overlay, and double-dismiss tests, plus manual
verification of the live-update pipeline (edit a vault file in another terminal and
watch the list refresh). (~4–7h)

**Checkpoint 5.3 — Graph screen (baseline), then stretch.** `g` pushes
`EgoGraphScreen` rendering Phase 3's `render_ascii` output; `+`/`-` adjust depth;
`Esc` pops back. Stretch: the two-layer pixel/canvas renderer — a stretch goal,
not a deliverable; it needs `uv sync --extra graph` and a plain terminal window
(see the tmux warning above). No automated tests certify this checkpoint — it is
verified by use. (~4–7h, stretch open-ended)

Stop and commit at every checkpoint. A learner who finishes only 5.1 still has a
working, navigable knowledge-graph browser.

---

## Common Pitfalls

**Loading data in compose() instead of on_mount():** `compose()` runs before widgets exist — database queries here can cause errors. Always load data in `on_mount()`.

**Blocking the event loop:** Textual is async. Any blocking operation (slow DB query, file read) on the main thread freezes the UI. Use `asyncio.to_thread()` for heavy work.

**Forgetting to refresh after mutations:** After create/delete/update, call `load_node_list()` explicitly — Textual doesn't auto-refresh.

**Hardcoding widget IDs:** Use CSS selectors (`app.query_one("#node-list")`) with explicit IDs for testability with Pilot.

---

## Deliverable

The test suite is in `tests/phase_05/test_tui.py`, driven by Textual's headless
`Pilot`. Your app class must be importable as `akanga_tui.app.AkangaTUI` (or
`AkangaApp`) and accept `vault` and `db_path` constructor arguments.

**Checkpoint 5.1 tests (shipped):**

- `test_tui_app_starts_without_crash` — mounts, accepts `q`, exits cleanly
- `test_tui_shows_node_titles` — the db's node titles appear in the widget tree after mount
- `test_tui_quit_on_q` — `q` actually stops the app (`app.is_running` is False after)
- `test_tui_search_mode_on_slash` — `/` makes a visible `Input` widget appear
- `test_tui_node_count_matches_db` — one list item per node in the db (ListView/ListItem)
- `test_tui_empty_vault_starts_without_crash` — zero-node vault must not raise
  IndexError/KeyError/AttributeError

**Checkpoint 5.2 tests (new in this suite):**

- the delete-confirmation tests — `d` pushes a confirmation `ModalScreen`; the node is
  removed only after confirming, and escape cancels with nothing deleted
- the help-overlay test — `?` shows the keybinding cheatsheet overlay and any key
  dismisses it
- `test_modal_double_dismiss_is_safe` — closing the help modal twice (key
  auto-repeat / a queued duplicate close event) leaves the base screen intact;
  route every modal exit through the dismiss-once guard (§Interaction States)

**Verified manually (no shipped tests):** j/k navigation, search filtering of the
tree, the edit/save round-trip, and the live-update pipeline are part of the
deliverable but have no automated tests — certify them by hand: edit a vault file
in a second terminal and watch the list refresh; that is the full Phase 4 → Phase 5
pipeline in action. The graph screen (checkpoint 5.3) has no automated tests at all.

Plus 9 vault nodes with typed edges.

---

## Accessibility Note

**Encode node types with shape + color, never color alone.** In every place a node's
type is signaled — the list's type groups, the detail panel, and especially the graph
renderers — pair the color with a redundant channel: a distinct shape (circle/square/
diamond in the stretch renderer), a glyph prefix (`●` note, `▸` reference), or the
type name as text. Roughly 1 in 12 men cannot reliably distinguish the red/green
pairs that "obvious" palettes lean on, and a monochrome or low-color terminal strips
color entirely.

**TUIs and screen readers do not mix.** Textual paints a character grid, not an
accessibility tree — screen readers generally cannot navigate it. That is a real
limitation of this phase's artifact, not something to patch around in the TUI. The
programmatic alternative is Phase 6: the REST API exposes every operation the TUI
performs (list, read, search, create, delete) as plain JSON over HTTP, which is
scriptable and assistive-technology-friendly. If accessibility is a requirement for
your context, treat the Phase 6 API as the primary interface and this TUI as one
client of it.

---

## Reflect

> **Solo:** Sketch the full event flow when a user saves a file in an external editor while the TUI is open: file change → watcher → EventBus → TUI refresh. Which components are running in which threads?

> **Group:** Compare the TUI's approach (single process, direct DB access) with a web app approach (browser + HTTP API). What does each gain? What does each give up?
