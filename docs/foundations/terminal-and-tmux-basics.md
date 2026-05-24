# Terminal and tmux Basics

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
cd /Users/yourname/code/noteapp   # absolute path
cd src/akanga_core                # relative path
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
export AKANGA_SRC=/Users/yourname/code/noteapp/src
echo $AKANGA_SRC
# /Users/yourname/code/noteapp/src
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

The `AKANGA_SRC` variable is critical: test files that import `akanga_core`
need `PYTHONPATH` pointing at the `src/` directory, or Python can't find the
package.

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

- **Left pane (66%)** — neovim opened to the relevant source file for the phase.
- **Top right** — `glow` rendering the phase's Markdown documentation.
- **Bottom right** — a shell ready for you to run `claude` or any command.

The layout is created by `scripts/study.sh`:

```bash
#!/usr/bin/env bash
PHASE=${1:-1}
SESSION="akanga-phase-${PHASE}"

# Create or attach to session
tmux new-session -d -s "$SESSION" -x 220 -y 50

# Open neovim in left pane (66% width)
tmux send-keys -t "$SESSION" "nvim $AKANGA_SRC/akanga_core/..." Enter

# Split right: top pane for glow, bottom for claude
tmux split-window -h -l 34% -t "$SESSION"
tmux send-keys -t "$SESSION" "glow docs/learning/phase-${PHASE}.md" Enter

tmux split-window -v -t "$SESSION"
# bottom-right pane is ready for commands

tmux attach-session -t "$SESSION"
```

The `AKANGA_SRC` environment variable must be set before running `make study` or
the paths will be wrong. Add it to your shell profile (`~/.zshrc` or `~/.bashrc`):

```bash
export AKANGA_SRC=/Users/yourname/code/noteapp/src
```

---

## Practical workflow for a study session

1. Open a terminal and verify your environment:

```bash
echo $AKANGA_SRC
# should print the path to noteapp/src
```

2. Launch the study layout:

```bash
cd /Users/yourname/code/akanga_mirin
make study PHASE=3
```

3. In the left pane (neovim), read the source. In the top right, the phase doc is
   rendered. Use the bottom right for running tests:

```bash
PYTHONPATH=$AKANGA_SRC pytest tests/test_server.py -v
```

4. When done, detach (`Ctrl+b d`) — the session keeps running. Reattach later:

```bash
tmux attach-session -t akanga-phase-3
```

5. When truly done, kill the session:

```bash
tmux kill-session -t akanga-phase-3
```

---

## In this codebase

- `scripts/study.sh` — creates the three-pane tmux layout described above.
- `Makefile` — the `study` target calls `scripts/study.sh` with the phase number.
- `AKANGA_SRC` — must point to `noteapp/src/` for imports to resolve in tests.
- All `make` commands use `uv run python` to ensure the virtualenv is picked up;
  see `Makefile` for the full list of targets.
