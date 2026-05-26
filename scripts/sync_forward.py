#!/usr/bin/env python3
"""
sync_forward.py — propagate a bug fix from phase N to all later phases.

Usage:
    python scripts/sync_forward.py src/akanga_core/parser.py 2
    python scripts/sync_forward.py src/akanga_core/parser.py 2 --apply

This script diffs the source file (from phase N) against the same file in 
all later phases and optionally applies the source version to them.
"""

from __future__ import annotations

import argparse
import difflib
import sys
from pathlib import Path


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

        target_lines = target_file.read_text(encoding="utf-8").splitlines(keepends=True)
        
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
        print("\nRun with --apply to apply these changes.")
    elif not any_diff:
        print("All phases already in sync.")


if __name__ == "__main__":
    main()
