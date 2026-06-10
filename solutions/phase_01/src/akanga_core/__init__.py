"""Akanga core — Phase 1 reference solution (1A: edge schema, 1B: sync queue).

This package is the Phase 1 snapshot of the learning path's reference
implementation. It contains everything Phase 0 had (the parser round-trip:
parse → write → parse) plus the two Phase 1 additions:

- **1A** — the `Edge` dataclass, inline-edge extraction from prose
  (`[[Target | relation]]`), the merge rule (frontmatter wins), and the
  `write_back()` pipeline that syncs inline edges into frontmatter.
- **1B** — reference nodes (`type: reference` with `url` / `external_type` /
  `description`) and the SQLite-backed sync queue that defers rename
  propagation off the save path.
"""
from .models import Edge, Node

__all__ = ["Edge", "Node"]
