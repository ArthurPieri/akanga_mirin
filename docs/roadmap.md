# Akanga — Version Roadmap

This document formally defines the scope boundaries for each Akanga release. It is
the authoritative answer to "what ships when?" For the full feature rationale see
`docs/future-ideas.md`. For user value statements see `docs/user-stories.md`.

---

## How to Read This Document

Each version section answers four questions:
1. **Problem solved** — what user pain does this version eliminate?
2. **Scope in** — what is explicitly included?
3. **Scope out** — what is explicitly excluded (and deferred to which version)?
4. **Done criteria** — how do we know this version is complete?

Then: what makes the next version possible.

---

## MVP — "It Works, I Own It"

### Problem Solved

A developer has good ideas during technical work but loses them: insights from code
review, architecture decisions, reading notes. Existing tools (Notion, Obsidian) are
either cloud-dependent, proprietary, or lack a structured relationship model. MVP
gives them a local, plain-file, git-backed note system with explicit typed connections
between notes — and a programmable REST API so scripts and other tools can read and
write to it.

### Scope In

| Component | What it delivers |
|---|---|
| Parser (`parser.py`) | Read and write `.md` files with YAML frontmatter atomically. Generate UUIDs. Compute content hashes. |
| Schema (`schema.py`) | `Node` and `Edge` dataclasses. 72 typed relation vocabulary. |
| DB (`db.py`) | SQLite with WAL mode, FTS5 full-text search. CRUD for nodes and edges. Thread-safe via `threading.Lock`. |
| Indexer (`indexer.py`) | Two-pass vault walk: index nodes, then extract edges from wikilinks and Markdown links. |
| Links (`links.py`) | Wikilink and Markdown link extraction. Case-insensitive title resolution. |
| REST API (`server.py`) | Full CRUD: nodes, edges, neighbors, backlinks, active results, templates. FastAPI + lifespan context. |
| CLI (`cli.py`) | `index`, `serve`, `version` commands. `--vault`, `--db` flags. |
| Security | Parameterized SQL queries. Path traversal protection. YAML safe loader. Localhost-only default binding. |

**Phases covered:** Phase 0 through Phase 2, Phase 6 (basic).

**Learning path deliverable:** A learner completing Phases 0–2 and 6 has a working
personal knowledge graph with a REST API. This is the MVP.

### Scope Out

| Feature | Deferred to |
|---|---|
| Terminal UI | V1 |
| Git auto-commit | V1 |
| File watcher / live updates | V1 |
| Active nodes (health checks) | V4+ |
| MCP server | V2 |
| Graph RAG | V2 |
| Vector embeddings | V4+ |
| Multi-user vaults | V4+ |
| Akanga Cloud sync | V4+ |

### Done Criteria

- `pytest tests/phase_00/ tests/phase_01/ tests/phase_02/ tests/phase_06/` pass with
  no skips on a clean checkout.
- `uv run python -m akanga_core.cli index --vault ./vault` indexes a 50-node vault in
  under 2 seconds.
- `uv run python -m akanga_core.cli serve` starts the API and `GET /api/v1/nodes`
  returns correctly paginated results.
- All DB queries use parameterized SQL (no string interpolation).
- Path traversal on `POST /api/v1/nodes` with `../` payload returns 400.

### What Enables V1

The REST API (MVP) provides the programmatic interface the WebSocket notification
layer (V1) extends. The SQLite DB (MVP) provides the stable storage layer the file
watcher (V1) and git manager (V1) write to. The `EventBus` (Phase 4 / V1) requires
the indexer (MVP) as its primary subscriber.

---

## V1 — "My Daily Driver"

### Problem Solved

The MVP requires a terminal window and a curl command to interact with notes. A
knowledge graph tool that requires HTTP calls is not a daily-use tool — it is an
API. V1 makes Akanga a first-class terminal application: a TUI you open, search,
navigate, and edit from without leaving the keyboard, with every change automatically
tracked in git.

### Scope In

| Component | What it delivers |
|---|---|
| TUI (`akanga_tui/`) | Three-panel Textual layout: node tree, Markdown content, detail (edges, backlinks). Keybindings: `/` search, `e` edit, `n` new, `d` delete, `g` ego-graph, `G` vault graph, `?` help. |
| Graph renderer | Force-directed ego-graph and full vault graph. Two-layer design: ASCII fallback + Kitty/Ghostty graphics protocol layer. |
| File watcher (`watcher.py`) | watchdog observer. Debounce (500ms). Ignores hidden dirs and editor temp files. Publishes to EventBus. |
| EventBus (`eventbus.py`) | Thread-safe pub/sub. `run_coroutine_threadsafe` bridge. Subscriber error isolation. |
| Git manager (`gitmgr.py`) | Auto-commit on file change (debounced 5s). Change queue + squash. Non-fatal. GitPython wrapper. |
| WebSocket push (`/ws`) | Server-sent events to connected clients on node updates. `ConnectionManager` in `server.py`. |
| Virtual nodes | `type: virtual` with `url`, `external_type`, `description`. Participate in graph topology normally. |
| `tui` CLI command | `uv run python -m akanga_core.cli tui --vault ./vault --db ./.akanga.db` |
| Deployment | macOS launchd plist, Linux systemd user service, `make serve` target. Documented in `docs/deployment.md`. |
| Observability | Python `logging` wired into EventBus. `--verbose` flag on all CLI commands. Documented in `docs/observability-module.md`. |

**Phases covered:** Phase 3 (graph algorithms), Phase 4 (concurrency and events),
Phase 5 (TUI), Phase 7 (version control).

**Learning path deliverable:** A learner completing all phases through 7 has a fully
usable local knowledge graph tool.

### Scope Out

| Feature | Deferred to |
|---|---|
| MCP server | V2 |
| Graph RAG / AI context injection | V2 |
| Active nodes (health checks, code execution) | V4+ |
| Diagram/canvas nodes | V4+ |
| Vector embeddings | V4+ |
| Node size weighting by connection count | V4+ |
| Temporal graph animation (git history replay) | V4+ |
| Multi-user vaults | V4+ |
| Akanga Cloud sync | V4+ |
| Mobile / web client | V4+ |

### Done Criteria

- `pytest tests/` (all phases) pass on a clean checkout.
- TUI opens in under 1 second on a 200-node vault.
- File saved in external editor reflects in TUI within 1 second.
- 10 rapid saves to the same file produce exactly 1 git commit (debounce proof).
- `g` key in TUI renders an ego-graph. `G` key renders the vault graph.
- `?` key displays the keyboard shortcut cheatsheet.
- Akanga starts as a launchd service on macOS: `launchctl list | grep akanga` shows
  the service running.

### What Enables V2

The EventBus (V1) provides the notification infrastructure the MCP server's write
tools can publish to. The REST API (MVP) + WebSocket layer (V1) make the server
stateful enough to serve AI agents. The git history (V1) provides the provenance
layer Graph RAG can reference.

---

## V2 — "AI-Native"

### Problem Solved

V1 is a great personal tool, but an island — AI assistants like Claude have no way
to access the graph. A researcher asking Claude about a topic gets general training
data, not their own recorded thinking. V2 opens Akanga to AI agents via MCP, and
builds Graph RAG so that any LLM integration returns answers grounded in the user's
typed knowledge graph rather than hallucinated synthesis.

### Scope In

| Component | What it delivers |
|---|---|
| MCP server (`akanga_mcp/`) | FastMCP server. Tools: `get_context`, `search_nodes`, `get_node`, `get_neighbors`, `ego_graph_tool`, `create_node`, `list_relation_types`. Resource: `akanga://nodes/{id}`. |
| Graph RAG (`rag.py`) | FTS5 seed search → BFS ego-graph → triple serialization → prompt-ready string. Depth 2 default, capped at 200 triples. |
| MCP instructions | Server instructions string embedded in `initialize` response. Guides LLM tool selection. Anti-pattern list. |
| `mcp-server` CLI command | `--transport stdio` (Claude Desktop) and `--transport http` (remote agents). |
| Output size limits | All MCP tool responses capped at 15,000 chars. Graceful truncation with indication. |
| Structured observability | JSON log formatter. `GET /health` endpoint with sub-system status (DB, watcher, git). |

**Phase covered:** Phase 8 (AI integration).

**Learning path deliverable:** A learner completing Phase 8 has an MCP server usable
from Claude Desktop and a Graph RAG function usable in any Python AI application.

### Scope Out

| Feature | Deferred to |
|---|---|
| LlamaIndex PropertyGraphStore connector | V4+ |
| Vector embeddings (semantic seed retrieval) | V4+ |
| Active nodes | V4+ |
| Diagram nodes | V4+ |
| Relation inference (transitivity) | V4+ |
| Multi-user vaults | V4+ |
| Akanga Cloud sync | V4+ |

### Done Criteria

- `pytest tests/phase_08/` passes on a clean checkout.
- Claude Desktop, configured with the MCP entry, can call `get_context` and receive
  a structured triple block containing at least one typed edge.
- `get_context` on a 100-node vault with 200 edges returns in under 500ms.
- All MCP tool responses are under 15,000 characters when the vault is large.
- `GET /health` returns a JSON body with `db`, `watcher`, and `git` sub-system fields.
- `--verbose` flag on `mcp-server` command writes DEBUG-level logs to stderr.

### What Enables V4+

The MCP server (V2) is the AI agent interface that active nodes and diagram nodes will
publish results through. Graph RAG (V2) is the retrieval foundation that vector
embeddings improve. The FTS5 + BFS architecture survives into V4+ without structural
change — embeddings add a parallel retrieval path, not a replacement.

---

## V4+ — "Platform"

### Problem Solved

V2 is a powerful single-user, single-device tool. V4+ makes Akanga a platform:
multi-device sync, collaborative vaults, executable nodes that generate graph content
autonomously, visual diagram nodes, and LlamaIndex integration for developers building
AI applications. These features require significant additional design (see
`docs/future-ideas.md`) and are not blocked by the learning path phases.

### Scope In (indicative, requires separate design documents)

| Feature | Status |
|---|---|
| Active nodes (HTTP health checks, TCP, code execution) | Design questions documented in `future-ideas.md`. |
| Diagram/canvas nodes (Mermaid, BPMN, architecture diagrams) | Requires two-layer graph renderer (V1) to be stable first. |
| Graph visualisation enhancements (node sizing, gravity weighting, edge colour by relation category) | Requires two-layer renderer + 50+ node vault. |
| Temporal animation (graph evolution via git history replay) | Requires git history integration (V1) and renderer stability. |
| Vector embeddings / semantic search (`sentence-transformers` over node bodies) | Can be added without changing Phase 1–8 architecture. FTS5 + BFS remains the primary retrieval path. |
| LlamaIndex PropertyGraphStore connector | Requires stable REST API (MVP) and MCP server (V2) as design reference. |
| Akanga Cloud sync | Requires conflict resolution model (CRDTs or git-based). Entirely separate infrastructure concern. |
| Multi-user / collaborative vaults | Requires auth, access control, and a conflict model. Incompatible with single-SQLite architecture without significant rework. |
| Mobile / web client | REST API (MVP) is the foundation; client is out of scope for the learning path. |
| Relation inference (transitive, symmetric) | `symmetric` and `inverse_id` fields in Phase 1 are the foundation; full transitivity is a research problem. |

### Done Criteria

V4+ features ship as independently versioned extensions with their own acceptance
criteria, defined at the time each feature moves from the parking lot to active design.

### What Enables V5+

Not yet defined. The V4+ features — especially multi-user vaults and Akanga Cloud —
will surface the requirements for a V5 that this document does not attempt to
anticipate.

---

## Summary Table

| Version | Core Value | Key Phases | Done When |
|---|---|---|---|
| MVP | Own your notes, query them via API | 0, 1, 2, 6 | Tests pass, API serves, SQL is parameterized |
| V1 | Daily-use TUI + git memory | 3, 4, 5, 7 | TUI opens fast, watcher live, git auto-commits, launchd service runs |
| V2 | AI-native: MCP + Graph RAG | 8 | Claude calls `get_context`, response is typed triples, health endpoint structured |
| V4+ | Platform: sync, collab, active/diagram nodes | Post-learning-path | Per-feature criteria defined at design time |
