#!/usr/bin/env bash
# study [PHASE_NUMBER]
#
# Opens the Akanga study environment as a three-pane tmux layout:
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
#   AKANGA_CODE  → path to your code directory (default: ~/code/akanga_mirin)
#   AKANGA_DOCS  → path to the docs/ directory  (default: ~/code/akanga_mirin/docs)

# Exit immediately on any error, treat unset variables as errors,
# and propagate pipe failures (so a failing `find | head` doesn't silently pass).
set -euo pipefail

# ── 0. Dependency preflight ───────────────────────────────────────────────────
# The study layout needs tmux + nvim + glow; claude is optional (warn only).
MISSING=0
for cmd in tmux nvim glow; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        case "$cmd" in
            tmux) HINT="brew install tmux        (Debian/Ubuntu: apt install tmux)" ;;
            nvim) HINT="brew install neovim      (Debian/Ubuntu: apt install neovim)" ;;
            glow) HINT="brew install glow        (or: go install github.com/charmbracelet/glow@latest)" ;;
        esac
        echo "error: '$cmd' not found — required for the study session." >&2
        echo "       install: $HINT" >&2
        MISSING=1
    fi
done
if [[ "$MISSING" -eq 1 ]]; then
    exit 1
fi
if ! command -v claude >/dev/null 2>&1; then
    echo "warning: 'claude' (Claude Code CLI) not found — the bottom-right pane will open but the command will fail." >&2
    echo "         install: npm install -g @anthropic-ai/claude-code  (https://claude.com/claude-code)" >&2
fi

# ── 1. Normalise the phase number ─────────────────────────────────────────────
# Accept bare digits (0, 3, 08) and zero-pad to two digits (00, 03, 08).
# Phase 1 is split into 1A/1B: accept "1a"/"1b" (case-insensitive) as a suffix.
# Convention also implemented in scripts/_common.py:normalize_phase — keep in step.
# 10#$PHASE forces base-10 so "08" isn't treated as invalid octal.
PHASE="${1:-00}"
SUB=""
if [[ "$PHASE" =~ ^([0-9]+)([aAbB])$ ]]; then
    SUB=$(printf '%s' "${BASH_REMATCH[2]}" | tr '[:upper:]' '[:lower:]')
    PHASE="${BASH_REMATCH[1]}"
fi
PADDED=$(printf "%02d" "$((10#$PHASE))")
if [[ "$PADDED" == "01" && -z "$SUB" ]]; then
    echo "note: Phase 1 is split into 1A and 1B — opening 1A. Use 'PHASE=1b' for 1B."
    SUB="a"
fi

# ── 2. Resolve paths ──────────────────────────────────────────────────────────
# Allow overrides via env vars so the script works outside the default layout.
AKANGA_DOCS="${AKANGA_DOCS:-$HOME/code/akanga_mirin/docs}"
CODE_DIR="${AKANGA_CODE:-$HOME/code/akanga_mirin}"

# tmux session name (used when launching from outside an existing tmux session)
# and window name (the tab label visible in the status bar).
SESSION="akanga-study"
WINDOW="phase-${PADDED}${SUB}"

# ── 3. Locate the phase learning document ────────────────────────────────────
# Files are named phase-NN-<slug>.md (or phase-NNa-/phase-NNb- for split phases);
# glob on the NN prefix + optional sub-phase letter. head -1 picks the first match.
PHASE_DOC=$(find "$AKANGA_DOCS/learning" -name "phase-${PADDED}${SUB}-*.md" 2>/dev/null | sort | head -1)
if [[ -z "$PHASE_DOC" ]]; then
    echo "error: no phase doc found for phase ${PADDED} in $AKANGA_DOCS/learning"
    exit 1
fi

echo "▶ Phase ${PADDED}: $(basename "$PHASE_DOC")"
echo "  code → $CODE_DIR"
echo "  docs → $PHASE_DOC"

# ── 4. Ensure the code directory exists ───────────────────────────────────────
mkdir -p "$CODE_DIR"

# ── 5. Create the tmux window and capture the first pane's ID ─────────────────
# We track panes by their unique ID (%N, e.g. %5) rather than by
# "session:window.pane_index". IDs are globally unique within the tmux server,
# so they survive window renames, reordering, and nested sessions without
# ambiguity — the root cause of the earlier "can't find pane: 0" errors.
#
# Two cases:
#   a) Already inside tmux → open a new named window in the current session.
#      -P -F "#{pane_id}" makes new-window print the ID of the pane it just
#      created, which we capture into PANE_LEFT.
#   b) Outside tmux → create a dedicated session in the background (-d),
#      then query its first pane ID via display-message.
if [[ -n "${TMUX:-}" ]]; then
    PANE_LEFT=$(tmux new-window -n "$WINDOW" -P -F "#{pane_id}")
else
    tmux kill-session -t "$SESSION" 2>/dev/null || true   # remove stale session
    tmux new-session -d -s "$SESSION" -n "$WINDOW"
    PANE_LEFT=$(tmux display-message -t "${SESSION}:${WINDOW}" -p "#{pane_id}")
fi

# ── 6. Left pane (66%) — neovim ───────────────────────────────────────────────
# send-keys targets the pane by ID, cds into the code directory, and opens
# neovim in directory mode so the file tree is immediately visible.
tmux send-keys -t "$PANE_LEFT" "cd '$CODE_DIR' && nvim ." Enter

# ── 7. Right column — split the left pane horizontally at 34% ────────────────
# -h  = horizontal split (left | right)
# -p 34 = right pane gets 34% of total width
# -P -F "#{pane_id}" = print the new pane's ID so we can reference it later
PANE_RIGHT=$(tmux split-window -t "$PANE_LEFT" -h -p 34 -P -F "#{pane_id}")

# ── 8. Top-right pane — phase doc via glow ────────────────────────────────────
# glow -p renders the Markdown with a pager (like less) so you can scroll
# through the full phase learning document without it wrapping off-screen.
tmux send-keys -t "$PANE_RIGHT" "glow -p '$PHASE_DOC'" Enter

# ── 9. Bottom-right pane — Claude Code in tutor mode ─────────────────────────
# Split the top-right pane vertically 50/50 to create the bottom-right slot.
# -v = vertical split (top / bottom), -p 50 = equal halves
# Claude launches with the /tutor command (.claude/commands/tutor.md) so the
# session knows the current phase and follows the learning-assistant brief
# (doc routing, anti-spoiler rules) instead of the contributor CLAUDE.md focus.
PANE_BOTTOM=$(tmux split-window -t "$PANE_RIGHT" -v -p 50 -P -F "#{pane_id}")
tmux send-keys -t "$PANE_BOTTOM" "cd '$CODE_DIR' && claude '/tutor ${PADDED}${SUB}'" Enter

# ── 10. Return focus to the editor ────────────────────────────────────────────
# After all the splits the active pane is PANE_BOTTOM. Move focus back to
# neovim so the learner can start coding immediately.
tmux select-pane -t "$PANE_LEFT"

# ── 11. Attach (only needed when we created a new session outside tmux) ───────
# If we were already inside tmux the new window is already visible; no attach needed.
if [[ -z "${TMUX:-}" ]]; then
    tmux attach-session -t "$SESSION"
fi
