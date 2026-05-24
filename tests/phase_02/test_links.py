"""Phase 02 tests — links: extract_wikilinks, resolve_wikilink."""
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(node_id: str, title: str, tmp_vault: Path):
    """Construct a minimal Node instance."""
    from parser import Node  # noqa: PLC0415

    return Node(
        id=node_id,
        path=str(tmp_vault / f"{node_id[:8]}.md"),
        title=title,
        type="note",
        tags=[],
        content_hash=f"hash_{node_id[:8]}",
    )


# ---------------------------------------------------------------------------
# 1. extract_wikilinks
# ---------------------------------------------------------------------------

def test_extract_wikilinks_basic():
    """Plain [[Title]] wikilinks are extracted as a list of title strings."""
    from links import extract_wikilinks  # noqa: PLC0415

    content = "See [[Blink]] and [[Flow]] for more."
    result = extract_wikilinks(content)
    assert "Blink" in result
    assert "Flow" in result


def test_extract_wikilinks_none():
    """Content without any [[...]] patterns returns an empty list."""
    from links import extract_wikilinks  # noqa: PLC0415

    result = extract_wikilinks("No wikilinks here at all.")
    assert result == []


def test_extract_wikilinks_skips_inline_edges():
    """
    [[Target | relation]] inline edge syntax should not produce a wikilink for the
    full 'Target | relation' string.

    Acceptable outcomes:
    - The pattern is ignored entirely (empty list, or list without 'Target | relation').
    - Only the target title 'Target' is returned (extract_wikilinks strips the relation).

    Either behaviour is compliant with the spec; the test validates both.
    """
    from links import extract_wikilinks  # noqa: PLC0415

    content = "See [[Flow State | supports]] for context."
    result = extract_wikilinks(content)

    # The raw 'Flow State | supports' string must never appear as a wikilink title.
    assert "Flow State | supports" not in result
    # If 'Flow State' alone is returned, that is an acceptable implementation choice.
    # If result is empty, that is also acceptable.
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# 2. resolve_wikilink
# ---------------------------------------------------------------------------

def test_resolve_wikilink_found(tmp_db: str, tmp_vault: Path):
    """resolve_wikilink returns the node_id when the title exists in the DB."""
    from db import GraphDatabase  # noqa: PLC0415
    from links import resolve_wikilink  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaa1111-0000-0000-0000-000000000001", "Cognitive Load", tmp_vault)
    db.upsert_node(node)

    result = resolve_wikilink("Cognitive Load", db)
    assert result == node.id


def test_resolve_wikilink_case_insensitive(tmp_db: str, tmp_vault: Path):
    """resolve_wikilink matches titles case-insensitively."""
    from db import GraphDatabase  # noqa: PLC0415
    from links import resolve_wikilink  # noqa: PLC0415

    db = GraphDatabase(tmp_db)
    node = _make_node("aaaa2222-0000-0000-0000-000000000002", "Cognitive Load", tmp_vault)
    db.upsert_node(node)

    result = resolve_wikilink("cognitive load", db)
    assert result == node.id


def test_resolve_wikilink_not_found(tmp_db: str, tmp_vault: Path):
    """resolve_wikilink returns None when the title has no matching node."""
    from db import GraphDatabase  # noqa: PLC0415
    from links import resolve_wikilink  # noqa: PLC0415

    db = GraphDatabase(tmp_db)

    result = resolve_wikilink("Nonexistent Node Title That Cannot Match", db)
    assert result is None
