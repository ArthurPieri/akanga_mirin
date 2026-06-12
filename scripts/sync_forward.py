#!/usr/bin/env python3
"""
sync_forward.py — keep cross-phase module copies converged.

Two modes:

1. Propagate mode — diff a file from its source phase against all later phases
   in ONE explicit tree (no silent solutions/skeletons precedence) and
   optionally overwrite them:

       python scripts/sync_forward.py --base solutions src/akanga_core/parser.py 2
       python scripts/sync_forward.py --base solutions src/akanga_core/parser.py 2 --apply

   Propagate mode CONSULTS scripts/sync_manifest.toml (adversarial-analysis-v4
   #3): target phases listed in a module's `excluded`, or outside its
   `applies_to`, are SKIPPED with an explanation — they diverge on purpose and
   blind propagation would clobber them. `--force` overrides the skip (use it
   only when you are deliberately re-converging a divergent copy). Files with
   no manifest entry at all are propagated with a loud "unmanifested" warning.

2. Audit mode — read scripts/sync_manifest.toml (the canonical-source map from
   adversarial-analysis-v3.md #7) and verify every should-be-identical pair is
   byte-identical. This is the CI convergence gate:

       python scripts/sync_forward.py --check-all

   The audit runs three passes:
     a. manifest self-consistency (excluded/applies_to disjoint, reasons only
        on real exclusions, canonical + applies_to copies exist) — failures
        are usage errors (exit 2) because the gate itself is misconfigured;
     b. byte-identity of every manifest pair (drift → exit 1);
     c. completeness — every path that exists in >= 2 solutions/*/src trees
        must be covered by a [[modules]] or [[ignore]] entry, so a new
        multi-copy file can never appear outside the gate (drift → exit 1).

Exit codes:
    0  everything in sync (or --apply was given and changes were applied)
    1  drift found
    2  usage error (bad arguments, missing files, unreadable or
       self-contradictory manifest)

Marker files (later-phase skeleton placeholders saying "Copy your Phase NN
solution here" / "intentionally left as a reference marker") are never
overwritten and never counted as drift.
"""

from __future__ import annotations

import argparse
import difflib
import sys
import tomllib

# Shared scripts/ conventions live in _common (a sibling module, resolvable
# because scripts run as `python scripts/x.py`): the marker convention so the
# drift gate and the skeleton merger can never disagree about what a marker
# is (adversarial-analysis-v5 #4), and REPO_ROOT (adversarial-analysis-v5 #6).
from _common import REPO_ROOT, is_marker_file
MANIFEST_PATH = REPO_ROOT / "scripts" / "sync_manifest.toml"
MANIFEST_LABEL = "scripts/sync_manifest.toml"
SOLUTIONS_DIR = REPO_ROOT / "solutions"

EXIT_OK = 0
EXIT_DRIFT = 1
EXIT_USAGE = 2

# Noise that the completeness walk must never count as a "copy".
COMPLETENESS_SKIP_PARTS = {"__pycache__", ".DS_Store"}
COMPLETENESS_SKIP_SUFFIXES = {".pyc", ".pyo"}


def usage_error(message: str) -> None:
    print(f"error: {message}", file=sys.stderr)
    sys.exit(EXIT_USAGE)


# ---------------------------------------------------------------------------
# Manifest loading + self-consistency validation
# ---------------------------------------------------------------------------


def load_manifest_data() -> dict:
    """Load the full manifest TOML: [[modules]] entries + [[ignore]] entries."""
    if not MANIFEST_PATH.exists():
        usage_error(f"manifest not found: {MANIFEST_PATH}")
    try:
        data = tomllib.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        usage_error(f"manifest is not valid TOML: {exc}")
    if not data.get("modules"):
        usage_error("manifest contains no [[modules]] entries")
    data.setdefault("ignore", [])
    return data


def manifest_file_line(rel_file: str) -> int | None:
    """Best-effort line number of the `file = "..."` key for error pointers."""
    try:
        for i, line in enumerate(
            MANIFEST_PATH.read_text(encoding="utf-8").splitlines(), start=1
        ):
            if line.split("#", 1)[0].replace(" ", "").startswith(f'file="{rel_file}"'):
                return i
    except OSError:
        pass
    return None


def _pointer(rel_file: str) -> str:
    line = manifest_file_line(rel_file)
    return f"{MANIFEST_LABEL}:{line}" if line else MANIFEST_LABEL


def validate_manifest(data: dict) -> list[str]:
    """Self-consistency checks (adversarial-analysis-v4 #3b).

    Returns a list of human-readable errors; an empty list means the manifest
    is internally coherent and matches the solutions tree it governs.
    """
    errors: list[str] = []

    for mod in data["modules"]:
        rel = mod.get("file")
        if not rel:
            errors.append(f"{MANIFEST_LABEL}: a [[modules]] entry has no `file` key")
            continue
        where = _pointer(rel)

        intro = mod.get("introduced_in")
        applies = mod.get("applies_to")
        if intro is None or applies is None:
            errors.append(
                f"{where} ({rel}): entry needs both `introduced_in` and `applies_to`"
            )
            continue

        excluded = mod.get("excluded", [])
        overlap = sorted(set(excluded) & set(applies))
        if overlap:
            errors.append(
                f"{where} ({rel}): phases {overlap} are in BOTH `applies_to` and "
                "`excluded` — a phase cannot be converged and divergent at once"
            )

        if mod.get("excluded_reason") and not excluded:
            errors.append(
                f"{where} ({rel}): has `excluded_reason` but no non-empty `excluded` "
                "list — a reason with nothing excluded is stale (delete it or "
                "restore the exclusion)"
            )

        canonical = SOLUTIONS_DIR / f"phase_{intro:02d}" / rel
        if not canonical.is_file():
            errors.append(
                f"{where} ({rel}): canonical file does not exist: "
                f"solutions/phase_{intro:02d}/{rel}"
            )

        for phase in applies:
            copy = SOLUTIONS_DIR / f"phase_{phase:02d}" / rel
            if not copy.is_file():
                errors.append(
                    f"{where} ({rel}): `applies_to` lists phase {phase} but "
                    f"solutions/phase_{phase:02d}/{rel} does not exist"
                )

    for entry in data["ignore"]:
        rel = entry.get("file")
        if not rel:
            errors.append(f"{MANIFEST_LABEL}: an [[ignore]] entry has no `file` key")
            continue
        if not entry.get("reason"):
            errors.append(
                f"{_pointer(rel)} ({rel}): [[ignore]] entry has no `reason` — "
                "an ignore without a recorded reason is how intent gets lost"
            )

    return errors


def load_validated_manifest() -> dict:
    """Load the manifest and exit 2 with pointers if it is self-contradictory."""
    data = load_manifest_data()
    errors = validate_manifest(data)
    if errors:
        print(
            f"manifest self-consistency: {len(errors)} error(s) in {MANIFEST_LABEL}:",
            file=sys.stderr,
        )
        for e in errors:
            print(f"  {e}", file=sys.stderr)
        sys.exit(EXIT_USAGE)
    return data


def module_entry_for(data: dict, rel_file: str) -> dict | None:
    norm = rel_file.lstrip("./")
    for mod in data["modules"]:
        if mod.get("file") == norm:
            return mod
    return None


def ignore_entry_for(data: dict, rel_file: str) -> dict | None:
    norm = rel_file.lstrip("./")
    for entry in data["ignore"]:
        if entry.get("file") == norm:
            return entry
    return None


# ---------------------------------------------------------------------------
# Audit mode
# ---------------------------------------------------------------------------


def completeness_pass(data: dict) -> int:
    """Flag every >= 2-copy path under solutions/*/src that the manifest does
    not govern (neither [[modules]] nor [[ignore]]). Returns finding count.

    This is the decay guard from adversarial-analysis-v4 #3: without it, a new
    multi-copy file silently lives outside the convergence gate forever.
    """
    phases_by_path: dict[str, list[int]] = {}
    for phase_dir in sorted(SOLUTIONS_DIR.glob("phase_*")):
        try:
            phase = int(phase_dir.name.split("_")[1])
        except (IndexError, ValueError):
            continue
        src = phase_dir / "src"
        if not src.is_dir():
            continue
        for f in sorted(src.rglob("*")):
            if not f.is_file():
                continue
            if COMPLETENESS_SKIP_PARTS & set(f.parts):
                continue
            if f.suffix in COMPLETENESS_SKIP_SUFFIXES:
                continue
            rel = str(f.relative_to(phase_dir))
            phases_by_path.setdefault(rel, []).append(phase)

    governed = {m["file"] for m in data["modules"] if m.get("file")}
    governed |= {e["file"] for e in data["ignore"] if e.get("file")}

    findings = 0
    for rel, phases in sorted(phases_by_path.items()):
        if len(phases) < 2 or rel in governed:
            continue
        findings += 1
        print(
            f"  DRIFT  unmanifested multi-copy path: {rel} exists in "
            f"phases {phases} but {MANIFEST_LABEL} has no [[modules]] or "
            "[[ignore]] entry for it — add one (with a reason if the copies "
            "are meant to diverge)"
        )
    return findings


def check_all(base: str) -> int:
    """Run the full audit: self-consistency, byte-identity, completeness.

    Returns the number of drift findings (self-consistency failures exit 2
    before this returns). Missing files in the solutions tree count as drift;
    missing or marker files in the skeletons tree are skipped (skeletons
    legitimately re-ship only a subset, via markers or omission).
    """
    data = load_validated_manifest()
    modules = data["modules"]
    base_dir = REPO_ROOT / base
    if not base_dir.is_dir():
        usage_error(f"base directory not found: {base_dir}")

    drift = 0
    checked = 0
    print(f"Convergence audit: {base}/ against {MANIFEST_LABEL}")
    print("Manifest self-consistency: OK\n")

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

    completeness_findings = completeness_pass(data)
    drift += completeness_findings

    print(
        f"\n{checked} pair(s) compared, {drift} drifting "
        f"(of which {completeness_findings} unmanifested multi-copy path(s))."
    )
    if drift:
        print(
            "Fix: converge each file onto its canonical (introduction-phase) version, e.g.\n"
            f"  python scripts/sync_forward.py --base {base} <FILE> <INTRO_PHASE> --apply\n"
            "or add the missing manifest entry for unmanifested paths."
        )
    else:
        print(
            "All manifest pairs are byte-identical and every multi-copy path is "
            "governed — trees are converged."
        )
    return drift


# ---------------------------------------------------------------------------
# Propagate mode
# ---------------------------------------------------------------------------


def propagate(
    base: str,
    rel_file: str,
    from_phase: int,
    to_phase: int,
    apply: bool,
    force: bool = False,
) -> int:
    """Diff (and optionally apply) one file from its source phase forward.

    Consults the manifest first: excluded / out-of-range phases are skipped
    loudly unless --force; unmanifested files propagate with a warning.
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

    data = load_validated_manifest()
    entry = module_entry_for(data, rel_file)
    ignored = ignore_entry_for(data, rel_file)

    if ignored is not None:
        print("=" * 72)
        print(f"MANIFEST: {rel_file} is on the [[ignore]] list in {MANIFEST_LABEL}:")
        print(f"  reason: {ignored.get('reason', '(no reason recorded)')}")
        if force:
            print("  --force given: propagating anyway. You are overriding recorded intent.")
        else:
            print(
                "  Every phase's copy is intentionally divergent — nothing will be\n"
                "  propagated. Re-run with --force only if you are deliberately\n"
                "  re-converging these copies (and update the manifest afterwards)."
            )
        print("=" * 72)
        if not force:
            print("Nothing propagated.")
            sys.exit(EXIT_OK)
    elif entry is None:
        print("=" * 72)
        print(
            f"WARNING: {rel_file} has NO entry in {MANIFEST_LABEL} — "
            "propagating blindly."
        )
        print(
            "  The convergence gate does not govern this file. If it legitimately\n"
            "  exists in several phases, add a [[modules]] entry (or an [[ignore]]\n"
            "  entry with a reason) so `--check-all` can guard it."
        )
        print("=" * 72)
    else:
        if from_phase != entry["introduced_in"]:
            print(
                f"note: manifest says {rel_file} is canonical in "
                f"phase {entry['introduced_in']}, but you are propagating from "
                f"phase {from_phase} — make sure that is intentional.\n"
            )

    print(f"Source: {source_file.relative_to(REPO_ROOT)}")
    print(f"Propagating to phases {from_phase + 1}-{to_phase} in {base}/\n")

    drift = 0
    for n in range(from_phase + 1, to_phase + 1):
        target_file = base_dir / f"phase_{n:02d}" / rel_file
        target_label = f"phase_{n:02d}"

        if entry is not None:
            excluded = entry.get("excluded", [])
            applies = entry.get("applies_to", [])
            blocked_reason = None
            if n in excluded:
                blocked_reason = (
                    f"phase {n} is in `excluded` for this file in {MANIFEST_LABEL}"
                )
                detail = entry.get("excluded_reason")
                if detail:
                    blocked_reason += f"\n      manifest says: {detail}"
            elif n not in applies:
                blocked_reason = (
                    f"phase {n} is outside `applies_to` {applies} for this file "
                    f"in {MANIFEST_LABEL} (pre-introduction or never-shipping layer)"
                )
            if blocked_reason is not None:
                if force:
                    print(
                        f"  {target_label}: manifest would skip this phase "
                        "(--force: propagating anyway)"
                    )
                    print(f"      {blocked_reason}")
                else:
                    print(f"  {target_label}: SKIPPED by manifest — will not touch it.")
                    print(f"      {blocked_reason}")
                    print("      (override with --force only if you mean to re-converge it)")
                    continue

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
        "--force",
        action="store_true",
        help="Propagate even into phases the manifest excludes (overrides recorded intent)",
    )
    parser.add_argument(
        "--to",
        metavar="N",
        type=int,
        default=None,
        help="Stop at this phase (default: the manifest's [manifest].phases maximum, "
        "so a new phase added to the manifest is propagated to without editing this script)",
    )
    args = parser.parse_args()

    if args.to is None:
        # Resolve the bound from the manifest roster rather than a hard-coded
        # literal — adversarial-analysis-v5 #5 (phase roster single-sourcing).
        args.to = max(load_manifest_data().get("manifest", {}).get("phases", [8]))

    if args.check_all:
        if args.file or args.from_phase is not None or args.apply or args.force:
            usage_error("--check-all takes no FILE/FROM/--apply/--force arguments")
        drift = check_all(args.base or "solutions")
        sys.exit(EXIT_DRIFT if drift else EXIT_OK)

    if args.base is None:
        usage_error("--base solutions|skeletons is required (no silent tree precedence)")
    if args.file is None or args.from_phase is None:
        usage_error("propagate mode needs FILE and FROM (or use --check-all)")

    drift = propagate(
        args.base, args.file, args.from_phase, args.to, args.apply, force=args.force
    )

    if drift and not args.apply:
        print("\nDrift found. Run with --apply to apply these changes.")
        sys.exit(EXIT_DRIFT)
    if not drift:
        print("All phases already in sync.")
    sys.exit(EXIT_OK)


if __name__ == "__main__":
    main()
