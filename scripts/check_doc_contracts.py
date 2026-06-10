#!/usr/bin/env python3
"""check_doc_contracts.py — CI lint for doc <-> skeleton contract drift.

WHAT
    Mechanically detects three classes of documentation drift that previously
    had to be caught by eyeball review:

    1. SIGNATURE DRIFT — a function signature shown in a phase doc
       (docs/learning/phase-NN-*.md) disagrees with the real signature in
       that phase's skeleton (skeletons/phase_NN/src/**/*.py).
       Signatures are harvested from two places in each doc:
         a. ``def NAME(...)`` lines inside fenced ```python blocks
         b. bare call signatures in "What You Build" tables, e.g.
            `upsert_edge(source_id, target_id, relation, relation_id)`
    2. MISSING MAKE TARGET — a doc tells the learner to run `make X`
       but `X` is not a target in the repo Makefile.
    3. MISSING FOUNDATION DOC — a doc references `docs/foundations/X.md`
       that does not exist on disk.

WHY
    Phase docs are prose and drift silently; skeletons + tests are normative
    (decision D2 in docs/adversarial-analysis.md). This lint makes the defect
    class impossible to silently regrow: any reintroduced drift fails CI.

HOW (conventions honored)
    - A fenced python block whose preceding line(s) contain the word
      "illustrative" is skipped — the docs use that word to mark aspirational
      / sketch snippets that are not contracts.
    - Skeleton files that are bare reference markers (comment-only files that
      say "copy your phase NN solution here") contain no AST statements and
      are skipped automatically.
    - `self` / `cls` are ignored; type annotations are ignored; a doc may
      omit trailing skeleton parameters if they all have defaults.
    - docs/archive/ is never scanned.

USAGE
    python3 scripts/check_doc_contracts.py             # report, exit 1 on drift
    python3 scripts/check_doc_contracts.py --warn-only # report, always exit 0

Stdlib only. No third-party imports.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Allowlist for INTENTIONAL doc simplifications.
#
# Entry formats (one string each):
#   "phase_02:upsert_edge"          — skip signature check for this function
#                                     in this skeleton phase
#   "make:some-target"              — skip the Makefile-target existence check
#   "foundations:some-doc.md"       — skip the foundations-file existence check
#
# Keep this list SHORT and commented: every entry is a doc that deliberately
# lies to the learner, which should be rare and justified.
# ---------------------------------------------------------------------------
ALLOW: frozenset[str] = frozenset(
    {
        # (seeded empty)
    }
)

# Words that can follow "make" in prose without being a target.
_MAKE_STOPWORDS = {
    "a", "an", "the", "it", "this", "that", "them", "sure", "sense",
    "use", "your", "one", "any", "each", "every", "no", "or", "and",
}

DOC_GLOB = "docs/learning/phase-*.md"
SKELETON_DIR = "skeletons"
FOUNDATIONS_DIR = "docs/foundations"


# ---------------------------------------------------------------------------
# Data carriers
# ---------------------------------------------------------------------------


@dataclass
class DocSignature:
    """A function contract stated by a phase doc."""

    name: str
    params: list[str]
    doc_file: Path
    doc_line: int
    source: str  # "code block" | "What You Build table"


@dataclass
class SkeletonSignature:
    """A real function signature parsed from skeleton source."""

    name: str
    params: list[str]
    n_defaults: int
    file: Path
    line: int

    def render(self) -> str:
        parts = list(self.params)
        # Mark which trailing params carry defaults so the report is honest.
        for i in range(len(parts) - self.n_defaults, len(parts)):
            if 0 <= i < len(parts):
                parts[i] = parts[i] + "=…"
        return f"{self.name}({', '.join(parts)})"


@dataclass
class Finding:
    kind: str
    lines: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def split_top_level(s: str) -> list[str]:
    """Split a parameter string on commas that are not nested in brackets."""
    parts: list[str] = []
    depth = 0
    buf: list[str] = []
    for ch in s:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    tail = "".join(buf)
    if tail.strip():
        parts.append(tail)
    return parts


def parse_param_names(param_src: str) -> list[str] | None:
    """Turn 'a, b: int = 3, *args' into ['a', 'b'].

    Returns None when the text is not a plausible bare parameter list
    (e.g. it contains call expressions or literals) — the caller then
    discards the candidate signature instead of producing a bogus finding.
    """
    names: list[str] = []
    for raw in split_top_level(param_src):
        piece = raw.strip()
        if not piece:
            continue
        if piece.startswith("*") or piece == "/":
            # *args / **kwargs / keyword-only or positional-only markers end
            # the positional comparison; everything before them still counts.
            break
        name = piece.split("=", 1)[0].split(":", 1)[0].strip()
        if not name.isidentifier():
            return None
        names.append(name)
    if names and names[0] in ("self", "cls"):
        names = names[1:]
    return names


# ---------------------------------------------------------------------------
# Phase doc parsing
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^\s*```(\w*)\s*$")
_DEF_RE = re.compile(r"^\s*(?:async\s+)?def\s+([A-Za-z_]\w*)\s*\(")
_TABLE_SIG_RE = re.compile(r"^([A-Za-z_]\w*)\((.*)\)\s*(?:(?:→|->).*)?$")
_BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
_FOUNDATION_REF_RE = re.compile(r"docs/foundations/([A-Za-z0-9._-]+\.md)")
_MAKE_RE = re.compile(r"(?:^|[\s;|&(`])make\s+([A-Za-z][A-Za-z0-9_.-]*)")


def doc_phase_dir(doc_path: Path) -> str | None:
    """phase-01a-data-modeling.md -> 'phase_01' (1A and 1B share a skeleton)."""
    m = re.match(r"phase-(\d{2})", doc_path.name)
    return f"phase_{m.group(1)}" if m else None


def iter_code_blocks(lines: list[str]) -> list[tuple[str, int, list[str], bool]]:
    """Yield (lang, start_line_1based, block_lines, is_illustrative)."""
    blocks: list[tuple[str, int, list[str], bool]] = []
    in_block = False
    lang = ""
    start = 0
    buf: list[str] = []
    for i, line in enumerate(lines, start=1):
        m = _FENCE_RE.match(line)
        if m and not in_block:
            in_block, lang, start, buf = True, m.group(1).lower(), i + 1, []
            # Look back over up to 3 preceding non-blank lines for the
            # "illustrative" marker the docs use for aspirational snippets.
            preceding = [ln for ln in lines[: i - 1] if ln.strip()][-3:]
            illustrative = any("illustrative" in ln.lower() for ln in preceding)
            blocks.append((lang, start, buf, illustrative))
        elif m and in_block:
            in_block = False
        elif in_block:
            buf.append(line)
    return blocks


def defs_from_python_block(
    block_lines: list[str], start_line: int, doc_file: Path
) -> list[DocSignature]:
    """Extract def signatures from one fenced python block.

    Strategy: ast.parse the whole block when it is valid Python (most blocks
    are); fall back to a line regex with parenthesis balancing for partial
    snippets that do not parse.
    """
    src = "\n".join(block_lines)
    sigs: list[DocSignature] = []
    try:
        tree = ast.parse(_dedent(src))
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = [a.arg for a in node.args.posonlyargs + node.args.args]
                if params and params[0] in ("self", "cls"):
                    params = params[1:]
                sigs.append(
                    DocSignature(
                        name=node.name,
                        params=params,
                        doc_file=doc_file,
                        doc_line=start_line + node.lineno - 1,
                        source="code block",
                    )
                )
        return sigs
    # Regex fallback for non-parseable snippets.
    i = 0
    while i < len(block_lines):
        m = _DEF_RE.match(block_lines[i])
        if not m:
            i += 1
            continue
        # Balance parens, possibly across lines.
        collected = block_lines[i][m.end() - 1 :]
        j = i
        while collected.count("(") > collected.count(")") and j + 1 < len(block_lines):
            j += 1
            collected += " " + block_lines[j].strip()
        inner = collected[1 : collected.rfind(")")] if ")" in collected else ""
        params = parse_param_names(inner)
        if params is not None:
            sigs.append(
                DocSignature(
                    name=m.group(1),
                    params=params,
                    doc_file=doc_file,
                    doc_line=start_line + i,
                    source="code block",
                )
            )
        i = j + 1
    return sigs


def _dedent(src: str) -> str:
    import textwrap

    return textwrap.dedent(src)


def sigs_from_what_you_build_tables(
    lines: list[str], doc_file: Path
) -> list[DocSignature]:
    """Extract bare call signatures from 'What You Build' table rows."""
    sigs: list[DocSignature] = []
    in_section = False
    for i, line in enumerate(lines, start=1):
        if re.match(r"^##\s+What You Build\s*$", line):
            in_section = True
            continue
        if in_section and re.match(r"^##\s", line):
            in_section = False
        if not in_section or not line.lstrip().startswith("|"):
            continue
        for span in _BACKTICK_SPAN_RE.findall(line):
            m = _TABLE_SIG_RE.match(span.strip())
            if not m:
                continue
            params = parse_param_names(m.group(2))
            if params is None:
                continue
            sigs.append(
                DocSignature(
                    name=m.group(1),
                    params=params,
                    doc_file=doc_file,
                    doc_line=i,
                    source="What You Build table",
                )
            )
    return sigs


def parse_doc(doc_path: Path) -> tuple[
    list[DocSignature],
    list[tuple[str, int]],  # (make target, line)
    list[tuple[str, int]],  # (foundations filename, line)
]:
    lines = doc_path.read_text(encoding="utf-8").splitlines()
    sigs: list[DocSignature] = []

    blocks = iter_code_blocks(lines)
    code_line_numbers: set[int] = set()
    for lang, start, block_lines, illustrative in blocks:
        code_line_numbers.update(range(start, start + len(block_lines)))
        if illustrative:
            continue
        if lang in ("python", "py"):
            sigs.extend(defs_from_python_block(block_lines, start, doc_path))

    sigs.extend(sigs_from_what_you_build_tables(lines, doc_path))

    make_refs: list[tuple[str, int]] = []
    foundation_refs: list[tuple[str, int]] = []
    for i, line in enumerate(lines, start=1):
        for fname in _FOUNDATION_REF_RE.findall(line):
            foundation_refs.append((fname, i))
        # `make X` is only a contract when it appears in a code context:
        # inside a fenced block, or inside inline backticks.
        if i in code_line_numbers:
            candidates = _MAKE_RE.findall(line)
        else:
            candidates = []
            for span in _BACKTICK_SPAN_RE.findall(line):
                candidates.extend(_MAKE_RE.findall(span))
        for target in candidates:
            if target.lower() not in _MAKE_STOPWORDS:
                make_refs.append((target, i))
    return sigs, make_refs, foundation_refs


# ---------------------------------------------------------------------------
# Skeleton parsing
# ---------------------------------------------------------------------------


def parse_skeleton_phase(phase_dir: Path) -> dict[str, list[SkeletonSignature]]:
    """Map function name -> all real signatures in this phase's skeleton."""
    by_name: dict[str, list[SkeletonSignature]] = {}
    for py in sorted(phase_dir.rglob("*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # malformed skeleton is skeleton_check.py's problem
        if not tree.body:
            continue  # comment-only reference-marker file ("copy phase N here")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = [a.arg for a in node.args.posonlyargs + node.args.args]
            if params and params[0] in ("self", "cls"):
                params = params[1:]
            by_name.setdefault(node.name, []).append(
                SkeletonSignature(
                    name=node.name,
                    params=params,
                    n_defaults=len(node.args.defaults),
                    file=py,
                    line=node.lineno,
                )
            )
    return by_name


def signature_matches(doc: DocSignature, skel: SkeletonSignature) -> bool:
    if doc.params == skel.params:
        return True
    # The doc may omit trailing parameters that have defaults in the skeleton
    # (e.g. doc says `search_fts(query)`, skeleton has search_fts(query, limit=20)).
    n = len(doc.params)
    if (
        n < len(skel.params)
        and doc.params == skel.params[:n]
        and len(skel.params) - n <= skel.n_defaults
    ):
        return True
    return False


# ---------------------------------------------------------------------------
# Makefile parsing
# ---------------------------------------------------------------------------


def parse_makefile_targets(makefile: Path) -> set[str]:
    targets: set[str] = set()
    if not makefile.exists():
        return targets
    for line in makefile.read_text(encoding="utf-8").splitlines():
        # "target other-target: deps" — but not variable assignments (:=)
        # and not special targets (.PHONY etc.) and not indented recipe lines.
        m = re.match(r"^([A-Za-z][A-Za-z0-9 _.-]*?):(?!=)", line)
        if m:
            for t in m.group(1).split():
                targets.add(t)
    return targets


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

FIX_DIRECTION = (
    "fix direction: skeleton + tests are normative (decision D2) — update the doc."
)


def run_checks() -> list[Finding]:
    findings: list[Finding] = []

    docs = sorted(ROOT.glob(DOC_GLOB))
    docs = [d for d in docs if "archive" not in d.parts]
    makefile_targets = parse_makefile_targets(ROOT / "Makefile")
    skeleton_cache: dict[str, dict[str, list[SkeletonSignature]]] = {}

    for doc in docs:
        sigs, make_refs, foundation_refs = parse_doc(doc)
        phase = doc_phase_dir(doc)

        # ---- 1. signature drift ----
        if phase is not None:
            phase_dir = ROOT / SKELETON_DIR / phase
            if phase_dir.is_dir():
                if phase not in skeleton_cache:
                    skeleton_cache[phase] = parse_skeleton_phase(phase_dir)
                skel_map = skeleton_cache[phase]
                for sig in sigs:
                    if sig.name not in skel_map:
                        continue  # only names present in BOTH are contracts
                    if f"{phase}:{sig.name}" in ALLOW:
                        continue
                    candidates = skel_map[sig.name]
                    if any(signature_matches(sig, c) for c in candidates):
                        continue
                    best = candidates[0]
                    doc_render = f"{sig.name}({', '.join(sig.params)})"
                    findings.append(
                        Finding(
                            kind="SIGNATURE DRIFT",
                            lines=[
                                f"{rel(sig.doc_file)}:{sig.doc_line} "
                                f"({sig.source}) says  {doc_render}",
                                f"{rel(best.file)}:{best.line} "
                                f"skeleton has        {best.render()}",
                                FIX_DIRECTION,
                            ],
                        )
                    )

        # ---- 2. make targets ----
        for target, line in make_refs:
            if f"make:{target}" in ALLOW:
                continue
            if target not in makefile_targets:
                findings.append(
                    Finding(
                        kind="MISSING MAKE TARGET",
                        lines=[
                            f"{rel(doc)}:{line} tells the learner to run "
                            f"`make {target}`, but `{target}` is not a target "
                            f"in the Makefile.",
                            "fix direction: the Makefile is normative — fix the "
                            "doc, or add the target if it was meant to exist.",
                        ],
                    )
                )

        # ---- 3. foundations references ----
        for fname, line in foundation_refs:
            if f"foundations:{fname}" in ALLOW:
                continue
            if not (ROOT / FOUNDATIONS_DIR / fname).is_file():
                findings.append(
                    Finding(
                        kind="MISSING FOUNDATION DOC",
                        lines=[
                            f"{rel(doc)}:{line} references "
                            f"docs/foundations/{fname}, which does not exist.",
                            "fix direction: create the foundation doc or "
                            "correct the reference.",
                        ],
                    )
                )

    return findings


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Lint phase docs against skeletons, the Makefile, and "
        "foundation docs. Exit 1 on drift unless --warn-only."
    )
    parser.add_argument(
        "--warn-only",
        action="store_true",
        help="report findings but always exit 0 (CI soft-launch mode)",
    )
    args = parser.parse_args(argv)

    findings = run_checks()

    if not findings:
        print("doc-contract lint: OK — no doc <-> skeleton drift detected.")
        return 0

    print(f"doc-contract lint: {len(findings)} finding(s)\n")
    for n, f in enumerate(findings, start=1):
        print(f"[{n}] {f.kind}")
        for line in f.lines:
            print(f"    {line}")
        print()

    if args.warn_only:
        print("(--warn-only: exiting 0 despite findings)")
        return 0
    print(
        "Add intentional simplifications to the ALLOW list in "
        "scripts/check_doc_contracts.py, or fix the doc."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
