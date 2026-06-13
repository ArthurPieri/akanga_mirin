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

# `[[Title]]` — the capture stops at `|`, so the `[[Target | relation]]`
# inline-edge shorthand yields only the bare target title, never the raw
# piped string. The optional non-capturing group consumes the relation part.
_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]")
# Fenced code blocks are stripped before extraction so that example syntax
# inside ``` fences is never mistaken for a real wikilink — the same
# invariant `parser.extract_inline_edges` enforces for typed inline edges.
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def extract_wikilinks(content: str) -> list[str]:
    """Return the title of every `[[Title]]` wikilink in `content`.

    Fenced code blocks are stripped first so example syntax in ``` fences
    is ignored. Titles are whitespace-stripped; empty captures are dropped.
    The `[[Target | relation]]` inline-edge syntax contributes only `Target`
    (the relation half is the parser's `extract_inline_edges` concern).
    """
    stripped = _CODE_FENCE_RE.sub("", content)
    return [title.strip() for title in _WIKILINK_RE.findall(stripped) if title.strip()]


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
