"""Phase 01 tests — Edge schema, inline edge extraction, merge, and write-back."""
from pathlib import Path
from textwrap import dedent

import pytest


# ---------------------------------------------------------------------------
# Module-level import helper
# ---------------------------------------------------------------------------

def _get_parse_fn(m):
    """Return the parse function, accepting either 'parse' or 'parse_node_file'."""
    fn = getattr(m, "parse", None) or getattr(m, "parse_node_file", None)
    if fn is None:
        pytest.fail(
            "parser module must export either 'parse' or 'parse_node_file'. "
            "Found neither."
        )
    return fn


def _load_module():
    """Import the learner's parser module.

    Tries ``parser`` first (flat layout), then ``akanga_core.parser``
    (package layout).  Fails with a clear message if neither is found.
    """
    try:
        import parser as m  # noqa: PLC0415
        return m
    except ModuleNotFoundError:
        import importlib  # noqa: PLC0415
        import sys  # noqa: PLC0415
        # Try akanga_core.parser
        try:
            from akanga_core import parser as m  # noqa: PLC0415
            return m
        except ModuleNotFoundError:
            pytest.fail(
                "Cannot import parser module. "
                "Set AKANGA_SRC to a directory containing either parser.py or akanga_core/parser.py"
            )


# ---------------------------------------------------------------------------
# 1. Edge dataclass
# ---------------------------------------------------------------------------

def test_edge_dataclass_fields():
    """Edge can be instantiated with all four fields and attributes are accessible."""
    m = _load_module()
    Edge = m.Edge

    edge = Edge(
        relation="contradicts",
        relation_id="EP-002",
        target="Blink — Gladwell",
        target_id="d4e1f9cc-5678-1234-efab-012345678901",
    )
    assert edge.relation == "contradicts"
    assert edge.relation_id == "EP-002"
    assert edge.target == "Blink — Gladwell"
    assert edge.target_id == "d4e1f9cc-5678-1234-efab-012345678901"


# ---------------------------------------------------------------------------
# 2. extract_inline_edges
# ---------------------------------------------------------------------------

def test_extract_inline_edges_basic():
    """A single [[Target | relation]] pattern in prose produces one Edge."""
    m = _load_module()
    extract_inline_edges = m.extract_inline_edges

    body = "This idea [[Blink — Gladwell | contradicts]] fast thinking."
    edges = extract_inline_edges(body)
    assert len(edges) == 1
    assert edges[0].relation == "contradicts"
    assert edges[0].target == "Blink — Gladwell"


def test_extract_inline_edges_multiple():
    """Two inline edge patterns in prose produce two distinct Edge objects."""
    m = _load_module()
    extract_inline_edges = m.extract_inline_edges

    body = (
        "See [[Blink — Gladwell | contradicts]] and "
        "[[Kahneman System 1 | supports]] for context."
    )
    edges = extract_inline_edges(body)
    assert len(edges) == 2
    targets = {e.target for e in edges}
    relations = {e.relation for e in edges}
    assert "Blink — Gladwell" in targets
    assert "Kahneman System 1" in targets
    assert "contradicts" in relations
    assert "supports" in relations


def test_extract_inline_edges_ignores_code_blocks():
    """Inline edge shorthand inside backtick fences must be ignored."""
    m = _load_module()
    extract_inline_edges = m.extract_inline_edges

    body = "Normal text.\n```\n[[Some Node | supports]]\n```\nMore text."
    edges = extract_inline_edges(body)
    assert edges == []


def test_extract_inline_edges_ignores_regular_wikilinks():
    """Plain [[NodeName]] without a pipe separator is not an inline edge."""
    m = _load_module()
    extract_inline_edges = m.extract_inline_edges

    body = "See [[NodeName]] for more details."
    edges = extract_inline_edges(body)
    # Plain wikilinks have no relation — they must not appear as edges.
    assert edges == [], (
        f"Plain [[NodeName]] wikilinks must produce no inline edges, got: {edges!r}"
    )


def test_extract_inline_edges_empty_body():
    """Empty string input returns an empty list without raising."""
    m = _load_module()
    extract_inline_edges = m.extract_inline_edges

    edges = extract_inline_edges("")
    assert edges == []


# ---------------------------------------------------------------------------
# 3. merge_edges
# ---------------------------------------------------------------------------

def test_merge_edges_deduplicates():
    """Duplicate (relation, target) pair: resolved target_id from existing is preserved."""
    m = _load_module()
    Edge = m.Edge
    merge_edges = m.merge_edges

    existing = [Edge(relation="contradicts", relation_id="EP-002", target="Blink", target_id="abc-123")]
    inline = [Edge(relation="contradicts", relation_id="EP-002", target="Blink", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 1
    assert merged[0].target_id == "abc-123"


def test_merge_edges_adds_new():
    """An inline edge with a different (relation, target) is added to the result."""
    m = _load_module()
    Edge = m.Edge
    merge_edges = m.merge_edges

    existing = [Edge(relation="contradicts", relation_id="EP-002", target="Blink", target_id="abc-123")]
    inline = [Edge(relation="supports", relation_id="EP-001", target="Kahneman", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 2


def test_merge_is_not_order_sensitive():
    """Merging the same two edges in reversed order produces the same logical result."""
    m = _load_module()
    Edge = m.Edge
    merge_edges = m.merge_edges

    e1 = Edge(relation="contradicts", relation_id="EP-002", target="Blink", target_id="abc-123")
    e2 = Edge(relation="supports", relation_id="EP-001", target="Kahneman", target_id="def-456")

    merged_ab = merge_edges([e1], [e2])
    merged_ba = merge_edges([e2], [e1])

    assert {(e.relation, e.target) for e in merged_ab} == {(e.relation, e.target) for e in merged_ba}


def test_merge_edges_empty_inputs():
    """Both empty lists → empty result without raising."""
    m = _load_module()
    merge_edges = m.merge_edges

    merged = merge_edges([], [])
    assert merged == []


# ---------------------------------------------------------------------------
# 4. write_back
# ---------------------------------------------------------------------------

def test_write_back_moves_inline_to_frontmatter(tmp_vault: Path):
    """
    A file with an inline edge in the body but empty frontmatter edges block.
    After write_back(), the edges block contains the inline edge.
    """
    m = _load_module()
    parse = _get_parse_fn(m)
    write_back = m.write_back

    content = dedent("""\
        ---
        id: bbbbbbbb-0000-0000-0000-000000000001
        title: Write Back Test
        type: note
        tags: []
        edges: []
        ---

        This idea [[Blink — Gladwell | contradicts]] fast thinking.
        """)
    node_file = tmp_vault / "write-back-test.md"
    node_file.write_text(content, encoding="utf-8")

    write_back(node_file)

    reparsed = parse(node_file)
    raw_edges = reparsed.frontmatter.get("edges", [])
    assert len(raw_edges) == 1
    assert raw_edges[0]["relation"] == "contradicts"
    assert raw_edges[0]["target"] == "Blink — Gladwell"


def test_write_back_idempotent(tmp_vault: Path):
    """Calling write_back() twice on the same file must not duplicate edges."""
    m = _load_module()
    parse = _get_parse_fn(m)
    write_back = m.write_back

    content = dedent("""\
        ---
        id: bbbbbbbb-0000-0000-0000-000000000002
        title: Idempotent Test
        type: note
        tags: []
        edges: []
        ---

        This idea [[Blink — Gladwell | contradicts]] fast thinking.
        """)
    node_file = tmp_vault / "idempotent-test.md"
    node_file.write_text(content, encoding="utf-8")

    write_back(node_file)
    write_back(node_file)

    reparsed = parse(node_file)
    raw_edges = reparsed.frontmatter.get("edges", [])
    assert len(raw_edges) == 1


def test_write_back_preserves_existing_edges(tmp_vault: Path):
    """
    A file with an existing frontmatter edge plus a new inline edge in the body.
    After write_back(), both edges are present without duplication.
    """
    m = _load_module()
    parse = _get_parse_fn(m)
    write_back = m.write_back

    content = dedent("""\
        ---
        id: bbbbbbbb-0000-0000-0000-000000000003
        title: Preserve Test
        type: note
        tags: []
        edges:
          - relation: supports
            relation_id: EP-001
            target: Kahneman System 1
            target_id: cccccccc-0000-0000-0000-000000000099
        ---

        Also [[Blink — Gladwell | contradicts]] this claim.
        """)
    node_file = tmp_vault / "preserve-test.md"
    node_file.write_text(content, encoding="utf-8")

    write_back(node_file)

    reparsed = parse(node_file)
    raw_edges = reparsed.frontmatter.get("edges", [])
    assert len(raw_edges) == 2
    relations = {e["relation"] for e in raw_edges}
    assert "supports" in relations
    assert "contradicts" in relations
