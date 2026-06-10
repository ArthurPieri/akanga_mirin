# Phase 1 — Inline Edges & Sync Queue

Extend `parser.py` with three new functions and implement `sync_queue.py`.

`models.py` is provided — the `Node` is UNCHANGED from Phase 0 (one
monotonic Node for the whole path), and Phase 1A adds the `Edge`
dataclass: `Edge(relation, relation_id, target, target_id)` — THE
frontmatter edge shape used by every later phase. Do not modify it.

The Phase 0 stubs (`parse_node_file`, `content_hash`, `write_node_file`,
`create`) are still present — implement them here again or copy your
Phase 0 solution.

## Running the tests

```bash
# From this directory
PYTHONPATH=src pytest -v
# Or via the repo Makefile
make test PHASE=1
```
