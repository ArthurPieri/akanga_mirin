# Akanga Mirin — Learning Path

Build a personal knowledge graph from scratch, progressing from flat-file
parsing through graph algorithms, concurrency, REST APIs, and AI integration.
Each phase introduces a systems-level concept and has you implement it in
Python against a real test suite.

**Audience:** learners start at [Phase 0](learning/phase-00-file-system-as-database.md);
contributors should read `CONTRIBUTING.md` in the repository; internal planning
documents are contributor-facing and are not published on this site.

---

## The phases

Complete them in order — each phase builds on the previous.

| Phase | Title | Estimated time |
|---|---|---|
| [Phase 0](learning/phase-00-file-system-as-database.md) | File System as Database | 2–3h |
| [Phase 1A](learning/phase-01a-data-modeling-edge-schema.md) | Data Modeling: Edge Schema and Inline Shorthand | 2–3h |
| [Phase 1B](learning/phase-01b-workspace-and-sync.md) | Data Modeling: Workspace Registry and Background Sync | 2–3h |
| [Phase 2](learning/phase-02-storage-and-indexing.md) | Storage and Indexing | 3–4h |
| [Phase 3](learning/phase-03-graph-algorithms.md) | Graph Algorithms | 2–3h |
| [Phase 4](learning/phase-04-concurrency-and-events.md) | Concurrency and Events | 3–4h |
| [Phase 5](learning/phase-05-terminal-ui.md) | Terminal UI | 12–20h |
| [Phase 6](learning/phase-06-rest-api.md) | REST API | 3–4h |
| [Phase 7](learning/phase-07-version-control.md) | Version Control as a Feature | 2–3h |
| [Phase 8](learning/phase-08-ai-integration.md) | AI Integration (MCP) | 3–4h |

Times are implementation only — budget **~1 hour extra per phase** for the vault
nodes and Reflect prompts. The vault is a deliverable (`make vault-check` enforces
it), not an extra.

---

## Terminology

Three terms appear throughout the docs; here is the canonical meaning of each.

| Term | Means | Where it lives |
|---|---|---|
| **vault** | The directory of `.md` files — the single source of truth. Everything else (SQLite index, TUI, API) is derived from it. | A directory on disk (e.g. `./vault`) |
| **workspace** | A named subgraph of the vault — a way to view and filter a subset of nodes. | Defined under the `workspaces:` key in `akanga.yaml`; a node opts in via the `graph:` key in its frontmatter |
| **content** / **body** | The markdown prose below the YAML frontmatter. The API field `content`, the `Node` dataclass field `content`, and "the markdown body" all name the same thing — the docs use the three terms interchangeably. | Request models, `models.py`, and every `.md` file |

---

## Foundations

Seventeen background explainers, referenced from the phase docs. Read them when a
phase mentions a concept you're not confident about.

- [Asyncio Primer](foundations/asyncio-primer.md) — event loop, coroutines, `run_coroutine_threadsafe`
- [Design Patterns](foundations/design-patterns.md) — Observer, Debounce, Repository, Facade, Labeled Property Graph, Graph Traversal, Anemic Domain Model
- [Direnv Basics](foundations/direnv-basics.md) — per-directory environments with `.envrc`
- [Git Basics](foundations/git-basics.md) — git workflow, GitPython, commits and branches
- [Graph Algorithms Beyond BFS](foundations/graph-algorithms-beyond-bfs.md) — centrality, communities, Adamic-Adar, Personalized PageRank (enrichment)
- [Graph Theory Basics](foundations/graph-theory-basics.md) — your edges table as an adjacency list, recursive-CTE BFS, supernodes
- [HTTP Fundamentals](foundations/http-fundamentals.md) — verbs, status codes, FastAPI, WebSocket, security
- [JSON-RPC Basics](foundations/json-rpc-basics.md) — JSON-RPC 2.0, MCP protocol, FastMCP
- [Makefile Basics](foundations/makefile-basics.md) — targets, variables, phony targets
- [MKDocs Basics](foundations/mkdocs-basics.md) — building and serving this documentation site
- [Python Dataclasses](foundations/python-dataclasses.md) — `@dataclass`, `field()`, frozen, equality
- [Python Threading](foundations/python-threading.md) — threads, Lock, Timer, GIL, debounce
- [Python Type Annotations](foundations/python-type-annotations.md) — type hints, generics, Protocol
- [Relation Vocabulary](foundations/relation-vocabulary.md) — the 72 built-in relation types in 11 categories
- [SQLite Basics](foundations/sqlite-basics.md) — WAL, FTS5, parameterized queries
- [Terminal and tmux Basics](foundations/terminal-and-tmux-basics.md) — shell, tmux, the study session
- [YAML and Markdown Frontmatter](foundations/yaml-and-markdown-frontmatter.md) — YAML, frontmatter, python-frontmatter

There is also an [Observability & Debugging module](observability-module.md)
(structured logging, timing decorators, health endpoints — wired into Phase 4),
plus an [Architecture Overview](architecture-overview.md) and a
[Detailed Architecture Reference](architecture-detailed.md) describing the
system the curriculum builds.

---

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
AKANGA_SRC=./src make test PHASE=0   # run tests against your implementation
```

See `make help` for the full target list.
