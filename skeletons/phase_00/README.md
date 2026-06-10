# Phase 0 — Parser

Implement the four functions in `src/akanga_core/parser.py`
(`parse_node_file`, `content_hash`, `write_node_file`, `create`).

`models.py` is provided — do not modify it. It defines the ONE `Node`
dataclass used unchanged by every later phase (`type` is a plain string:
`"note"` | `"reference"` — there is no enum).

## Running the tests

```bash
# From this directory
PYTHONPATH=src pytest -v
# Or via the repo Makefile
make test PHASE=0
```
