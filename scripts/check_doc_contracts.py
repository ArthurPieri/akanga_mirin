#!/usr/bin/env python3
"""check_doc_contracts.py — CI lint for doc <-> skeleton contract drift.

WHAT
    Mechanically detects five classes of documentation drift that previously
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
    4. TEST-NAME CONTRACT (adversarial-analysis-v4 #5) — every backticked
       `test_*` token in a doc's "## Deliverable" section must exist as a
       test function in tests/phase_NN/ (phantom names are findings, exit 1);
       and every shipped `def test_*` the doc does NOT name is reported as a
       warning (exit 0 unless --strict-coverage).
    5. DOC FUNCTION MISSING FROM SKELETON (adversarial-analysis-v4 #11) — a
       non-test, non-private, top-level function the doc presents as a
       contract that exists NOWHERE in the phase skeleton (the rename case).
       Skipped when the phase skeleton is all reference markers.

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
    python3 scripts/check_doc_contracts.py --strict-coverage
                                # shipped-but-unlisted tests also fail (exit 1)

Stdlib only. No third-party imports.
"""
from __future__ import annotations

import argparse
import ast
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Shared scripts/ conventions (sibling module — scripts run as
# `python scripts/x.py`): REPO_ROOT, the phase-identifier convention with its
# 1A/1B split handling, and the "## Heading section" Markdown walker
# (adversarial-analysis-v5 #6).
from _common import REPO_ROOT, iter_md_section, normalize_phase

# ---------------------------------------------------------------------------
# Allowlist for INTENTIONAL doc simplifications.
#
# Entry formats (one string each):
#   "phase_02:upsert_edge"          — skip signature check for this function
#                                     in this skeleton phase
#   "make:some-target"              — skip the Makefile-target existence check
#   "foundations:some-doc.md"       — skip the foundations-file existence check
#   "test:phase_02:test_x"          — skip the phantom-test check for this name
#                                     (use ONLY for learner-authored exercise
#                                     tests the doc tells the reader to write)
#
# Keep this list SHORT and commented: every entry is a doc that deliberately
# lies to the learner, which should be rare and justified.
# ---------------------------------------------------------------------------
ALLOW: frozenset[str] = frozenset(
    {
        # phase-02 Deliverable says "Write `test_content_hash_skip` yourself" —
        # a learner-authored exercise test, intentionally absent from the
        # shipped suite.
        "test:phase_02:test_content_hash_skip",
    }
)

# Words that can follow "make" in prose without being a target.
_MAKE_STOPWORDS = {
    "a", "an", "the", "it", "this", "that", "them", "sure", "sense",
    "use", "your", "one", "any", "each", "every", "no", "or", "and",
}

DOC_GLOB = "docs/learning/phase-*.md"
SKELETON_DIR = "skeletons"
TESTS_DIR = "tests"
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
    top_level: bool = True  # module-top-level def (nested/method defs are not
    #                         skeleton contracts for check 5)


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
    severity: str = "error"  # "error" fails the lint; "warning" is exit-0
    #                          unless --strict-coverage promotes it


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def rel(p: Path) -> str:
    try:
        return str(p.relative_to(REPO_ROOT))
    except ValueError:
        return str(p)


def strip_self_cls(params: list[str]) -> list[str]:
    """Drop a leading `self`/`cls` — receivers are not contract parameters.

    One definition for the three harvest paths (doc AST blocks, doc regex
    fallback via parse_param_names, skeleton AST) so a doc method signature
    always compares against a skeleton method signature on equal terms.
    Local to this file on purpose: no second script strips receivers, and
    _common is capped at conventions with multi-script callers.
    """
    if params and params[0] in ("self", "cls"):
        return params[1:]
    return params


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
    return strip_self_cls(names)


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
    """phase-01a-data-modeling.md -> 'phase_01' (1A and 1B share a skeleton).

    The a/b suffix is dropped via the shared split-phase convention
    (_common.normalize_phase) — tests/skeletons are unified at the bare
    phase number, exactly like the Makefile's PHASE_NUM.
    """
    m = re.match(r"phase-(\d{2}[ab]?)", doc_path.name)
    if not m:
        return None
    num = normalize_phase(m.group(1), strip_split=True)  # '01a' -> '1'
    return f"phase_{int(num):02d}"


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
        top_level_ids = {id(n) for n in tree.body}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                params = strip_self_cls(
                    [a.arg for a in node.args.posonlyargs + node.args.args]
                )
                sigs.append(
                    DocSignature(
                        name=node.name,
                        params=params,
                        doc_file=doc_file,
                        doc_line=start_line + node.lineno - 1,
                        source="code block",
                        top_level=id(node) in top_level_ids,
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
                    top_level=not block_lines[i][:1].isspace(),
                )
            )
        i = j + 1
    return sigs


def _dedent(src: str) -> str:
    import textwrap

    return textwrap.dedent(src)


_WHAT_YOU_BUILD_HEAD_RE = re.compile(r"^##\s+What You Build\s*$")


def sigs_from_what_you_build_tables(
    lines: list[str], doc_file: Path
) -> list[DocSignature]:
    """Extract bare call signatures from 'What You Build' table rows."""
    sigs: list[DocSignature] = []
    for i, line in iter_md_section(lines, _WHAT_YOU_BUILD_HEAD_RE):
        if not line.lstrip().startswith("|"):
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
# Deliverable-section test-name harvesting (check 4)
# ---------------------------------------------------------------------------

# `test_foo` but not `test_foo.py` (filenames) and not substrings of longer
# identifiers like `latest_thing` (left boundary) — the naive pattern
# backtracks `test_db.py` into a phantom `test_d`.
_TEST_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9_])test_[a-z0-9_]+(?![a-z0-9_])")
_DELIVERABLE_HEAD_RE = re.compile(r"^##\s+Deliverables?\b")


def deliverable_test_tokens(doc_path: Path) -> tuple[list[tuple[str, int]], bool]:
    """Harvest test-function tokens from every '## Deliverable' section.

    Returns ([(token, line_1based), ...], section_found). Illustrative fenced
    blocks are skipped (same convention as the signature checks); tokens that
    are filenames (`test_db.py`) are not function contracts and are ignored.
    """
    lines = doc_path.read_text(encoding="utf-8").splitlines()
    illustrative_lines: set[int] = set()
    for _lang, start, block_lines, illustrative in iter_code_blocks(lines):
        if illustrative:
            illustrative_lines.update(range(start, start + len(block_lines)))

    tokens: list[tuple[str, int]] = []
    for i, line in iter_md_section(lines, _DELIVERABLE_HEAD_RE):
        if i in illustrative_lines:
            continue
        for m in _TEST_TOKEN_RE.finditer(line):
            if line[m.end() : m.end() + 3] == ".py":
                continue  # a test FILE, not a test function
            tokens.append((m.group(0), i))
    section_found = any(_DELIVERABLE_HEAD_RE.match(ln) for ln in lines)
    return tokens, section_found


def parse_phase_tests(tests_dir: Path) -> dict[str, str]:
    """Map test-function name -> 'tests/phase_NN/file.py:line' for one phase."""
    by_name: dict[str, str] = {}
    if not tests_dir.is_dir():
        return by_name
    for py in sorted(tests_dir.rglob("test_*.py")):
        try:
            tree = ast.parse(py.read_text(encoding="utf-8"))
        except SyntaxError:
            continue  # broken test files are pytest's problem, not the lint's
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith(
                "test_"
            ):
                by_name.setdefault(node.name, f"{rel(py)}:{node.lineno}")
    return by_name


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
        # Deliberately NOT _common.is_marker_file: this lint needs "carries no
        # code at all", which also covers empty __init__.py — a superset of
        # the prose-marker convention. tests/test_scripts_markers.py pins that
        # every prose marker is AST-empty, so the two heuristics agree on
        # every real marker file (adversarial-analysis-v5 #4).
        if not tree.body:
            continue  # comment-only reference-marker file ("copy phase N here")
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            params = strip_self_cls(
                [a.arg for a in node.args.posonlyargs + node.args.args]
            )
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


# ---------------------------------------------------------------------------
# Check 6 — relation-count drift (relation-vocabulary.md IS the registry)
# ---------------------------------------------------------------------------

_RELID_ROW_RE = re.compile(r"^\|\s*`([A-Z]{2}-\d{3})`\s*\|")

# A number CLAIMED to be the relation-type count. Three accepted shapes; the
# BARE "of the <n>" form is deliberately NOT used because it false-positives on
# node counts (pinned known-negative: phase-08 "roughly 22 of the 170 consume
# the whole 12,000-char budget" — neither 22 nor 170 may match). Pinned
# known-positive (must match -> 72): phase-08 "52 of the 72 relation types have
# no defined inverse" (the 72 matches; the 52 inverse-subcount must NOT).
_RELCOUNT_RES = (
    re.compile(r"\b(\d{2,3})-(?:type|relation)\b"),
    re.compile(r"\b(\d{2,3}) (?:built-in )?(?:typed )?relations?\b"),
    re.compile(r"\b(\d{2,3}) (?:built-in )?relation types?\b"),
    re.compile(r"of the (\d{2,3})(?=\s+(?:relation|typed|directed|have no))"),
)


def _registry_relation_count() -> int:
    path = REPO_ROOT / FOUNDATIONS_DIR / "relation-vocabulary.md"
    if not path.is_file():
        return 0
    ids = set()
    for line in path.read_text().splitlines():
        m = _RELID_ROW_RE.match(line)
        if m:
            ids.add(m.group(1))
    return len(ids)


def check_relation_count_drift() -> list[Finding]:
    """Every relation-type count across phase/foundation docs must equal the
    number of unique ID-first rows in relation-vocabulary.md. ALLOW entries are
    ``relcount:<filename>:<number>`` (expected to stay empty)."""
    findings: list[Finding] = []
    expected = _registry_relation_count()
    if expected == 0:
        return findings  # registry unreadable — do not mask it with false drift
    scan = sorted(REPO_ROOT.glob(DOC_GLOB))
    scan += [
        p
        for p in sorted((REPO_ROOT / FOUNDATIONS_DIR).glob("*.md"))
        if p.name != "relation-vocabulary.md"
    ]
    for path in scan:
        for lineno, line in enumerate(path.read_text().splitlines(), 1):
            nums = set()
            for rx in _RELCOUNT_RES:
                nums.update(int(m.group(1)) for m in rx.finditer(line))
            for n in sorted(nums):
                if n == expected:
                    continue
                if f"relcount:{path.name}:{n}" in ALLOW:
                    continue
                findings.append(
                    Finding(
                        kind="RELATION-COUNT DRIFT",
                        lines=[
                            f"{rel(path)}:{lineno} claims {n} relation types; the "
                            f"registry (relation-vocabulary.md) has {expected}.",
                            f"  > {line.strip()}",
                            "fix the doc (relation-vocabulary.md is the source of "
                            f"truth), or ALLOW relcount:{path.name}:{n} if intentional.",
                        ],
                    )
                )
    return findings


def run_checks() -> list[Finding]:
    findings: list[Finding] = []

    docs = sorted(REPO_ROOT.glob(DOC_GLOB))
    docs = [d for d in docs if "archive" not in d.parts]
    makefile_targets = parse_makefile_targets(REPO_ROOT / "Makefile")
    skeleton_cache: dict[str, dict[str, list[SkeletonSignature]]] = {}
    tests_cache: dict[str, dict[str, str]] = {}
    # Per-phase aggregation for check 4's reverse direction (1A + 1B share
    # tests/phase_01, so doc tokens must be unioned before comparing).
    listed_tokens_by_phase: dict[str, set[str]] = {}
    deliverable_seen_by_phase: dict[str, bool] = {}
    docs_by_phase: dict[str, list[Path]] = {}

    for doc in docs:
        sigs, make_refs, foundation_refs = parse_doc(doc)
        phase = doc_phase_dir(doc)

        # ---- 1. signature drift  +  5. doc functions absent from skeleton ----
        if phase is not None:
            phase_dir = REPO_ROOT / SKELETON_DIR / phase
            if phase_dir.is_dir():
                if phase not in skeleton_cache:
                    skeleton_cache[phase] = parse_skeleton_phase(phase_dir)
                skel_map = skeleton_cache[phase]
                for sig in sigs:
                    if f"{phase}:{sig.name}" in ALLOW:
                        continue
                    if sig.name not in skel_map:
                        # ---- 5. the rename case: the doc presents a function
                        # the skeleton no longer (or never) has. Only firm
                        # contracts count: top-level, not a test, not private,
                        # and only when the phase skeleton has real (non-marker)
                        # files to hold it.
                        if (
                            skel_map
                            and sig.top_level
                            and not sig.name.startswith(("test_", "_"))
                        ):
                            findings.append(
                                Finding(
                                    kind="DOC FUNCTION MISSING FROM SKELETON",
                                    lines=[
                                        f"{rel(sig.doc_file)}:{sig.doc_line} "
                                        f"({sig.source}) shows "
                                        f"`{sig.name}({', '.join(sig.params)})`, but no "
                                        f"function named `{sig.name}` exists anywhere in "
                                        f"{SKELETON_DIR}/{phase}/.",
                                        "fix direction: skeleton + tests are normative "
                                        "(decision D2) — rename it in the doc, or mark "
                                        'the block "illustrative" if it is not a '
                                        "contract.",
                                    ],
                                )
                            )
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

        # ---- 4a. Deliverable test names must exist (phantom-test check) ----
        if phase is not None:
            tokens, section_found = deliverable_test_tokens(doc)
            if phase not in tests_cache:
                tests_cache[phase] = parse_phase_tests(REPO_ROOT / TESTS_DIR / phase)
            phase_tests = tests_cache[phase]
            docs_by_phase.setdefault(phase, []).append(doc)
            deliverable_seen_by_phase[phase] = (
                deliverable_seen_by_phase.get(phase, False) or section_found
            )
            bucket = listed_tokens_by_phase.setdefault(phase, set())
            for token, line in tokens:
                bucket.add(token)
                if f"test:{phase}:{token}" in ALLOW:
                    continue
                if phase_tests and token not in phase_tests:
                    findings.append(
                        Finding(
                            kind="PHANTOM TEST NAME",
                            lines=[
                                f"{rel(doc)}:{line} (Deliverable section) names "
                                f"`{token}`, but no such test function exists in "
                                f"{TESTS_DIR}/{phase}/.",
                                "fix direction: tests are normative — use the real "
                                "test name (it was probably renamed in remediation).",
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
            if not (REPO_ROOT / FOUNDATIONS_DIR / fname).is_file():
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

    # ---- 4b. reverse direction: shipped tests the docs never name ----------
    # Warning-level by default: an unlisted test under-specifies the
    # deliverable but lies to nobody. --strict-coverage promotes these.
    for phase, listed in sorted(listed_tokens_by_phase.items()):
        phase_tests = tests_cache.get(phase, {})
        if not phase_tests:
            continue
        doc_names = ", ".join(rel(d) for d in docs_by_phase.get(phase, []))
        if not deliverable_seen_by_phase.get(phase, False):
            findings.append(
                Finding(
                    kind="NO DELIVERABLE SECTION",
                    severity="warning",
                    lines=[
                        f"{doc_names}: no '## Deliverable' section found, so the "
                        f"{len(phase_tests)} tests in {TESTS_DIR}/{phase}/ are "
                        "enumerated nowhere.",
                    ],
                )
            )
            continue
        unlisted = sorted(set(phase_tests) - listed)
        if unlisted:
            findings.append(
                Finding(
                    kind="TEST NOT LISTED IN DELIVERABLE",
                    severity="warning",
                    lines=[
                        f"{len(unlisted)} shipped test(s) in {TESTS_DIR}/{phase}/ "
                        f"are missing from the Deliverable section of {doc_names}:",
                        *[f"  {phase_tests[name]}  `{name}`" for name in unlisted],
                        "fix direction: a learner building to the Deliverable list "
                        "will fail tests whose spec lives in ambience — name them.",
                    ],
                )
            )

    # ---- 6. relation-count drift -----------------------------------
    findings += check_relation_count_drift()

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
    parser.add_argument(
        "--strict-coverage",
        action="store_true",
        help="shipped-but-unlisted test warnings (check 4b) also fail the lint",
    )
    args = parser.parse_args(argv)

    findings = run_checks()
    if args.strict_coverage:
        for f in findings:
            f.severity = "error"
    errors = [f for f in findings if f.severity == "error"]
    warnings = [f for f in findings if f.severity == "warning"]

    if not findings:
        print("doc-contract lint: OK — no doc <-> skeleton drift detected.")
        return 0

    print(
        f"doc-contract lint: {len(errors)} finding(s), {len(warnings)} warning(s)\n"
    )
    n = 0
    for f in errors + warnings:
        n += 1
        suffix = " (warning)" if f.severity == "warning" else ""
        print(f"[{n}] {f.kind}{suffix}")
        for line in f.lines:
            print(f"    {line}")
        print()

    if args.warn_only:
        print("(--warn-only: exiting 0 despite findings)")
        return 0
    if not errors:
        print(
            "(warnings only — exiting 0; use --strict-coverage to make them fail)"
        )
        return 0
    print(
        "Add intentional simplifications to the ALLOW list in "
        "scripts/check_doc_contracts.py, or fix the doc."
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
