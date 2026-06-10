# Akanga Mirin

> **Status:** Phase docs, skeletons, and test suites are complete for all 9 phases.
> Reference solutions are in progress (Phase 8 only so far). Run `make status` for the live completion matrix.

Akanga Mirin is an open-source, project-based learning path for Python developers who want to understand how real systems are built — not by following a tutorial, but by building one themselves. Across nine phases, you construct a personal, offline-first knowledge graph: from atomic file writes and UUID identity through SQLite indexing, graph algorithms, a Textual TUI, a FastAPI server, GitPython version control, and finally an AI layer using the Model Context Protocol. At the end of every phase, you have a working artifact you can use — not a checkpoint in someone else's codebase.

> **Ship a working artifact at the end of every phase. Your knowledge graph. Your vault. No cloud required.**

---

## What you will build

| Phase | Topic | Artifact delivered | Est. hours |
|---|---|---|---|
| 0 | File System as Database | Atomic writer + UUID-keyed vault parser | 2–3h |
| 1A | Data Modeling — Edge Schema | Typed edge vocabulary, frontmatter schema, write-back | 2–3h |
| 1B | Workspace and Sync | Workspace registry, reference nodes, sync queue | 2–3h |
| 2 | Storage and Indexing | SQLite + WAL + FTS5 full-text search | 3–4h |
| 3 | Graph Algorithms | BFS ego-graph, cycle detection, ASCII renderer | 2–3h |
| 4 | Concurrency and Events | Watchdog file watcher, debounce, EventBus | 3–4h |
| 5 | Terminal UI | Textual three-panel TUI with live graph view | 12–20h |
| 6 | REST API | FastAPI server with WebSocket push events | 3–4h |
| 7 | Version Control | GitPython auto-commit, squash queue, change history | 2–3h |
| 8 | AI Integration | MCP server + Graph RAG (FTS5 seed → BFS context) | 3–4h |

Total: **roughly 35–55 hours ±30%** of hands-on coding for an intermediate Python
developer working alone (more with optional foundation-doc study and vault work).
Per-phase estimates above are realistic learner time, not author time. Phase 5
(Textual TUI) is the steepest; budget 12–20 hours if you have not used Textual before.

> **Fast path.** Want a usable tool sooner? Phase 6 depends only on phases 0–2:
> do **0 → 1A → 1B → 2 → 6**, then come back for 3–5. This is the roadmap's MVP cut —
> roughly 10–14 hours to a working REST API over your own knowledge graph.

---

## Who this is for

**Individual learners.** Python developers (2+ years) who can build a CRUD app but want practical experience with the systems-level concepts that separate junior from senior work — WAL-mode SQLite, asyncio event bridges, BFS traversal, git internals, the Model Context Protocol.

**Workshop facilitators.** Tech leads, bootcamp instructors, senior devs running a 2–4 day curriculum. The repo ships per-phase learning objectives, checkpoint exercises, and a test suite that evaluates participant code objectively. (A dedicated facilitator guide is planned but not yet written.)

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
```

`make help` lists all available targets.

---

## How the learning path works

**Skeleton code.** Each phase starts from a skeleton file — full class and method signatures, type annotations, and WHAT/WHY/HOW docstrings explaining exactly what to implement. Every method body raises `NotImplementedError` with a specific hint. You fill in the implementation.

**Test suite.** A test suite in `tests/phase_NN/` validates your implementation. Point it at your code with the `AKANGA_SRC` environment variable:

```bash
AKANGA_SRC=./src make test PHASE=2
```

If `AKANGA_SRC` is not set, tests will fail with a clear error message telling you to set it. Use `AKANGA_SRC=./src make test PHASE=N` to test your own code.

**Reference solutions.** Reference implementations are being written phase by phase (currently Phase 8 only — run `make status` to see what exists). When a solution exists, `make test-solution PHASE=N` runs the suite against it. Look at solutions after you've written your own version, not before.

**Foundation docs.** `docs/foundations/` has 15 optional explainers (SQLite basics, asyncio primer, git basics, JSON-RPC, and more). Skip them if you already know the topic; read them if you're unfamiliar. They are not blocking prerequisites.

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

Requires: `tmux`, `nvim`, `glow`, `claude` (Claude Code CLI). The script checks for
these and tells you what to install if anything is missing.

For the Phase 5 stretch-goal graph renderer (Kitty graphics + canvas), install the
optional dependency group: `uv sync --extra graph`.

---

## Repository structure

```
akanga_mirin/
├── Makefile                        # all workflows: study, test, lint, serve
├── docs/
│   ├── README.md                   # documentation navigation hub ← start here
│   ├── learning/                   # 10 phase docs (the learning path; Phase 1 is split into 1A + 1B)
│   ├── foundations/                # 15 optional explainer docs
│   ├── implementation-plan.md      # master task list for repo contributors
│   ├── roadmap.md                  # MVP / V1 / V2 / V4+ version plan
│   ├── user-stories.md             # 38 stories across 5 personas
│   ├── observability-module.md     # structured logging, @timed, /health patterns
│   └── deployment.md               # launchd, systemd, tmux deployment guide
├── tests/                          # phase test suites (run against your code)
├── skeletons/                      # starting point for each phase (all 9 phases)
├── solutions/                      # reference implementations (in progress — Phase 8 only)
├── examples/                       # runnable examples per phase (all 9 phases)
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
make vault-init              # create ./vault + canonical akanga.yaml
make vault-check PHASE=2     # validate your vault (per-phase expected nodes)
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
