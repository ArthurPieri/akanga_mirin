"""Shared conventions for the scripts/ tooling — single home, no copies.

WHAT: definitions that more than one script must agree on. First resident:
the skeleton reference-marker convention (adversarial-analysis-v5 #4).

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
