#!/usr/bin/env python3
"""
skeleton_check.py <skel_src_dir>

Verifies that every non-dunder method in the skeleton source directory raises
NotImplementedError and contains no real implementation. Exits non-zero if any
implemented method is found (which would indicate accidental solution leakage).

Usage:
    python scripts/skeleton_check.py skeletons/phase_02/src
"""
import ast
import pathlib
import sys


def check_skeleton(skel: pathlib.Path) -> list[str]:
    errors = []
    skip_names = {"__init__", "__repr__", "__str__", "__len__", "__enter__", "__exit__"}

    for py in sorted(skel.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError as e:
            errors.append(f"{py}: SyntaxError — {e}")
            continue

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name in skip_names:
                continue

            has_not_impl = any(
                isinstance(s, ast.Raise)
                and isinstance(getattr(s.exc, "func", None), ast.Name)
                and s.exc.func.id == "NotImplementedError"
                for s in ast.walk(node)
            )

            # Non-trivial statements: anything that isn't a pure docstring or pass
            real_stmts = [
                s
                for s in node.body
                if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant))
                and not isinstance(s, ast.Pass)
            ]

            if real_stmts and not has_not_impl:
                try:
                    rel = py.relative_to(skel.parent.parent)
                except ValueError:
                    rel = py
                errors.append(
                    f"{rel}:{node.lineno}: {node.name}() contains implementation"
                    f" — possible solution leakage"
                )

    return errors


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <skel_src_dir>", file=sys.stderr)
        sys.exit(2)

    skel = pathlib.Path(sys.argv[1])
    if not skel.is_dir():
        print(f"error: directory not found: {skel}", file=sys.stderr)
        sys.exit(2)

    errors = check_skeleton(skel)

    if errors:
        print("FAIL — skeleton contains implemented methods:")
        for e in errors:
            print("  ", e)
        sys.exit(1)
    else:
        print("OK — all stub methods correctly raise NotImplementedError")


if __name__ == "__main__":
    main()
