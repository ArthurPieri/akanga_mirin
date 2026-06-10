#!/usr/bin/env python3
"""
sync_forward.py — propagate a bug fix from phase N to all later phases.

Usage:
    python scripts/sync_forward.py src/akanga_core/parser.py 2
    python scripts/sync_forward.py src/akanga_core/parser.py 2 --apply

This script diffs the source file (from phase N) against the same file in
all later phases and optionally applies the source version to them.

Exit codes:
    0  all phases in sync, or --apply was given and changes were applied
    1  drift found and --apply NOT given (lets CI gate on drift), or error

Marker files (later-phase placeholders saying "Copy your Phase NN solution
here" / "intentionally left as a reference marker") are never overwritten.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path

# Later-phase skeletons ship 3-line placeholder files that intentionally do NOT
# contain an implementation. Overwriting them with a prior phase's full file —
# or treating them as drift to "fix" — would defeat their purpose.
MARKER_SNIPPETS = (
    "intentionally left as a reference marker",
    "Copy your Phase",
)


def is_marker_file(content: str) -> bool:
    return any(snippet in content for snippet in MARKER_SNIPPETS)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", metavar="FILE", help="Relative file path within a phase directory")
    parser.add_argument("from_phase", metavar="FROM", type=int, help="Phase number where the fix was applied")
    parser.add_argument("--apply", action="store_true", help="Apply the source file to all later phases")
    parser.add_argument("--to", metavar="N", type=int, default=9, help="Stop at this phase (default: 9)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    
    # We try both skeletons and solutions as base directories
    source_phase_dir = f"phase_{args.from_phase:02d}"
    
    source_file = None
    base_dir = None
    
    for candidate_base in ["solutions", "skeletons"]:
        candidate_path = repo_root / candidate_base / source_phase_dir / args.file
        if candidate_path.exists():
            source_file = candidate_path
            base_dir = repo_root / candidate_base
            break
            
    if not source_file:
        print(f"error: source file not found in solutions/ or skeletons/: {args.file} (Phase {args.from_phase})", file=sys.stderr)
        sys.exit(1)

    source_content = source_file.read_text(encoding="utf-8")
    if is_marker_file(source_content):
        print(
            f"error: source file {source_file} is a marker placeholder, not an "
            "implementation — refusing to propagate it.",
            file=sys.stderr,
        )
        sys.exit(1)
    source_lines = source_content.splitlines(keepends=True)
    
    print(f"Source: {source_file}")
    print(f"Propagating to phases {args.from_phase + 1}–{args.to} in {base_dir.name}/\n")

    any_diff = False
    for n in range(args.from_phase + 1, args.to + 1):
        target_phase_dir = f"phase_{n:02d}"
        target_file = base_dir / target_phase_dir / args.file

        if not target_file.exists():
            # If it's not in the same base_dir, maybe it's in the other one?
            # But usually we sync within the same tree (solutions -> solutions or skeletons -> skeletons)
            continue

        target_content = target_file.read_text(encoding="utf-8")
        if is_marker_file(target_content):
            print(f"  {target_phase_dir}: marker file — skipped (intentional placeholder, never overwritten)")
            continue
        target_lines = target_content.splitlines(keepends=True)

        diff = list(difflib.unified_diff(
            target_lines,
            source_lines,
            fromfile=f"{base_dir.name}/{target_phase_dir}/{args.file} (current)",
            tofile=f"{base_dir.name}/{source_phase_dir}/{args.file} (fixed source)",
        ))

        if not diff:
            print(f"  {target_phase_dir}: already in sync ✓")
            continue

        any_diff = True
        print(f"  {target_phase_dir}: {len(diff)} diff lines")
        for line in diff:
            print("    " + line, end="")
        print()

        if args.apply:
            target_file.write_text(source_content, encoding="utf-8")
            print(f"  → Applied fixed source to {target_file}")

    if not args.apply and any_diff:
        print("\nDrift found. Run with --apply to apply these changes.")
        sys.exit(1)  # non-zero so CI can gate on unsynced fixes
    elif not any_diff:
        print("All phases already in sync.")


if __name__ == "__main__":
    main()
