#!/usr/bin/env python3
"""
sync_forward.py — propagate a bug fix from phase N to all later phases.

Usage:
    uv run python scripts/sync_forward.py src/akanga_core/parser.py 2
    uv run python scripts/sync_forward.py src/akanga_core/parser.py 2 --apply

The serial solutions pattern (solutions/phase_NN/ accumulates all prior phases)
means a bug in phase 2's parser.py must be patched in phases 3 through 9.
This script diffs the fixed file against each later phase and optionally applies.

Arguments:
    FILE    Path relative to solutions/phase_NN/  (e.g. src/akanga_core/parser.py)
    FROM    Phase number where the fix was applied (e.g. 2)

Options:
    --apply     Apply the diff to all later phases (default: preview only)
    --to N      Stop at phase N (default: 9)
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("file", metavar="FILE", help="Relative file path within solutions/phase_NN/")
    parser.add_argument("from_phase", metavar="FROM", type=int, help="Phase number of the fixed version")
    parser.add_argument("--apply", action="store_true", help="Apply diffs (default: preview only)")
    parser.add_argument("--to", metavar="N", type=int, default=9, help="Stop at this phase (default: 9)")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent
    solutions_dir = repo_root / "solutions"

    source_phase = f"phase_{args.from_phase:02d}"
    source_file = solutions_dir / source_phase / args.file

    if not source_file.exists():
        print(f"error: source file not found: {source_file}", file=sys.stderr)
        sys.exit(1)

    source_lines = source_file.read_text(encoding="utf-8").splitlines(keepends=True)
    print(f"Source: {source_file}")
    print(f"Propagating to phases {args.from_phase + 1}–{args.to}\n")

    any_diff = False
    for n in range(args.from_phase + 1, args.to + 1):
        target_phase = f"phase_{n:02d}"
        target_file = solutions_dir / target_phase / args.file

        if not target_file.exists():
            print(f"  phase_{n:02d}: {args.file} does not exist — skipping")
            continue

        target_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
        diff = list(difflib.unified_diff(
            target_lines,
            source_lines,
            fromfile=f"solutions/{target_phase}/{args.file}",
            tofile=f"solutions/{source_phase}/{args.file} (fixed)",
        ))

        if not diff:
            print(f"  phase_{n:02d}: already in sync ✓")
            continue

        any_diff = True
        print(f"  phase_{n:02d}: {len(diff)} diff lines")
        for line in diff:
            print("    " + line, end="")
        print()

        if args.apply:
            target_file.write_text(source_file.read_text(encoding="utf-8"), encoding="utf-8")
            print(f"  → Applied to {target_file}")

    if not args.apply and any_diff:
        print("\nRun with --apply to apply these changes.")
    elif not any_diff:
        print("All phases already in sync.")


if __name__ == "__main__":
    main()
