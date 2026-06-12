"""Pin the skeleton reference-marker convention to the real skeleton tree.

The convention "this skeleton file is a placeholder, not code" is load-bearing
for three tools — sync_forward.py (what the drift gate compares / what --apply
may overwrite), skeleton_merge.py (what the merger skips), and
check_doc_contracts.py (AST-empty heuristic). The first two share one
definition in scripts/_common.py; the marker FILES themselves are prose. This
test welds them together: reword the markers without updating MARKER_SNIPPETS
(or vice versa) and it fails loudly, instead of the gates silently disagreeing
(adversarial-analysis-v5 #4).

Imports no learner code — needs no AKANGA_SRC. Runs in CI's checks job.
"""
import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import _common  # noqa: E402  (scripts/ is path-injected above)


def _comment_only_pointer_files() -> list[Path]:
    """Skeleton .py files that are pure comments and point at a solution."""
    found = []
    for py in sorted((REPO_ROOT / "skeletons").rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        lines = [ln for ln in text.splitlines() if ln.strip()]
        if lines and all(ln.lstrip().startswith("#") for ln in lines) and "olution" in text:
            found.append(py)
    return found


def test_marker_files_exist_and_match_the_snippets():
    """Every comment-only solution-pointer file satisfies is_marker_file."""
    pointers = _comment_only_pointer_files()
    assert pointers, "no marker files found under skeletons/ — tree layout changed?"
    misses = [p for p in pointers if not _common.is_marker_file(p.read_text(encoding="utf-8"))]
    assert not misses, (
        "Marker files no longer match _common.MARKER_SNIPPETS — the drift gate "
        "and skeleton merger would now treat these as real code:\n  "
        + "\n  ".join(str(p.relative_to(REPO_ROOT)) for p in misses)
    )


def test_every_prose_marker_is_ast_empty():
    """is_marker_file ⇒ ast-empty, so check_doc_contracts' heuristic agrees."""
    disagree = []
    for py in sorted((REPO_ROOT / "skeletons").rglob("*.py")):
        text = py.read_text(encoding="utf-8")
        if _common.is_marker_file(text) and ast.parse(text).body:
            disagree.append(py)
    assert not disagree, (
        "Files match the prose-marker snippets but carry real code — "
        "check_doc_contracts.py's AST-empty heuristic would disagree with the "
        "drift gate about them:\n  "
        + "\n  ".join(str(p.relative_to(REPO_ROOT)) for p in disagree)
    )


def test_marker_match_is_anchored_to_the_file_head():
    """A real module that merely MENTIONS a marker phrase is not exempted."""
    decoy = (
        '"""A real module."""\n\n\n'
        "def deliberately_real() -> str:\n"
        '    # Copy your Phase 02 solution here, says some stale comment.\n'
        '    return "this file is intentionally left as a reference marker (not!)"\n'
    )
    assert not _common.is_marker_file(decoy), (
        "is_marker_file matched marker prose deep inside a real module — the "
        "whole-file substring false positive is back, silently exempting real "
        "files from the byte-identity drift gate"
    )
