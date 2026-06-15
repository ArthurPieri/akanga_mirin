"""Phase 02 — Link extraction and wikilink resolution skeleton.

Implement the two functions below.
"""
from __future__ import annotations



def extract_wikilinks(content: str) -> list[str]:
    """WHAT: Find all [[Title]] wikilinks in a Markdown body and return the titles.

    WHY: Wikilinks are the primary way nodes reference each other in Akanga.
    Every [[Title]] in a node's body becomes a directed edge in the graph
    (after resolution). Extracting them is the first step before resolution.

    HOW:
    1. Strip fenced code blocks FIRST, so `[[...]]` examples inside ``` fences
       are never mistaken for real wikilinks (the same invariant
       `parser.extract_inline_edges` enforces for typed inline edges):
           content = re.sub(r'```.*?```', '', content, flags=re.DOTALL)
    2. Define (or compile) a regex pattern that matches `[[...]]` wikilinks:
           pattern = re.compile(r'\\[\\[([^\\]|]+)(?:\\|[^\\]]+)?\\]\\]')
       Breakdown:
         - `\\[\\[`          — literal opening `[[`
         - `([^\\]|]+)`      — capture group: one or more chars that are NOT `]` or `|`
                               (this is the title; stops at `|` for inline-edge syntax)
         - `(?:\\|[^\\]]+)?` — optional non-capturing group: ` | relation` part (ignored)
         - `\\]\\]`          — literal closing `]]`
    3. Use `pattern.findall(content)` to get all captured title strings.
    4. Strip whitespace from each title with `.strip()`.
    5. Filter out any empty strings.
    6. Return the resulting list.

    Example:
        extract_wikilinks("See [[Blink]] and [[Flow State | supports]].")
        # Returns: ["Blink", "Flow State"]   (the relation part is discarded)

    Note: [[Title | relation]] inline-edge syntax must NOT produce the full
    "Title | relation" string as a wikilink — only "Title" (or nothing at all)
    is acceptable. Either behaviour is spec-compliant.
    """
    raise NotImplementedError(
        r"Strip ``` fences first (re.sub(r'```.*?```', '', content, flags=re.DOTALL)); "
        r"then re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]').findall(...); "
        "strip whitespace from each title; filter empty strings; return list"
    )


def resolve_wikilink(title: str, db: "GraphDatabase") -> str | None:
    """WHAT: Look up a node by title (case-insensitive) and return its UUID string.

    WHY: Wikilinks use human-readable titles, but the DB stores UUIDs. This
    function bridges the two representations so the indexer can store edges as
    stable UUID pairs rather than fragile title-to-title links.

    HOW:
    1. Inside `with db._lock:`, execute:
           SELECT id, path FROM nodes WHERE lower(title) = lower(?) ORDER BY path ASC
       with `(title,)` as the parameter, then `.fetchall()`.
    2. If no rows, return None.
    3. If MORE than one row, log a warning naming the shadowed duplicate(s) —
       a link you wrote should never resolve silently to an unpredictable node.
    4. Return the FIRST row's id (`rows[0]["id"]`).

    Notes:
    - Case-insensitive matching handles "cognitive load" == "Cognitive Load".
    - Returning None (not raising) lets the indexer skip-and-warn on
      unresolvable wikilinks rather than aborting the entire scan.
    - Duplicate titles resolve DETERMINISTICALLY by vault PATH order (path is
      NOT NULL UNIQUE — a total order, stable across `rm *.db` rebuilds, unlike
      rowid/insertion order). The first path wins (N10).
    """
    raise NotImplementedError(
        "SELECT id FROM nodes WHERE lower(title) = lower(?); fetchone(); "
        "return row['id'] or None if not found"
    )
