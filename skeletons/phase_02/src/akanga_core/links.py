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
           SELECT id FROM nodes WHERE lower(title) = lower(?)
       with `(title,)` as the parameter.
    2. Call `.fetchone()`. If the result is None, return None.
    3. Otherwise return `row[0]` (or `row["id"]` if using `sqlite3.Row`).

    Notes:
    - Case-insensitive matching handles "cognitive load" == "Cognitive Load".
    - Returning None (not raising) lets the indexer silently skip unresolvable
      wikilinks rather than aborting the entire scan.
    - If multiple nodes share the same title, the first result is returned.
      Disambiguating by path or UUID is out of scope for Phase 02.
    """
    raise NotImplementedError(
        "SELECT id FROM nodes WHERE lower(title) = lower(?); fetchone(); "
        "return row['id'] or None if not found"
    )
