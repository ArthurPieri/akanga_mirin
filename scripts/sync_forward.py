#!/usr/bin/env python3
"""
sync_forward.py — keep cross-phase module copies converged.

Two modes:

1. Propagate mode — diff a file from its source phase against all later phases
   in ONE explicit tree (no silent solutions/skeletons precedence) and
   optionally overwrite them:

       python scripts/sync_forward.py --base solutions src/akanga_core/parser.py 2
       python scripts/sync_forward.py --base solutions src/akanga_core/parser.py 2 --apply

2. Audit mode — read scripts/sync_manifest.toml (the canonical-source map from
   adversarial-analysis-v3.md #7) and verify every should-be-identical pair is
   byte-identical. This is the CI convergence gate:

       python scripts/sync_forward.py --check-all

Exit codes:
    0  everything in sync (or --apply was given and changes were applied)
    1  drift found
    2  usage error (bad arguments, missing files, unreadable manifest)

Marker files (later-phase skeleton placeholders saying "Copy your Phase NN
solution here" / "intentionally left as a reference marker") are never
overwritten and never counted as drift.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = REPO_ROOT / "scripts" / "sync_manifest.toml"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2

# Later-phase skeletons ship 3-line placeholder files that intentionally do NOT
# contain an implementation. Overwriting them with a prior phase's full file —
# or treating them as drift to "fix" — would defeat their purpose.
MARKER_SNIPPETS = (
    "intentionally left as a reference marker",
    "Copy your Phase",
)


def is_marker_file(content: str) -> bool:
    return any(snippet in content for snippet in MARKER_SNIPPETS)


def usage_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(EXIT_USAGE)


def load_manifest() -> list[dict]:
    if not MANIFEST_PATH.exists():
        usage_error(f"manifest not found: {MANIFEST_PATH}")
    try:
        data = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        usage_error(f"manifest is not valid TOML: {exc}")
    modules = data.get("modules", [])
    if not modules:
        usage_error("manifest contains no [[modules]] entries")
    return modules


def check_all(base: str) -> int:
    """Verify byte-identity of every should-be-identical pair in the manifest.

    Returns the number of drifting files. Missing files in the solutions tree
    count as drift; missing or marker files in the skeletons tree are skipped
    (skeletons legitimately re-ship only a subset, via markers or omission).
    """
    modules = load_manifest()
    base_dir = REPO_ROOT / base
    if not base_dir.is_dir():
        usage_error(f"base directory not found: {base_dir}")

    drift = 0
    checked = 0
    print(f"Convergence audit: {base}/ against scripts/sync_manifest.toml\n")

    for mod in modules:
        rel = mod["file"]
        intro = mod["introduced_in"]
        canonical = base_dir / f"phase_{intro:02d}" / rel
        canonical_label = canonical.relative_to(REPO_ROOT)

        if not canonical.exists():
            if base == "skeletons":
                continue  # skeletons may not ship this module at all
            print(f"  DRIFT  canonical source missing: {canonical_label}")
            drift += 1
            continue

        canonical_bytes = canonical.read_bytes()
        if is_marker_file(canonical_bytes.decode("utf-8", errors="replace")):
            continue  # a marker canonical means nothing to converge in this tree

        for phase in mod["applies_to"]:
            if phase == intro:
                continue
            target = base_dir / f"phase_{phase:02d}" / rel
            target_label = f"{base}/phase_{phase:02d}/{rel}"

            if not target.exists():
                if base == "skeletons":
                    continue
                print(f"  DRIFT  {target_label}: missing — expected a copy of {canonical_label}")
                drift += 1
                continue

            target_bytes = target.read_bytes()
            if is_marker_file(target_bytes.decode("utf-8", errors="replace")):
                continue  # intentional placeholder, never compared

            checked += 1
            if target_bytes != canonical_bytes:
                n_lines = len(
                    list(
                        difflib.unified_diff(
                            target_bytes.decode("utf-8", errors="replace").splitlines(),
                            canonical_bytes.decode("utf-8", errors="replace").splitlines(),
                        )
                    )
                )
                print(
                    f"  DRIFT  {target_label}: differs from canonical "
                    f"{canonical_label} ({n_lines} diff lines)"
                )
                drift += 1

    print(f"\n{checked} pair(s) compared, {drift} drifting.")
    if drift:
        print(
            "Fix: converge each file onto its canonical (introduction-phase) version, e.g.\n"
            f"  python scripts/sync_forward.py --base {base} <FILE> <INTRO_PHASE> --apply"
        )
    else:
        print("All manifest pairs are byte-identical — trees are converged.")
    return drift


def propagate(base: str, rel_file: str, from_phase: int, to_phase: int, apply: bool) -> int:
    """Diff (and optionally apply) one file from its source phase forward.

    Returns the number of drifting target files (before any --apply rewrite).
    """
    base_dir = REPO_ROOT / base
    source_file = base_dir / f"phase_{from_phase:02d}" / rel_file
    if not source_file.exists():
        usage_error(f"source file not found: {source_file}")

    source_content = source_file.read_text(encoding="utf-8")
    if is_marker_file(source_content):
        usage_error(
            f"source file {source_file} is a marker placeholder, not an "
            "implementation — refusing to propagate it."
        )
    source_lines = source_content.splitlines(keepends=True)

    print(f"Source: {source_file.relative_to(REPO_ROOT)}")
    print(f"Propagating to phases {from_phase + 1}-{to_phase} in {base}/\n")

    drift = 0
    for n in range(from_phase + 1, to_phase + 1):
        target_file = base_dir / f"phase_{n:02d}" / rel_file
        target_label = f"phase_{n:02d}"

        if not target_file.exists():
            continue

        target_content = target_file.read_text(encoding="utf-8")
        if is_marker_file(target_content):
            print(f"  {target_label}: marker file — skipped (intentional placeholder)")
            continue

        diff = list(
            difflib.unified_diff(
                target_content.splitlines(keepends=True),
                source_lines,
                fromfile=f"{base}/{target_label}/{rel_file} (current)",
                tofile=f"{base}/phase_{from_phase:02d}/{rel_file} (canonical source)",
            )
        )

        if not diff:
            print(f"  {target_label}: already in sync ✓")
            continue

        drift += 1
        print(f"  {target_label}: {len(diff)} diff lines")
        for line in diff:
            print("    " + line, end="")
        print()

        if apply:
            target_file.write_text(source_content, encoding="utf-8")
            print(f"  → Applied canonical source to {target_file.relative_to(REPO_ROOT)}")

    return drift


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--base",
        choices=("solutions", "skeletons"),
        help="Tree to operate on (REQUIRED in propagate mode — no silent precedence)",
    )
    parser.add_argument(
        "--check-all",
        action="store_true",
        help="Audit every manifest pair for byte-identity (default base: solutions)",
    )
    parser.add_argument(
        "file", metavar="FILE", nargs="?", help="Relative file path within a phase directory"
    )
    parser.add_argument(
        "from_phase",
        metavar="FROM",
        nargs="?",
        type=int,
        help="Phase number where the fix was applied",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Apply the source file to all later phases"
    )
    parser.add_argument(
        "--to", metavar="N", type=int, default=8, help="Stop at this phase (default: 8)"
    )
    args = parser.parse_args()

    if args.check_all:
        if args.file or args.from_phase is not None or args.apply:
            usage_error("--check-all takes no FILE/FROM/--apply arguments")
        drift = check_all(args.base or "solutions")
        sys.exit(EXIT_DRIFT if drift else EXIT_OK)

    if args.base is None:
        usage_error("--base solutions|skeletons is required (no silent tree precedence)")
    if args.file is None or args.from_phase is None:
        usage_error("propagate mode needs FILE and FROM (or use --check-all)")

    drift = propagate(args.base, args.file, args.from_phase, args.to, args.apply)

    if drift and not args.apply:
        print("\nDrift found. Run with --apply to apply these changes.")
        sys.exit(EXIT_DRIFT)
    if not drift:
        print("All phases already in sync.")
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
