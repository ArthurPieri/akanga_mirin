# Phase 2 — Storage and Indexing

Implement the database layer and vault indexer.

`models.py` is provided (Phase 02 variant — lighter Node with `content_hash`).
`parser.py` and `sync_queue.py` are reference markers — copy your Phase 01
solution into them, or set `AKANGA_SRC` to your Phase 01 `src/` directory.

## Files to implement

| File | Functions |
|---|---|
| `src/akanga_core/db.py` | `GraphDatabase.__init__`, `upsert_node`, `delete_node`, `get_node`, `list_nodes`, `search_fts`, `upsert_edge`, `get_neighbors`, `get_backlinks` |
| `src/akanga_core/indexer.py` | `scan_vault`, `index_file`, `full_scan_and_index` |
| `src/akanga_core/links.py` | `extract_wikilinks`, `resolve_wikilink` |

## Key concepts

- **WAL mode** — enables concurrent reads without blocking writes.
- **FTS5** — SQLite's full-text search extension. Content tables require manual
  sync on upsert and delete.
- **Two-pass indexing** — nodes first, edges second, so wikilink targets always
  exist when edge resolution runs.
- **SEC-06 (FTS5 operator injection)** — always double-quote FTS5 query terms.

## Running the tests

```bash
# From this skeleton directory (point AKANGA_SRC at the inner akanga_core package)
AKANGA_SRC=./src/akanga_core pytest -v
# Or via the repo Makefile (from the repo root)
AKANGA_SRC=./skeletons/phase_02/src/akanga_core make test PHASE=2
```
