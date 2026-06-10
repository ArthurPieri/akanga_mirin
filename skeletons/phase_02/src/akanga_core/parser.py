# Copy your Phase 01 solution here, or run with AKANGA_SRC pointing to your Phase 01 src/ directory.
# This file is intentionally left as a reference marker — the skeleton runner picks up
# your actual implementation from AKANGA_SRC.
#
# Phase 02 adds NO new parser functions and NO model changes — the Node and Edge
# dataclasses are identical to Phase 01's (the Node has been the same since Phase 0).
# Your Phase 01 parser works here verbatim.
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
