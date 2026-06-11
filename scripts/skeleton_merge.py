#!/usr/bin/env python3
"""
skeleton_merge.py <skel_src_dir> <learner_src_dir>

Bridges the phase-transition stub gap (adversarial-analysis-v3.md #8): later
phases ship NEW stubs inside files the learner already owns. `make skeleton`
preserves the learner's files, so those stubs — and their WHAT/WHY/HOW
docstrings — would never arrive. This script AST-compares the top-level
symbols (functions and classes) of each skeleton file against the learner's
same-path file and APPENDS the missing stubs, with a banner comment, to the
learner's copy. Existing learner code is never modified or reordered.

Usage:
    python scripts/skeleton_merge.py skeletons/phase_02/src src

Prints one line per touched file:
    added 4 new stub(s) to src/akanga_core/parser.py: extract_links, ...

Exit codes: 0 ok (including "nothing to add"), 2 usage error.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

# Same marker convention as sync_forward.py — placeholders carry no stubs.
MARKER_SNIPPETS = (
    "intentionally left as a reference marker",
    "Copy your Phase",
)


def is_marker_file(content: str) -> bool:
    return any(snippet in content for snippet in MARKER_SNIPPETS)


def top_level_symbols(tree: ast.Module) -> dict[str, ast.stmt]:
    """Map name → node for every top-level function/class (skeleton_check-style ast walk,
    restricted to module body)."""
    symbols: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols[node.name] = node
    return symbols


def source_segment(source_lines: list[str], node: ast.stmt) -> str:
    """Extract a node's full source, including its decorators."""
    start = node.lineno
    decorators = getattr(node, "decorator_list", [])
    if decorators:
        start = min(start, min(d.lineno for d in decorators))
    end = node.end_lineno or node.lineno
    return "".join(source_lines[start - 1 : end])


def merge_file(skel_file: pathlib.Path, learner_file: pathlib.Path, phase_label: str) -> list[str]:
    """Append skeleton stubs missing from the learner file. Returns added names."""
    skel_source = skel_file.read_text(encoding="utf-8")
    if is_marker_file(skel_source):
        return []

    try:
        skel_tree = ast.parse(skel_source)
    except SyntaxError as exc:
        print(f"warning: cannot parse skeleton {skel_file}: {exc}", file=sys.stderr)
        return []

    learner_source = learner_file.read_text(encoding="utf-8")
    try:
        learner_tree = ast.parse(learner_source)
    except SyntaxError as exc:
        print(
            f"warning: cannot parse {learner_file} ({exc}) — fix the syntax error and "
            "re-run `make skeleton` to receive the new stubs",
            file=sys.stderr,
        )
        return []

    skel_symbols = top_level_symbols(skel_tree)
    learner_names = set(top_level_symbols(learner_tree))

    missing = [name for name in skel_symbols if name not in learner_names]
    if not missing:
        return []

    skel_lines = skel_source.splitlines(keepends=True)
    banner = (
        f"\n\n# ── Added by `make skeleton` ({phase_label}) — new stubs introduced by this "
        "phase. ──\n"
        "# Your existing code above was not touched. Implement these; the WHAT/WHY/HOW\n"
        "# docstrings explain each one.\n\n"
    )
    chunks = [source_segment(skel_lines, skel_symbols[name]).rstrip("\n") for name in missing]

    with learner_file.open("a", encoding="utf-8") as fh:
        if not learner_source.endswith("\n"):
            fh.write("\n")
        fh.write(banner.rstrip("\n") + "\n")
        fh.write("\n\n".join(chunks) + "\n")

    return missing


def main() -> None:
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <skel_src_dir> <learner_src_dir>", file=sys.stderr)
        sys.exit(2)

    skel_src = pathlib.Path(sys.argv[1])
    learner_src = pathlib.Path(sys.argv[2])
    if not skel_src.is_dir():
        print(f"error: skeleton directory not found: {skel_src}", file=sys.stderr)
        sys.exit(2)
    if not learner_src.is_dir():
        print(f"error: learner directory not found: {learner_src}", file=sys.stderr)
        sys.exit(2)

    match = re.search(r"phase_\d{2}", str(skel_src))
    phase_label = match.group(0) if match else skel_src.name

    total = 0
    for skel_file in sorted(skel_src.rglob("*.py")):
        rel = skel_file.relative_to(skel_src)
        learner_file = learner_src / rel
        if not learner_file.is_file():
            continue  # new files are the copy loop's job, not the merge's

        added = merge_file(skel_file, learner_file, phase_label)
        if added:
            total += len(added)
            print(
                f"added {len(added)} new stub(s) to {learner_src / rel}: {', '.join(added)}"
            )

    if total == 0:
        print("No new stubs to merge — your preserved files already have every symbol.")


if __name__ == "__main__":
    main()
