"""Shared conventions for the scripts/ tooling — single home, no copies.

WHAT: definitions that more than one script must agree on. Exactly four
residents, each with >= 3 call sites — NOT a kitchen-sink utils module:

  1. the skeleton reference-marker convention (adversarial-analysis-v5 #4):
     MARKER_SNIPPETS / is_marker_file
  2. REPO_ROOT (adversarial-analysis-v5 #6)
  3. the phase-identifier convention, including the 1A/1B split:
     normalize_phase / SPLIT_PHASES (adversarial-analysis-v5 #6)
  4. the "## Heading section" Markdown walker: iter_md_section
     (adversarial-analysis-v5 #6)

WHY: scripts/ is the one multi-copy class the repo's own drift machinery
cannot see — sync_manifest.toml governs solutions/ phase copies, not
script-internal duplication, and no CI signal fires when two scripts'
private copies of a convention fork. Defined once here, they cannot.
`tests/test_scripts_markers.py` pins this module's marker definition
against the real skeleton tree and against check_doc_contracts.py's
deliberately different AST-empty heuristic.

Stdlib-only, imported as a sibling module (`import _common`), so every
script keeps working as a standalone `python scripts/<name>.py` invocation
with no packaging changes.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

# Later-phase skeletons ship 3-line placeholder files that intentionally do
# NOT contain an implementation ("Copy your Phase NN solution here..."').
# Overwriting them with a prior phase's full file — or treating them as drift
# to "fix" — would defeat their purpose. If the marker WORDING in the
# skeleton files ever changes, change it here too; the pinning test fails
# loudly when the two drift apart.
MARKER_SNIPPETS = (
    "intentionally left as a reference marker",
    "Copy your Phase",
)

# Markers are comment-only pointer files whose prose starts at line 1.
_MARKER_SCAN_LINES = 3


def is_marker_file(content: str) -> bool:
    """True when `content` is a skeleton reference-marker placeholder.

    Matches only within the first few lines — scanning the whole file would
    silently exempt any real module that merely mentions a marker phrase in
    a comment or docstring (a whole-file substring false positive that would
    remove the file from the drift gate without a word of output).
    """
    head = "\n".join(content.splitlines()[:_MARKER_SCAN_LINES])
    return any(snippet in head for snippet in MARKER_SNIPPETS)


# This module lives in scripts/, so the repo root is two levels up. Every
# script previously derived this independently (sync_forward.py,
# check_doc_contracts.py, and twice inline in validate_vault.py) — all four
# used the identical `Path(__file__).resolve().parent.parent` recipe, so
# unifying them here changes nothing except the number of places it can fork.
REPO_ROOT = Path(__file__).resolve().parent.parent

# Phases whose curriculum doc is split into sub-phases while tests/skeletons
# stay unified at the bare number. Today only Phase 1 (1A edge schema /
# 1B workspace registry). If another phase ever splits (e.g. 4 -> 4a/4b),
# this table is the ONLY Python-side line to touch.
SPLIT_PHASES: dict[str, tuple[str, ...]] = {"1": ("1a", "1b")}

_PHASE_RE = re.compile(r"0*(\d+)([ab]?)")


def normalize_phase(
    raw: str,
    *,
    strip_split: bool = False,
    expand_split: bool = False,
) -> str | list[str]:
    """'01a' → '1a', '00' → '0', '2' → '2'. Lowercase, no leading zeros.

    Unrecognised input is returned as-is (lowercased, stripped) so callers
    can produce their own "no such phase" error against the original token.

    strip_split=True  → also drop the a/b sub-phase letter ('01a' → '1'):
        the unified tests/skeletons phase number. check_doc_contracts uses
        this to map a phase doc to its skeleton dir; the Makefile's
        PHASE_NUM does the same job in shell.
    expand_split=True → return a list of concrete sub-phase keys instead:
        '1' → ['1a', '1b'] per SPLIT_PHASES, anything else → [key].
        validate_vault uses this so `--phase 1` checks both manifests.

    The two flags answer opposite questions (collapse vs expand the split),
    so combining them is always a caller bug — rejected loudly.

    Convention also implemented in shell — Makefile (`PHASE_NUM` variable
    and the `docs-phase` recipe's case/printf block) and scripts/study.sh
    ("Normalise the phase number" block) — keep all three in step.
    """
    if strip_split and expand_split:
        raise ValueError("strip_split and expand_split are mutually exclusive")
    p = raw.strip().lower()
    m = _PHASE_RE.fullmatch(p)
    if m:
        key = m.group(1) + ("" if strip_split else m.group(2))
    else:
        key = p
    if expand_split:
        return list(SPLIT_PHASES.get(key, (key,)))
    return key


# A section ends at the NEXT `## ` heading — every walker in the repo agrees
# on this boundary (### sub-headings stay inside the section).
_SECTION_END_RE = re.compile(r"^##\s")


def iter_md_section(
    lines: list[str], heading_re: re.Pattern[str]
) -> Iterator[tuple[int, str]]:
    """Yield (lineno_1based, line) for every line inside matching sections.

    A section opens at a line matching `heading_re` and closes just before
    the next `## ` heading (which may itself open another matching section —
    ALL matching sections are walked, not just the first). Heading lines
    themselves are never yielded.

    Deliberately not exposed: "was the heading present at all" — the two
    callers that need it do `any(heading_re.match(ln) for ln in lines)`,
    which keeps this a plain generator instead of a result object.
    """
    in_section = False
    for i, line in enumerate(lines, start=1):
        if heading_re.match(line):
            in_section = True
            continue
        if in_section and _SECTION_END_RE.match(line):
            in_section = False
            continue
        if in_section:
            yield i, line
