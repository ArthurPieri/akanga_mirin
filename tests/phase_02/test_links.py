"""Phase 02 tests — links: extract_wikilinks, resolve_wikilink."""
from pathlib import Path

import pytest

from tests.phase_02.conftest import _load_db, _load_links, _load_parser

# Bound by the autouse fixture below at fixture time -- not import time -- so
# a missing/broken learner module is reported through the AKANGA_SRC guard's
# diagnostics instead of a raw collection error (adversarial-analysis-v5 #2).
GraphDatabase = None
_links_mod = None
_parser_mod = None


@pytest.fixture(scope="module", autouse=True)
def _bind_learner_modules():
    global GraphDatabase, _links_mod, _parser_mod
    GraphDatabase = _load_db()
    _links_mod = _load_links()
    _parser_mod = _load_parser()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_node(node_id: str, title: str, vault_dir: Path):
    """Construct a minimal Node instance."""
    Node = _parser_mod.Node

    return Node(
        id=node_id,
        path=str(vault_dir / f"{node_id[:8]}.md"),
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
    extract_wikilinks = _links_mod.extract_wikilinks

    content = "See [[Blink]] and [[Flow]] for more."
    result = extract_wikilinks(content)
    assert "Blink" in result
    assert "Flow" in result


def test_extract_wikilinks_none():
    """Content without any [[...]] patterns returns an empty list."""
    extract_wikilinks = _links_mod.extract_wikilinks

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
    extract_wikilinks = _links_mod.extract_wikilinks

    content = "See [[Flow State | supports]] for context."
    result = extract_wikilinks(content)

    # The raw 'Flow State | supports' string must never appear as a wikilink title.
    assert "Flow State | supports" not in result
    # If 'Flow State' alone is returned, that is an acceptable implementation choice.
    # If result is empty, that is also acceptable.
    assert isinstance(result, list)


def test_extract_wikilinks_ignores_fenced_code():
    """
    [[Title]] syntax inside fenced code blocks is example text, not a link.

    The typed-edge extractor (parser.extract_inline_edges) already strips
    ``` fences before matching; extract_wikilinks must enforce the same
    invariant, or fenced examples become real edges in the graph.
    """
    extract_wikilinks = _links_mod.extract_wikilinks

    content = (
        "Real link to [[Blink]].\n"
        "```\n"
        "Example syntax: [[Flow State]] and [[Deep Work | supports]]\n"
        "```\n"
        "Another real link to [[Atomic Habits]].\n"
    )
    result = extract_wikilinks(content)

    assert "Blink" in result
    assert "Atomic Habits" in result
    assert "Flow State" not in result
    assert "Deep Work" not in result


# ---------------------------------------------------------------------------
# 2. resolve_wikilink
# ---------------------------------------------------------------------------

def test_resolve_wikilink_found(db_path: str, vault_dir: Path):
    """resolve_wikilink returns the node_id when the title exists in the DB."""
    resolve_wikilink = _links_mod.resolve_wikilink

    db = GraphDatabase(db_path)
    node = _make_node("aaaa1111-0000-0000-0000-000000000001", "Cognitive Load", vault_dir)
    db.upsert_node(node)

    result = resolve_wikilink("Cognitive Load", db)
    assert result == node.id


def test_resolve_wikilink_case_insensitive(db_path: str, vault_dir: Path):
    """resolve_wikilink matches titles case-insensitively."""
    resolve_wikilink = _links_mod.resolve_wikilink

    db = GraphDatabase(db_path)
    node = _make_node("aaaa2222-0000-0000-0000-000000000002", "Cognitive Load", vault_dir)
    db.upsert_node(node)

    result = resolve_wikilink("cognitive load", db)
    assert result == node.id


def test_resolve_wikilink_not_found(db_path: str, vault_dir: Path):
    """resolve_wikilink returns None when the title has no matching node."""
    resolve_wikilink = _links_mod.resolve_wikilink

    db = GraphDatabase(db_path)

    result = resolve_wikilink("Nonexistent Node Title That Cannot Match", db)
    assert result is None


def test_duplicate_title_resolves_deterministically(db_path: str, vault_dir: Path, caplog):
    """Duplicate titles resolve by vault path order (N10), not insertion order — with a warning."""
    import logging

    resolve_wikilink = _links_mod.resolve_wikilink
    Node = _parser_mod.Node

    db = GraphDatabase(db_path)
    # Insert "b-second.md" FIRST so insertion order != path order: if resolution
    # used rowid/insertion order it would return this one; path order must not.
    db.upsert_node(Node(
        id="aaaa5001-0000-0000-0000-000000000001", path="b-second.md",
        title="Shared Title", type="note", tags=[], content_hash="h1",
    ))
    db.upsert_node(Node(
        id="aaaa5002-0000-0000-0000-000000000002", path="a-first.md",
        title="Shared Title", type="note", tags=[], content_hash="h2",
    ))

    with caplog.at_level(logging.WARNING):
        result = resolve_wikilink("Shared Title", db)

    assert result == "aaaa5002-0000-0000-0000-000000000002", (
        "duplicate titles must resolve to the node first in vault PATH order "
        "(a-first.md), deterministically across rebuilds — not by insertion order"
    )
    assert "Duplicate title" in caplog.text, (
        f"resolving an ambiguous title must warn and name the shadowed node; got {caplog.text!r}"
    )
