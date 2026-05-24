#!/usr/bin/env bash
# study [PHASE_NUMBER]
#
# Opens the Akanga study environment:
#
#   ┌──────────────────────┬────────────────┐
#   │                      │  glow docs     │
#   │   neovim (code)      │  (phase doc)   │
#   │      66%             ├────────────────┤
#   │                      │  claude code   │
#   └──────────────────────┴────────────────┘
#
# Usage:
#   study        → opens phase 00 (default)
#   study 3      → opens phase 03
#   study 08     → opens phase 08
#
# Environment variables:
#   AKANGA_CODE  → path to your code directory (default: ~/code/akanga)
#   AKANGA_DOCS  → path to akanga_mirin repo  (default: ~/code/akanga_mirin)

set -euo pipefail

PHASE="${1:-00}"
PADDED=$(printf "%02d" "$((10#$PHASE))")   # normalise: 3 → 03, 08 → 08

AKANGA_DOCS="${AKANGA_DOCS:-$HOME/code/akanga_mirin/docs}"
CODE_DIR="${AKANGA_CODE:-$HOME/code/akanga_mirin}"
SESSION="akanga-study"
WINDOW="phase-${PADDED}"

# ── Locate the phase document ─────────────────────────────────────────────────
PHASE_DOC=$(find "$AKANGA_DOCS/learning" -name "phase-${PADDED}-*.md" 2>/dev/null | head -1)
if [[ -z "$PHASE_DOC" ]]; then
    echo "error: no phase doc found for phase ${PADDED} in $AKANGA_DOCS/docs/learning"
    exit 1
fi

echo "▶ Phase ${PADDED}: $(basename "$PHASE_DOC")"
echo "  code → $CODE_DIR"
echo "  docs → $PHASE_DOC"

# ── Ensure the code directory exists ─────────────────────────────────────────
mkdir -p "$CODE_DIR"

# ── Build tmux layout ─────────────────────────────────────────────────────────
# If already inside tmux: open a new window.
# If outside tmux: create a new session and attach at the end.
if [[ -n "${TMUX:-}" ]]; then
    tmux new-window -n "$WINDOW"
    TARGET="$(tmux display-message -p '#S'):$WINDOW"
else
    # Kill stale session with the same name if it exists
    tmux kill-session -t "$SESSION" 2>/dev/null || true
    tmux new-session -d -s "$SESSION" -n "$WINDOW"
    TARGET="${SESSION}:${WINDOW}"
fi

# Pane 0 — left 66% — neovim
tmux send-keys -t "${TARGET}.0" "cd '$CODE_DIR' && nvim ." Enter

# Split right, 34% of total width
tmux split-window -t "${TARGET}.0" -h -p 34

# Pane 1 — top-right — phase doc via glow
tmux send-keys -t "${TARGET}.1" "glow -p '$PHASE_DOC'" Enter

# Split pane 1 vertically, 50/50
tmux split-window -t "${TARGET}.1" -v -p 50

# Pane 2 — bottom-right — Claude Code
tmux send-keys -t "${TARGET}.2" "cd '$CODE_DIR' && claude" Enter

# Return focus to neovim
tmux select-pane -t "${TARGET}.0"

# Attach if we created the session from outside tmux
if [[ -z "${TMUX:-}" ]]; then
    tmux attach-session -t "$SESSION"
fi
