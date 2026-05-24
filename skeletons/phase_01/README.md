# Phase 1 — Inline Edges & Sync Queue

Extend `parser.py` with three new functions and implement `sync_queue.py`.

`models.py` is provided — it now includes the learning-path `Edge` dataclass
(different from Phase 0's Edge). Do not modify it.

The Phase 0 stubs (`parse_node_file`, `content_hash`, `write_node_file`) are
still present — implement them here again or copy your Phase 0 solution.

## Running the tests

```bash
# From this directory
PYTHONPATH=src pytest -v
# Or via the repo Makefile
make test PHASE=1
```
