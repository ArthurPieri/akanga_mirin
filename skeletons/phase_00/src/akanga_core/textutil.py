"""Phase 0 — shared text/path utilities skeleton.

`slugify` is the SINGLE title→filename rule every surface will reuse (this
phase's `create`, the Phase 6 API, the Phase 8 MCP server). Implement both
functions; `tests/phase_00/test_textutil.py` asserts a conformance table.
"""
from __future__ import annotations

import re

# Matches one or more characters that are NOT lowercase-alphanumeric — each run
# becomes a single "-". (unique_path will also need `import os`.)
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """WHAT: Reduce a title to a filesystem-safe slug.

    WHY: Three surfaces (create, the API, the MCP server) all turn a title into
    a filename. If each invents its own rule, the SAME title yields DIFFERENT
    filenames depending on who created the note — silent data divergence. One
    rule, asserted by a conformance table, keeps them in lockstep.

    HOW:
    1. Lowercase the title.
    2. Replace every run of non-`[a-z0-9]` characters with a single "-"
       (use `_SLUG_RE.sub("-", ...)`).
    3. Strip leading/trailing "-".
    4. If the result is empty (e.g. "!!!" or non-Latin text), return "untitled".

    Examples: "My First Note" -> "my-first-note"; "C++ & Python 3.13" ->
    "c-python-3-13"; "!!!" -> "untitled".
    """
    raise NotImplementedError(
        "Lowercase, collapse non-[a-z0-9] runs to '-', strip edge dashes, "
        "fall back to 'untitled'."
    )


def unique_path(vault: str, slug: str, ext: str = ".md") -> str:
    """WHAT: Return a collision-free absolute path for `slug` inside `vault`.

    WHY: A slug rule alone is not enough — two notes titled "Ideas" must not
    map to the same file. A collision-unsafe `create` silently OVERWRITES an
    existing note (data loss). Suffixing makes `create` safe to call twice.

    HOW:
    1. path = abspath(join(vault, slug + ext)).
    2. While that path exists, try `slug-1{ext}`, `slug-2{ext}`, ... in order.
    3. Return the first path that does not exist.
    """
    raise NotImplementedError(
        "Return vault/slug.md, or vault/slug-N.md for the first N where it does "
        "not already exist."
    )
