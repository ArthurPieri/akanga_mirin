# Akanga Mirin — Documentation Index

This directory contains all documentation for the akanga_mirin learning path.
Navigate to the section that matches where you are.

---

## Learning Path (docs/learning/)

The core curriculum — 9 phases building a personal knowledge graph from scratch.

| Phase | Title | Estimated Time |
|---|---|---|
| [Phase 0](learning/phase-00-file-system-as-database.md) | File System as Database | 4–6h |
| [Phase 1A](learning/phase-01a-data-modeling-edge-schema.md) | Data Modeling: Edge Schema | 6–8h |
| [Phase 1B](learning/phase-01b-workspace-and-sync.md) | Data Modeling: Workspace & Sync | 4–6h |
| [Phase 2](learning/phase-02-storage-and-indexing.md) | Storage and Indexing | 8–12h |
| [Phase 3](learning/phase-03-graph-algorithms.md) | Graph Algorithms | 6–10h |
| [Phase 4](learning/phase-04-concurrency-and-events.md) | Concurrency and Events | 8–12h |
| [Phase 5](learning/phase-05-terminal-ui.md) | Terminal UI | 12–20h |
| [Phase 6](learning/phase-06-rest-api.md) | REST API | 8–12h |
| [Phase 7](learning/phase-07-version-control.md) | Version Control | 4–6h |
| [Phase 8](learning/phase-08-ai-integration.md) | AI Integration (MCP) | 8–12h |

**Total estimated time:** 68–104 hours of focused implementation work (380h ±30% including study).

---

## Foundation Docs (docs/foundations/)

Short reference docs covering concepts used across multiple phases. Read these when the phase doc mentions a concept you're not confident about.

| Doc | Covers |
|---|---|
| [asyncio-primer.md](foundations/asyncio-primer.md) | asyncio event loop, coroutines, run_coroutine_threadsafe |
| [design-patterns.md](foundations/design-patterns.md) | Observer, Debounce, Repository, Atomic Write, Facade, DI |
| [git-basics.md](foundations/git-basics.md) | git workflow, GitPython, commits and branches |
| [http-fundamentals.md](foundations/http-fundamentals.md) | HTTP verbs, FastAPI, status codes, WebSocket |
| [json-rpc-basics.md](foundations/json-rpc-basics.md) | JSON-RPC 2.0, MCP protocol, FastMCP |
| [makefile-basics.md](foundations/makefile-basics.md) | Makefile targets, variables, phony targets |
| [python-dataclasses.md](foundations/python-dataclasses.md) | @dataclass, frozen, __eq__, field() |
| [python-threading.md](foundations/python-threading.md) | threads, Lock, Timer, GIL, debounce |
| [python-type-annotations.md](foundations/python-type-annotations.md) | type hints, generics, Protocol |
| [relation-vocabulary.md](foundations/relation-vocabulary.md) | 71 built-in relation types, 11 categories |
| [sqlite-basics.md](foundations/sqlite-basics.md) | SQLite, WAL, FTS5, parameterized queries |
| [terminal-and-tmux-basics.md](foundations/terminal-and-tmux-basics.md) | terminal, tmux, AKANGA_SRC, study session |
| [yaml-and-markdown-frontmatter.md](foundations/yaml-and-markdown-frontmatter.md) | YAML, frontmatter, python-frontmatter library |

---

## Planning & Design (docs/)

| Doc | Contents |
|---|---|
| [implementation-plan.md](implementation-plan.md) | Sprint plan, bug analysis, design decisions |
| [adversarial-analysis.md](adversarial-analysis.md) | Security and architectural risk analysis |
| [deployment.md](deployment.md) | tmux, launchd, systemd deployment options |
| [user-stories.md](user-stories.md) | User journey and product requirements |

---

## Examples (examples/)

Standalone runnable scripts demonstrating one concept per phase:

| Script | Demonstrates |
|---|---|
| [phase_00_atomic_writer.py](../examples/phase_00_atomic_writer.py) | Atomic write pattern |
| [phase_01_edge_parsing.py](../examples/phase_01_edge_parsing.py) | Inline edge extraction |
| [phase_02_sqlite_wal.py](../examples/phase_02_sqlite_wal.py) | WAL mode + threading |
| [phase_03_bfs_ego_graph.py](../examples/phase_03_bfs_ego_graph.py) | BFS with cycle detection |
| [phase_04_debounce_timer.py](../examples/phase_04_debounce_timer.py) | Debounce pattern |
| [phase_05_textual_basics.py](../examples/phase_05_textual_basics.py) | Minimal Textual app |
| [phase_06_fastapi_basics.py](../examples/phase_06_fastapi_basics.py) | FastAPI CRUD |
| [phase_07_git_manager.py](../examples/phase_07_git_manager.py) | Non-fatal GitPython |
| [phase_08_rag_context.py](../examples/phase_08_rag_context.py) | RAG context with SEC-01 |
