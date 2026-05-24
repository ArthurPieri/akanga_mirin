# Akanga Mirin

> **Status:** Sprint 1 of 5 active — tests, skeletons, and solutions are in progress.
> Phase docs and Makefile are complete. Star/watch for updates.

Akanga Mirin is an open-source, project-based learning path for Python developers who want to understand how real systems are built — not by following a tutorial, but by building one themselves. Across nine phases, you construct a personal, offline-first knowledge graph: from atomic file writes and UUID identity through SQLite indexing, graph algorithms, a Textual TUI, a FastAPI server, GitPython version control, and finally an AI layer using the Model Context Protocol. At the end of every phase, you have a working artifact you can use — not a checkpoint in someone else's codebase.

> **Ship a working artifact at the end of every phase. Your knowledge graph. Your vault. No cloud required.**

---

## What you will build

| Phase | Topic | Artifact delivered | Est. hours |
|---|---|---|---|
| 0 | File System as Database | Atomic writer + UUID-keyed vault parser | 2–3h |
| 1 | Data Modeling | Typed edge vocabulary, frontmatter schema, sync queue | 2–3h |
| 2 | Storage and Indexing | SQLite + WAL + FTS5 full-text search | 3–4h |
| 3 | Graph Algorithms | BFS ego-graph, cycle detection, ASCII renderer | 2–3h |
| 4 | Concurrency and Events | Watchdog file watcher, debounce, EventBus | 3–4h |
| 5 | Terminal UI | Textual three-panel TUI with live graph view | 12–20h |
| 6 | REST API | FastAPI server with WebSocket push events | 3–4h |
| 7 | Version Control | GitPython auto-commit, squash queue, change history | 2–3h |
| 8 | AI Integration | MCP server + Graph RAG (FTS5 seed → BFS context) | 3–4h |

Total: **roughly 380 hours ±30%** for an intermediate Python developer working alone.
Per-phase estimates above are realistic learner time, not author time. Phase 5
(Textual TUI) is the steepest; budget 12–20 hours if you have not used Textual before.

---

## Who this is for

**Individual learners.** Python developers (2+ years) who can build a CRUD app but want practical experience with the systems-level concepts that separate junior from senior work — WAL-mode SQLite, asyncio event bridges, BFS traversal, git internals, the Model Context Protocol.

**Workshop facilitators.** Tech leads, bootcamp instructors, senior devs running a 2–4 day curriculum. The repo ships a facilitator guide, per-phase learning objectives, checkpoint exercises, and a test suite that evaluates participant code objectively.

**Engineering teams.** Teams who want to upskill together and end up with a real artifact — a shared knowledge graph of their own architecture, documentation, or projects — rather than slides and notes.

**AI tooling developers.** Developers building MCP servers and Graph RAG pipelines who want a concrete, end-to-end worked example that shows how a knowledge graph is constructed before the AI layer is added. Phase 8 is not an isolated MCP tutorial — it is the final layer on a graph you built yourself.

---

## Quickstart

```bash
git clone https://github.com/ArthurPieri/akanga_mirin
cd akanga_mirin
make setup
make skeleton PHASE=0   # copies Phase 0 skeleton into ./src/
make study PHASE=0      # opens tmux: neovim (left) | phase doc (top-right) | claude (bottom-right)
```

Run the tests against your own code:

```bash
AKANGA_SRC=./src make test PHASE=0    # your code
make test-solution PHASE=0            # reference solution (to compare)
```

`make help` lists all available targets.

---

## How the learning path works

**Skeleton code.** Each phase starts from a skeleton file — full class and method signatures, type annotations, and WHAT/WHY/HOW docstrings explaining exactly what to implement. Every method body raises `NotImplementedError` with a specific hint. You fill in the implementation.

**Test suite.** A test suite in `tests/phase_NN/` validates your implementation. Point it at your code with the `AKANGA_SRC` environment variable:

```bash
AKANGA_SRC=./src make test PHASE=2
```

If `AKANGA_SRC` is not set, the tests automatically fall back to the reference solution — useful for verifying the tests themselves are correct.

**Reference solutions.** `solutions/phase_NN/` contains a complete, working implementation of all phases up to and including phase N. Look at it after you've written your own version, not before.

**Foundation docs.** `docs/foundations/` has 10 optional explainers (SQLite basics, asyncio primer, git basics, JSON-RPC, and more). Skip them if you already know the topic; read them if you're unfamiliar. They are not blocking prerequisites.

---

## Study session

The `study` Makefile target opens a three-pane tmux layout:

```
┌─────────────────────┬──────────────────┐
│                     │  phase doc       │
│   neovim (66%)      │  via glow        │
│   skeleton code     ├──────────────────┤
│                     │  claude code     │
└─────────────────────┴──────────────────┘
```

```bash
make study PHASE=3   # opens Phase 3 in the study layout
```

Requires: `tmux`, `nvim`, `glow`, `claude` (Claude Code CLI).

---

## Repository structure

```
akanga_mirin/
├── Makefile                        # all workflows: study, test, lint, serve
├── docs/
│   ├── learning/                   # 9 phase docs (the learning path)
│   ├── foundations/                # 10 optional explainer docs
│   ├── implementation-plan.md      # master task list for repo contributors
│   ├── roadmap.md                  # MVP / V1 / V2 / V4+ version plan
│   ├── user-stories.md             # 38 stories across 5 personas
│   ├── observability-module.md     # structured logging, @timed, /health patterns
│   ├── deployment.md               # launchd, systemd, tmux deployment guide
│   └── facilitator-guide.md        # workshop facilitation (coming soon)
├── tests/                          # phase test suites (run against your code)
├── skeletons/                      # starting point for each phase (coming soon)
├── solutions/                      # reference implementations (coming soon)
├── examples/                       # runnable examples per phase (coming soon)
├── templates/
│   └── project-makefile            # learner's own project Makefile template
└── scripts/
    ├── study.sh                    # tmux study session script
    └── skeleton_check.py           # verifies skeletons still raise NotImplementedError
```

---

## Makefile reference

```bash
make help                    # full target list

make study PHASE=3           # open study session for Phase 3
make test PHASE=2            # test your code (set AKANGA_SRC first)
make test-solution PHASE=2   # test reference solution
make skeleton PHASE=1        # copy Phase 1 skeleton into ./src/
make lint                    # lint all Python
make check                   # full quality gate (lint + test-all)
```

---

## Out of scope (deliberately)

This learning path is local-first and personal. The following are explicitly out of scope — documented in `docs/future-ideas.md` for later:

- Cloud sync or multi-device
- Multi-user or collaborative vaults
- Docker (no daemon, no container overhead for a personal tool)
- Vector embeddings / semantic search (FTS5 is sufficient for MVP)
- Diagram / canvas nodes and active / executable nodes

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Bug reports and questions in [GitHub Issues](https://github.com/ArthurPieri/akanga_mirin/issues), discussion in [GitHub Discussions](https://github.com/ArthurPieri/akanga_mirin/discussions).

---

## License

MIT
