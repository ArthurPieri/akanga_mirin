# Copy your Phase 01 solution here, or run with AKANGA_SRC pointing to your Phase 01 src/ directory.
# This file is intentionally left as a reference marker — the skeleton runner picks up
# your actual implementation from AKANGA_SRC.
#
# Phase 02 adds ONE parser change and NO model changes — the Node and Edge
# dataclasses are identical to Phase 01's (the Node has been the same since Phase 0).
#
# The change: normalize YAML-implicit dates at the parse boundary.
#   WHAT  add a `_normalize_fm(value)` helper and apply it where parse_node_file
#         loads metadata: `fm = _normalize_fm(post.metadata or {})`.
#   WHY   PyYAML implicitly types bare scalars: `due: 2026-07-01` in frontmatter
#         parses to a `datetime.date` object, not the string the author visually
#         wrote. `json.dumps(node.frontmatter)` raises TypeError on it, and every
#         downstream consumer would otherwise have to handle two types. Normalize
#         once at the parse boundary and the whole system sees one type: str.
#   HOW   recurse over the metadata: datetime/date -> value.isoformat();
#         dict -> normalize each value; list -> normalize each item; everything
#         else passes through unchanged. (`datetime` is a subclass of `date`,
#         so one isinstance check against `(datetime, date)` covers both.)
#
# Full carry-forward set this phase expects from parser.py:
#   - parse_node_file(path: str) -> Node
#   - content_hash(path: str) -> str
#   - write_node_file(path: str, frontmatter_dict: dict, content: str) -> None
#   - create(title, type, vault, url="", external_type="", description="") -> Node
#   - extract_inline_edges(body: str) -> list[Edge]
#   - merge_edges(existing: list[Edge], inline: list[Edge]) -> list[Edge]
#   - write_back(path: str | Path) -> None
#
# See skeletons/phase_01/src/akanga_core/parser.py for the stubs and docstrings.
