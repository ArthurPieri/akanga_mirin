# Terminal and tmux Basics

**Audience:** developers new to the terminal or to tmux as a daily driver · **Read time:** ~12 min

A practical reference for working in the terminal — the primary environment for
developing and running akanga.

---

## Why the terminal matters for local-first tools

Akanga is deliberately local-first: no cloud services, no web dashboard required.
The terminal is where you start the server, watch logs, run tests, and inspect the
vault. Understanding the shell is not optional — it is the interface.

Modern terminal workflows also let you run multiple programs simultaneously in a
single window with no context-switching overhead. That is where tmux comes in.

---

## Basic navigation

### pwd — print working directory

Shows where you are in the filesystem. When something doesn't work, check this
first.

```bash
pwd
# /Users/yourname/code/akanga_mirin
```

### ls — list directory contents

```bash
ls               # list current directory
ls -la           # long format, show hidden files (the -a flag)
ls src/          # list a specific path
```

### cd — change directory

```bash
cd /Users/yourname/code/akanga_mirin   # absolute path
cd src/akanga_core                     # relative path (your implementation)
cd ..                             # go up one level
cd ~                              # go to home directory
cd -                              # go back to previous directory
```

### cat — print a file

```bash
cat src/akanga_core/gitmgr.py
```

For long files, pipe through a pager:

```bash
cat src/akanga_core/server.py | less
# navigate with arrow keys, q to quit
```

### grep — search inside files

```bash
grep "def commit" src/akanga_core/gitmgr.py        # find a function
grep -r "eventbus" src/                             # recursive search
grep -rn "HTTPException" src/akanga_core/           # show line numbers
grep -r "def " src/akanga_core/ | grep "node"       # pipe grep into grep
```

### find — locate files

```bash
find . -name "*.md"                        # all markdown files
find . -name "*.py" -path "*/tests/*"      # Python files in tests/
find . -name "__pycache__" -type d         # find cache dirs
find . -name "*.db"                        # find database files
```

---

## Environment variables

Environment variables are key-value pairs available to any process. They pass
configuration without hardcoding it.

### Setting and reading variables

```bash
export AKANGA_SRC=./src
echo $AKANGA_SRC
# ./src
```

The `export` command makes the variable available to child processes (subprocesses
you launch from this shell). Without `export`, the variable is only visible in the
current shell.

### Using variables

```bash
PYTHONPATH=$AKANGA_SRC pytest tests/
cd $AKANGA_SRC/akanga_core
```

### Checking what is set

```bash
env                         # print all environment variables
env | grep AKANGA           # filter to akanga-related ones
printenv AKANGA_SRC         # print one variable
```

### Shell session vs subprocess

A key distinction:

- **Shell session** — the interactive terminal you're typing in. Variables you
  `export` here are available in this session and any subprocesses it spawns.
- **Subprocess** — a command your shell runs (e.g., `pytest`, `python`). It
  *inherits* the parent shell's exported variables. If you set a variable without
  `export`, the subprocess won't see it.

```bash
# This works: PYTHONPATH is set in the subprocess's environment
PYTHONPATH=src pytest tests/

# This also works: exported before running pytest
export PYTHONPATH=src
pytest tests/

# This does NOT work: no-export means pytest won't inherit it
PYTHONPATH=src   # sets it in shell only
pytest tests/    # subprocess gets no PYTHONPATH
```

The `AKANGA_SRC` variable is how the test harness finds *your* code: running
`AKANGA_SRC=./src make test PHASE=2` points pytest at your implementation in
`./src`. Without it, tests fall back to the reference solutions. (The study
session uses different variables — `AKANGA_CODE` and `AKANGA_DOCS` — see below.)

---

## tmux

tmux is a terminal multiplexer: it lets you run multiple terminal sessions inside
a single terminal window, keep sessions alive when you disconnect, and arrange
panes side by side.

### Core concepts

- **Session** — a named workspace. Multiple windows, persists when you detach.
- **Window** — a full-screen tab inside a session. Has one or more panes.
- **Pane** — a subdivided region of a window. Each pane runs an independent shell.

```
Session: akanga-study
  └── Window 0: study
        ├── Pane 0 (left 66%): neovim
        ├── Pane 1 (top right): glow (renders the doc)
        └── Pane 2 (bottom right): claude
```

### Essential key bindings

All tmux commands start with the **prefix key**: `Ctrl+b` (hold Ctrl, press b,
release both, then press the command key).

| Binding | Action |
|---------|--------|
| `Ctrl+b %` | Split pane vertically (left / right) |
| `Ctrl+b "` | Split pane horizontally (top / bottom) |
| `Ctrl+b arrow` | Move focus to the pane in that direction |
| `Ctrl+b d` | Detach from the session (leaves it running) |
| `Ctrl+b z` | Zoom current pane to full screen (toggle) |
| `Ctrl+b [` | Enter scroll / copy mode (arrows to scroll, q to exit) |
| `Ctrl+b x` | Close current pane (prompts for confirmation) |
| `Ctrl+b c` | Create a new window |
| `Ctrl+b n` | Next window |
| `Ctrl+b p` | Previous window |
| `Ctrl+b s` | List sessions (interactive picker) |
| `Ctrl+b $` | Rename current session |

### Starting and attaching

```bash
# Start a new named session
tmux new-session -s akanga-study

# Detach (inside tmux)
# Ctrl+b d

# List running sessions
tmux ls

# Attach to a session by name
tmux attach-session -t akanga-study

# Attach to the most recent session
tmux attach
```

### Resizing panes

Hold `Ctrl+b` then hold an arrow key to resize incrementally. Or use the mouse if
your tmux config has `set -g mouse on`.

```bash
# In tmux.conf to enable mouse support:
set -g mouse on
```

### Killing a session

```bash
# From inside the session
tmux kill-session

# From outside
tmux kill-session -t akanga-study
```

---

## The akanga study layout

The `make study PHASE=N` command opens a three-pane tmux window optimized for
the learning path:

```
┌─────────────────────────────┬───────────────────┐
│                             │  glow (doc)        │
│  neovim (source code)       │                    │
│  66% width                  ├───────────────────┤
│                             │  claude (AI help)  │
└─────────────────────────────┴───────────────────┘
```

- **Left pane (66%)** — neovim opened in your code directory (`nvim .`).
- **Top right** — `glow -p` rendering the phase's learning doc in a pager.
- **Bottom right** — Claude Code launched in your code directory.

The layout is created by `scripts/study.sh`. What it actually does:

- **Session and window names** — the session is always `akanga-study`; each phase
  gets a *window* named `phase-NN` (zero-padded), or `phase-01a` / `phase-01b`
  for the split Phase 1. If you are already inside tmux, the script opens a new
  window in your current session instead of creating `akanga-study`.
- **Phase argument** — `study 3`, `study 08`, and `study 1b` all work. Bare
  `study 1` defaults to Phase 1A with a note.
- **Configuration via two environment variables** (both optional, with defaults):

```bash
AKANGA_CODE   # path to your code directory   (default: ~/code/akanga_mirin)
AKANGA_DOCS   # path to the docs/ directory   (default: ~/code/akanga_mirin/docs)
```

- **Preflight** — the script exits with install hints if `tmux`, `nvim`, or
  `glow` is missing, and warns (but continues) if `claude` is not installed.
- **Doc lookup** — it globs `$AKANGA_DOCS/learning/phase-NN*-*.md` to find the
  phase doc and errors out if none exists.

No environment variables are *required* — the defaults match the standard
repository layout. (`AKANGA_SRC` plays no role in the study session; it is only
used by `make test` to locate your implementation.)

> **Kitty graphics inside tmux**
>
> Phase 5 explores terminals that can render pixel graphics (Ghostty, Kitty,
> WezTerm) via the Kitty graphics protocol. tmux sits between your program and
> the terminal and **swallows those escape sequences by default**, so images
> render as garbage or not at all inside the study session. If you want
> graphics inside tmux you need tmux **3.3 or newer** with passthrough enabled
> in `~/.tmux.conf`:
>
> ```
> set -g allow-passthrough on
> ```
>
> Even then, support is partial (no damage tracking; images can ghost over
> pane splits). For the Phase 5 graph-rendering work, the simplest reliable
> setup is a plain Ghostty or Kitty window *outside* tmux — keep the tmux study
> session for editing and tests, and run the graphics experiments in a separate
> terminal window.

---

## Practical workflow for a study session

1. Launch the study layout:

```bash
cd /Users/yourname/code/akanga_mirin
make study PHASE=3
```

2. In the left pane (neovim), write your implementation. In the top right, the
   phase doc is rendered. Use the bottom right for Claude Code or for running
   tests:

```bash
AKANGA_SRC=./src make test PHASE=3
```

3. When done, detach (`Ctrl+b d`) — the session keeps running. Reattach later:

```bash
tmux attach-session -t akanga-study
```

   Inside the session, each phase you've opened is its own window
   (`phase-03`, `phase-01a`, ...) — switch with `Ctrl+b n` / `Ctrl+b p`.

4. When truly done, kill the session:

```bash
tmux kill-session -t akanga-study
```

---

## In this repository

- `scripts/study.sh` — creates the three-pane tmux layout described above
  (session `akanga-study`, one window per phase).
- `Makefile` — the `study` target calls `scripts/study.sh` with the phase number.
- `AKANGA_CODE` / `AKANGA_DOCS` — optional overrides for where study.sh finds
  your code and the docs; the defaults match the standard layout.
- `AKANGA_SRC` — used by `make test` only: point it at your implementation
  (`AKANGA_SRC=./src`) so pytest tests your code instead of the reference solutions.
- All `make` commands use `uv run python` to ensure the virtualenv is picked up;
  see `Makefile` for the full list of targets.
