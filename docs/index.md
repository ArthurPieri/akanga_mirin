# Akanga Mirin — Learning Path

Build a personal knowledge graph from scratch in **9 phases**, progressing from flat-file
parsing through graph algorithms, concurrency, REST APIs, and AI integration. Each phase
introduces a systems-level concept and has you implement it in Python against a real test
suite.

## Where to start

- **[Phase 0 — File System as Database](learning/phase-00-file-system-as-database.md)** —
  parse Markdown frontmatter and treat your filesystem as a queryable store.
- **[Foundations](foundations/makefile-basics.md)** — background explainers on SQLite,
  asyncio, dataclasses, direnv, and more.

## Quick setup

```bash
make setup          # install dependencies via uv
direnv allow        # activate the virtual environment automatically
make docs-serve     # browse the learning path at localhost:8000
```

## Learning workflow

```bash
make study PHASE=0          # open a three-pane tmux session
make skeleton PHASE=0       # copy starter code into src/
make test PHASE=0           # run tests against your implementation
```

See `make help` for the full target list.
