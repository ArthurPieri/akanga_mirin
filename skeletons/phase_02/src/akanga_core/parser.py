# IMPORTANT — Phase 02 Node shape is DIFFERENT from Phase 01:
#   Phase 01 Node: id=UUID, type=NodeType(StrEnum), has frontmatter/created_at/updated_at, NO content_hash
#   Phase 02 Node: id=str, type=str, has content_hash, NO frontmatter/created_at/updated_at
#
# Do NOT copy your Phase 01 parser verbatim. Key changes required:
#   1. id: generate str(uuid4()) instead of UUID(uuid4())
#   2. type: pass the string directly (not NodeType enum)
#   3. Remove frontmatter=, created_at=, updated_at= from Node(...)
#   4. Add content_hash= (SHA-256 of the body content)
#   5. parse_node_file signature stays the same: (path: str) -> Node

# Copy your Phase 01 solution here, or run with AKANGA_SRC pointing to your Phase 01 src/ directory.
# This file is intentionally left as a reference marker — the skeleton runner picks up
# your actual implementation from AKANGA_SRC.
#
# If you are filling in this file directly, implement (or copy from Phase 01):
#   - parse_node_file(path: str) -> Node
#   - content_hash(path: str) -> str
#   - write_node_file(path: str, frontmatter_dict: dict, content: str) -> None
#
# Phase 02 adds no new parser functions; the Node returned here now uses the
# simpler Phase 02 Node dataclass (with content_hash, without frontmatter/created_at).
#
# See skeletons/phase_01/src/akanga_core/parser.py for the stubs to implement.
