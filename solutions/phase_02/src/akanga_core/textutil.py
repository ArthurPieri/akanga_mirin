"""Shared text/path utilities — the single title→filename rule.

``slugify`` is the ONE canonical rule every surface uses (the Phase 0 ``create``,
the Phase 6 API, the Phase 8 MCP server), so the same title always yields the same
filename no matter which surface mints it — three different slug rules across three
surfaces is silent data divergence. ``tests/phase_00/test_textutil.py`` asserts a
cross-surface conformance table; extend it whenever the rule changes.
"""
from __future__ import annotations

import os
import re

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(title: str) -> str:
    """Lowercase, collapse non-alphanumeric runs to ``-``, strip edge dashes.

    Empty or fully-non-alphanumeric titles fall back to ``"untitled"``.
    """
    slug = _SLUG_RE.sub("-", title.lower()).strip("-")
    return slug or "untitled"


def unique_path(vault: str, slug: str, ext: str = ".md") -> str:
    """Absolute collision-free path for *slug* inside *vault*.

    On collision, numeric suffixes ``-1``, ``-2``, ... are tried in order — so
    ``create`` never silently overwrites an existing note.
    """
    path = os.path.abspath(os.path.join(vault, f"{slug}{ext}"))
    n = 1
    while os.path.exists(path):
        path = os.path.abspath(os.path.join(vault, f"{slug}-{n}{ext}"))
        n += 1
    return path
