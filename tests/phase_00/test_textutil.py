"""Phase 00 tests — textutil.slugify and unique_path (the single filename rule).

The slug cases are the cross-surface conformance table inlined from noteapp's
``tests/data/slug_cases.json`` — one table, asserted here, so every surface that
slugs a title (Phase 0 create, the Phase 6 API, the Phase 8 MCP server) agrees.
"""
from pathlib import Path

import pytest
from tests._helpers import load_attr

# Inlined from noteapp tests/data/slug_cases.json (Round 3 finding #1).
_SLUG_CASES = [
    ("My First Note", "my-first-note"),
    ("Héllo World!", "h-llo-world"),
    ("a/b notes", "a-b-notes"),
    ("UPPER  Case", "upper-case"),
    ("", "untitled"),
    ("!!!", "untitled"),
    ("  surrounded by spaces  ", "surrounded-by-spaces"),
    ("snake_case_title", "snake-case-title"),
    ("Already-Slugged", "already-slugged"),
    ("Numbers 123 here", "numbers-123-here"),
    ("C++ & Python 3.13", "c-python-3-13"),
    ("naïve café", "na-ve-caf"),
    ("Dots.and.dots", "dots-and-dots"),
    ("---dashes---", "dashes"),
    ("日本語タイトル", "untitled"),
    ("Mixed éèê ascii", "mixed-ascii"),
]


def _load_textutil():
    return load_attr(
        ("textutil", None),
        ("akanga_core.textutil", None),
        guard=lambda m: hasattr(m, "slugify"),
        guard_desc="no slugify — not the learner's textutil",
        hint="the textutil module (textutil.py or akanga_core/textutil.py)",
    )


@pytest.mark.parametrize("title,expected", _SLUG_CASES)
def test_slugify_conformance_table(title, expected):
    """slugify matches the cross-surface conformance table byte-for-byte."""
    slugify = _load_textutil().slugify
    assert slugify(title) == expected, (
        f"slugify({title!r}) must be {expected!r} — collapse non-alphanumeric "
        f"runs to '-', strip edge dashes, fall back to 'untitled'"
    )


def test_unique_path_no_collision(tmp_path):
    """A free slug returns `slug.md` unchanged."""
    unique_path = _load_textutil().unique_path
    assert Path(unique_path(str(tmp_path), "my-note")).name == "my-note.md"


def test_unique_path_suffixes_in_order(tmp_path):
    """Occupied slugs get `-1`, `-2`, ... in order — create never overwrites."""
    unique_path = _load_textutil().unique_path
    p1 = unique_path(str(tmp_path), "my-note")
    Path(p1).write_text("x", encoding="utf-8")
    p2 = unique_path(str(tmp_path), "my-note")
    Path(p2).write_text("x", encoding="utf-8")
    p3 = unique_path(str(tmp_path), "my-note")
    assert Path(p1).name == "my-note.md"
    assert Path(p2).name == "my-note-1.md"
    assert Path(p3).name == "my-note-2.md"
