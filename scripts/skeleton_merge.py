#!/usr/bin/env python3
"""
skeleton_merge.py <skel_src_dir> <learner_src_dir>

Bridges the phase-transition stub gap (adversarial-analysis-v3.md #8, hardened
in v4 #4): later phases ship NEW stubs inside files the learner already owns.
`make skeleton` preserves the learner's files, so those stubs — and their
WHAT/WHY/HOW docstrings — would never arrive. This script AST-compares each
skeleton file against the learner's same-path file and:

  1. APPENDS missing top-level symbols (functions, classes, AND module-level
     constants — simple-name Assign/AnnAssign targets) under a banner comment;
  2. INSERTS the skeleton imports the learner file lacks (deduped name-by-name,
     placed after the module docstring and any `from __future__` imports) so
     the new stubs' names actually resolve — no more NameError: Edge;
  3. REPORTS signature collisions: a symbol that exists in BOTH files but
     whose argument list CHANGED in this phase (e.g. `create()` gaining
     url/external_type/description at 1B) gets a prominent notice pointing at
     the skeleton file. The learner's version is NEVER modified.

Existing learner code is never modified or reordered, and re-running is
idempotent: already-merged imports, constants, and stubs are never duplicated.

Usage:
    python scripts/skeleton_merge.py skeletons/phase_02/src src

Exit codes:
    0  ok (including "nothing to add")
    2  usage error
    3  one or more LEARNER files could not be parsed (syntax error) — those
       files received nothing; fix them and re-run `make skeleton`.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

# Marker convention shared with sync_forward.py via _common (a sibling
# module) — placeholders carry no stubs, and the two tools must never
# disagree about what a marker is (adversarial-analysis-v5 #4).
from _common import is_marker_file

RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def _color(text: str, code: str) -> str:
    if sys.stdout.isatty():
        return f"{code}{text}{RESET}"
    return text


# ---------------------------------------------------------------------------
# AST harvesting
# ---------------------------------------------------------------------------


def top_level_symbols(tree: ast.Module) -> dict[str, ast.stmt]:
    """Map name → node for every top-level function/class AND module-level
    constant (simple-name Assign/AnnAssign targets), skeleton_check-style ast
    walk restricted to the module body."""
    symbols: dict[str, ast.stmt] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            symbols[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    symbols[target.id] = node
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                symbols[node.target.id] = node
    return symbols


def import_units(tree: ast.Module) -> set[tuple]:
    """Atomic import units at module top, deduped by (module, name, asname).

    ('import', name, asname)                  — `import x` / `import x as y`
    ('from', level, module, name, asname)     — `from m import n` / aliases
    """
    units: set[tuple] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                units.add(("import", alias.name, alias.asname))
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                units.add(("from", node.level, node.module, alias.name, alias.asname))
    return units


def render_import_lines(missing: set[tuple]) -> list[str]:
    """Render missing import units as source lines, __future__ first,
    plain imports next, from-imports grouped per (level, module)."""
    lines: list[str] = []
    plain = sorted(u for u in missing if u[0] == "import")
    froms = [u for u in missing if u[0] == "from"]

    grouped: dict[tuple[int, str | None], list[tuple[str, str | None]]] = {}
    for _, level, module, name, asname in froms:
        grouped.setdefault((level, module), []).append((name, asname))

    def from_line(level: int, module: str | None, names: list[tuple[str, str | None]]) -> str:
        rendered = ", ".join(
            n if a is None else f"{n} as {a}" for n, a in sorted(names)
        )
        return f"from {'.' * level}{module or ''} import {rendered}"

    # __future__ imports must precede everything else we insert.
    for (level, module), names in sorted(
        grouped.items(), key=lambda kv: (kv[0][1] != "__future__", kv[0][0], kv[0][1] or "")
    ):
        if module == "__future__":
            lines.append(from_line(level, module, names))
    for _, name, asname in plain:
        lines.append(f"import {name}" if asname is None else f"import {name} as {asname}")
    for (level, module), names in sorted(grouped.items(), key=lambda kv: (kv[0][0], kv[0][1] or "")):
        if module != "__future__":
            lines.append(from_line(level, module, names))
    return lines


def import_insert_line(tree: ast.Module) -> int:
    """1-based line AFTER which new imports go: past the module docstring and
    any leading `from __future__` imports (which must stay first)."""
    insert = 0
    body = tree.body
    idx = 0
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        insert = body[0].end_lineno or body[0].lineno
        idx = 1
    while (
        idx < len(body)
        and isinstance(body[idx], ast.ImportFrom)
        and body[idx].module == "__future__"
    ):
        insert = body[idx].end_lineno or body[idx].lineno
        idx += 1
    return insert


def func_arg_names(node: ast.FunctionDef | ast.AsyncFunctionDef) -> tuple[str, ...]:
    """Argument names in declaration order, with *, ** markers — the basis for
    signature-collision detection."""
    a = node.args
    parts: list[str] = [arg.arg for arg in a.posonlyargs]
    if a.posonlyargs:
        parts.append("/")
    parts.extend(arg.arg for arg in a.args)
    if a.vararg is not None:
        parts.append("*" + a.vararg.arg)
    elif a.kwonlyargs:
        parts.append("*")
    parts.extend(arg.arg for arg in a.kwonlyargs)
    if a.kwarg is not None:
        parts.append("**" + a.kwarg.arg)
    return tuple(parts)


def source_segment(source_lines: list[str], node: ast.stmt) -> str:
    """Extract a node's full source, including its decorators."""
    start = node.lineno
    decorators = getattr(node, "decorator_list", [])
    if decorators:
        start = min(start, min(d.lineno for d in decorators))
    end = node.end_lineno or node.lineno
    return "".join(source_lines[start - 1 : end])


# ---------------------------------------------------------------------------
# Per-file merge
# ---------------------------------------------------------------------------


class MergeResult:
    def __init__(self) -> None:
        self.added_symbols: list[str] = []
        self.added_imports: list[str] = []
        self.collisions: list[tuple[str, tuple[str, ...], tuple[str, ...]]] = []
        self.learner_syntax_error: str | None = None


def merge_file(
    skel_file: pathlib.Path, learner_file: pathlib.Path, phase_label: str
) -> MergeResult:
    """Merge one skeleton file into the learner's same-path file."""
    result = MergeResult()

    skel_source = skel_file.read_text(encoding="utf-8")
    if is_marker_file(skel_source):
        return result

    try:
        skel_tree = ast.parse(skel_source)
    except SyntaxError as exc:
        print(f"warning: cannot parse skeleton {skel_file}: {exc}", file=sys.stderr)
        return result

    learner_source = learner_file.read_text(encoding="utf-8")
    try:
        learner_tree = ast.parse(learner_source)
    except SyntaxError as exc:
        result.learner_syntax_error = f"line {exc.lineno}: {exc.msg}"
        return result

    skel_symbols = top_level_symbols(skel_tree)
    learner_symbols = top_level_symbols(learner_tree)

    # ── 1. Missing top-level symbols (functions, classes, constants) ────────
    missing_names = [name for name in skel_symbols if name not in learner_symbols]
    # An Assign like `A = B = ...` maps two names to one node — append it once.
    seen_nodes: set[int] = set()
    missing: list[str] = []
    for name in missing_names:
        node = skel_symbols[name]
        if id(node) in seen_nodes:
            continue
        seen_nodes.add(id(node))
        missing.append(name)

    # ── 2. Missing imports (only when this phase actually adds something —
    #       pulling in unused imports would trip ruff on untouched files) ────
    missing_imports: list[str] = []
    if missing:
        missing_units = import_units(skel_tree) - import_units(learner_tree)
        missing_imports = render_import_lines(missing_units)

    # ── 3. Signature collisions (report only — never touch learner code) ────
    for name, skel_node in skel_symbols.items():
        if name not in learner_symbols:
            continue
        learner_node = learner_symbols[name]
        if isinstance(skel_node, (ast.FunctionDef, ast.AsyncFunctionDef)) and isinstance(
            learner_node, (ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            skel_sig = func_arg_names(skel_node)
            learner_sig = func_arg_names(learner_node)
            if skel_sig != learner_sig:
                result.collisions.append((name, learner_sig, skel_sig))

    if not missing and not missing_imports:
        return result

    # ── Rewrite the learner file: imports inserted up top, stubs appended ───
    lines = learner_source.splitlines(keepends=True)

    if missing_imports:
        insert_at = import_insert_line(learner_tree)  # insert AFTER this 1-based line
        import_block = (
            f"# ── Added by `make skeleton` ({phase_label}) — imports needed by this "
            "phase's new stubs. ──\n"
            + "\n".join(missing_imports)
            + "\n"
        )
        prefix = "".join(lines[:insert_at])
        if insert_at > 0 and prefix and not prefix.endswith("\n"):
            prefix += "\n"
        if insert_at > 0:
            import_block = "\n" + import_block
        lines = [prefix, import_block] + lines[insert_at:]
        result.added_imports = missing_imports

    body = "".join(lines)
    if missing:
        skel_lines = skel_source.splitlines(keepends=True)
        banner = (
            f"\n\n# ── Added by `make skeleton` ({phase_label}) — new stubs introduced "
            "by this phase. ──\n"
            "# Your existing code above was not touched. Implement these; the WHAT/WHY/HOW\n"
            "# docstrings explain each one.\n\n"
        )
        chunks = [source_segment(skel_lines, skel_symbols[name]).rstrip("\n") for name in missing]
        if not body.endswith("\n"):
            body += "\n"
        body += banner.lstrip("\n") if body.endswith("\n\n") else banner
        body += "\n\n".join(chunks) + "\n"
        result.added_symbols = missing

    learner_file.write_text(body, encoding="utf-8")
    return result


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


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

    total_symbols = 0
    total_imports = 0
    syntax_errors: list[tuple[pathlib.Path, str]] = []
    all_collisions: list[tuple[pathlib.Path, pathlib.Path, str, tuple, tuple]] = []

    for skel_file in sorted(skel_src.rglob("*.py")):
        rel = skel_file.relative_to(skel_src)
        learner_file = learner_src / rel
        if not learner_file.is_file():
            continue  # new files are the copy loop's job, not the merge's

        res = merge_file(skel_file, learner_file, phase_label)

        if res.learner_syntax_error is not None:
            syntax_errors.append((learner_file, res.learner_syntax_error))
            continue
        if res.added_symbols:
            total_symbols += len(res.added_symbols)
            print(
                f"added {len(res.added_symbols)} new stub(s) to {learner_file}: "
                f"{', '.join(res.added_symbols)}"
            )
        if res.added_imports:
            total_imports += len(res.added_imports)
            print(
                f"added {len(res.added_imports)} import(s) to {learner_file}: "
                f"{'; '.join(res.added_imports)}"
            )
        for name, learner_sig, skel_sig in res.collisions:
            all_collisions.append((learner_file, skel_file, name, learner_sig, skel_sig))

    for learner_file, skel_file, name, learner_sig, skel_sig in all_collisions:
        print()
        print(_color("─" * 72, YELLOW))
        print(
            _color(
                f"NOTICE: `{name}` exists in your {learner_file} but this phase "
                f"CHANGED its signature — review {skel_file}",
                YELLOW,
            )
        )
        print(f"    yours:    {name}({', '.join(learner_sig)})")
        print(f"    skeleton: {name}({', '.join(skel_sig)})")
        print(
            "    Your version was NOT modified. Update it yourself once you reach"
            " the part of the phase doc that introduces the new parameters."
        )
        print(_color("─" * 72, YELLOW))

    if syntax_errors:
        print()
        for learner_file, msg in syntax_errors:
            print(
                _color(
                    f"could not parse {learner_file} ({msg}): fix the syntax error, "
                    "then re-run `make skeleton` — this file received no new stubs "
                    "or imports.",
                    RED,
                )
            )
        sys.exit(3)

    if total_symbols == 0 and total_imports == 0:
        print("No new stubs to merge — your preserved files already have every symbol.")
    sys.exit(0)


if __name__ == "__main__":
    main()
