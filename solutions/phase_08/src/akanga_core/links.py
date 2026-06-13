"""Phase 02 — wikilink extraction and title → UUID resolution.

Wikilinks (`[[Title]]`) are how nodes reference each other in prose.
Every wikilink becomes a directed edge in the graph once resolved. The
two halves of that pipeline live here:

- `extract_wikilinks` — Markdown body → list of target titles
- `resolve_wikilink`  — title → node UUID (the DB stores stable UUID
  pairs, never fragile title-to-title links)
"""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — import only for type checkers
    from .db import GraphDatabase

logger = logging.getLogger(__name__)

# `[[Title]]` or `[[Title | segment]]` — group 1 is the target title, group 2
# the optional pipe segment (captured so the grammar can classify it).
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
# Fenced code blocks and inline code spans are stripped before extraction so
# example syntax inside ``` fences or `backticks` is never mistaken for a real
# wikilink — the same invariant `parser.extract_inline_edges` enforces.
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")


def extract_wikilinks(content: str) -> list[str]:
    """Return the target title of every PLAIN or ALIAS `[[...]]` wikilink.

    Fenced code blocks and inline code spans are stripped first. A TYPED link
    whose pipe segment is slug-shaped (`[[Flow State | supports]]`) is owned by
    the frontmatter fold pipeline (`parser.extract_inline_edges`), so it
    contributes NO wikilink edge here — a typed link yields exactly one edge,
    the typed one (single-edge semantics, N5). A plain `[[Title]]` or an
    Obsidian display alias (`[[Title | My Alias]]`, or an escaped
    `[[Title \\| x]]`) yields the bare target title.
    """
    from .parser import split_pipe_segment  # single source for the pipe grammar

    stripped = _INLINE_CODE_RE.sub("", _CODE_FENCE_RE.sub("", content))
    titles: list[str] = []
    for target, segment in _WIKILINK_RE.findall(stripped):
        # An escaped pipe leaves a trailing backslash on the target → alias.
        escaped = target.endswith("\\")
        if segment and not escaped and split_pipe_segment(segment)[0] == "relation":
            continue  # typed edge — not a wikilink (single-edge, N5)
        title = target.rstrip("\\").strip()
        if title:
            titles.append(title)
    return titles


def resolve_wikilink(title: str, db: GraphDatabase) -> str | None:
    """Look up a node by title (case-insensitive) and return its UUID string.

    Returns None when no node matches, letting the indexer skip-and-warn on
    unresolvable wikilinks instead of aborting the scan. Duplicate titles
    resolve DETERMINISTICALLY: matches are ordered by vault path (`path` is
    NOT NULL UNIQUE — a total order) and the first wins, with a warning that
    names every shadowed duplicate. Path order is stable across `rm *.db`
    rebuilds, unlike insertion order (N10). The title is bound as a `?`
    parameter, never interpolated into the SQL string.
    """
    with db._lock:
        rows = db.conn.execute(
            "SELECT id, path FROM nodes WHERE lower(title) = lower(?) ORDER BY path ASC",
            (title,),
        ).fetchall()
    if not rows:
        return None
    if len(rows) > 1:
        logger.warning(
            "Duplicate title %r: resolving to %s (%s) — first in vault path order; "
            "shadowed: %s",
            title,
            rows[0]["id"],
            rows[0]["path"],
            ", ".join(f"{r['id']} ({r['path']})" for r in rows[1:]),
        )
    return rows[0]["id"]
