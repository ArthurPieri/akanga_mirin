# Architecture Overview

> **Derived reference.** This document summarizes the system the curriculum builds.
> On any conflict, the phase docs (`docs/learning/`) and the skeletons
> (`skeletons/phase_NN/`) are authoritative — fix this document, not your code.

## Introduction

Akanga is a personal knowledge graph where the file system is the database. Markdown
files with YAML frontmatter are the single source of truth for all knowledge. Every
other component in the system -- the SQLite index, the terminal UI, the REST API, the
AI integration -- is derived from those files and is fully expendable. Delete the
database, and it rebuilds from the vault. Delete the UI, and the knowledge remains
intact on disk. This "file-first" philosophy is the foundational design decision from
which every other architectural choice follows.

The practical consequence of file-first design is that the system must watch the
filesystem, react to changes, parse Markdown into structured data, and keep a derived
index in sync -- all without ever treating the index as authoritative. The user edits
files with any text editor they prefer. The system observes, indexes, and presents
what it finds. It never writes to the vault on behalf of its own internal bookkeeping;
files are written only when the user explicitly creates or edits a note through one of
the interface layers.

The architecture is layered into five distinct tiers, each depending only on the
layers below it. This layering is not incidental -- it mirrors the nine build phases
of the curriculum. Learners construct the storage and core layers first (Phases 0-3),
add concurrency and event handling next (Phase 4), build interface layers on top
(Phases 5-7), and cap it off with AI integration (Phase 8). The result is a system
that grows from a simple file parser to a full knowledge graph application with
real-time updates, a REST API, and Claude integration.

The system is designed for a single trusted user on a single machine. There is no
multi-user authentication, no cloud sync, and no remote access. This constraint
simplifies the architecture considerably and keeps the security surface small, while
still teaching real-world patterns like pub/sub messaging, thread-async bridging, and
crash-safe file I/O.

---

## Layers

| Layer | Components | Phase(s) | Responsibility |
|---|---|---|---|
| **Storage** | Vault (Markdown files), SQLite (WAL + FTS5) | 0, 2 | Persistent state: files as truth, DB as derived index |
| **Core Library** | Parser, Node/Edge models, Indexer, Links, Graph algorithms | 0, 1, 2, 3 | Data structures, parsing, querying, traversal |
| **Runtime Services** | EventBus, VaultWatcher, Debouncer, GitManager | 4, 7 | Concurrency, event routing, filesystem observation, versioning |
| **Interface** | Terminal UI (Textual), REST API (FastAPI + WebSocket) | 5, 6 | User-facing presentation and interaction |
| **AI** | RAG Context Builder, MCP Server (FastMCP) | 8 | LLM integration via structured context and tool exposure |

Each layer communicates downward through direct function calls and upward through the
EventBus pub/sub mechanism. No layer reaches into the internals of a layer above it.

---

## Design Philosophy

- **File-first.** Files are the record of truth, not a cache of some other store. The
  SQLite database can be deleted and rebuilt from the vault at any time. The files are
  never derived from the database.

- **Layered independence.** Each architectural layer depends only on layers beneath it.
  The TUI does not know about the REST API. The REST API does not know about the MCP
  server. Both query the same database and subscribe to the same EventBus.

- **Observer pattern.** Components communicate through EventBus pub/sub rather than
  direct method calls. The VaultWatcher does not call the Parser directly -- it
  publishes a `file_changed` event, and any interested subscriber reacts independently.

- **Atomic operations.** File writes use the tempfile-plus-rename pattern
  (`tempfile.NamedTemporaryFile` followed by `os.replace`) to guarantee crash safety.
  A power failure mid-write leaves either the old file or the new file on disk, never a
  half-written corrupted file.

- **Thread-async bridge.** The filesystem watcher (watchdog) runs in OS threads, while
  the TUI (Textual) and REST API (FastAPI) run in asyncio event loops. The EventBus
  bridges these two worlds using `asyncio.run_coroutine_threadsafe(coro, loop)` to
  submit coroutines from thread callbacks to the registered loop. The loop must be
  registered via `set_loop()` before the watcher starts; events that arrive for async
  subscribers before the loop is set are buffered and replayed once it is registered,
  closing the startup race.

- **Security by default.** FTS5 search queries wrap user-supplied terms in double
  quotes to prevent operator injection. File path operations use
  `Path.resolve().is_relative_to()` to block path traversal. The MCP server binds to
  `127.0.0.1` only, never `0.0.0.0`.

---

## Key Abstractions

### Node

The fundamental unit of knowledge. A Node represents a single Markdown file parsed
into structured fields: `id` (a UUID string), `title`, `type` (`"note"` or
`"reference"`), `tags`, `content_hash` (for change detection), `content` (the
Markdown prose — kept on disk, never persisted in the database), `path` (relative to
the vault root), and `frontmatter` (the YAML metadata dictionary). The UUID is
assigned at creation and stored in the frontmatter, giving each node an immutable
identity that survives file renames and directory moves.

### Edge

A typed, directed relationship between two nodes. The **primary edge mechanism is
the frontmatter `edges:` block** — each entry stores the dual keys `relation` +
`relation-id` and `target` + `target-id`. The inline wiki-link syntax
`[[Target|relation]]` is the *capture* shorthand: edges written informally in prose
are extracted and merged into the frontmatter block, which remains the source of
truth. The system ships 72 built-in relation types organized into 11 semantic
categories (Epistemic/Reasoning, Hierarchical/Taxonomic, Structural/Compositional,
Causal/Temporal, Attribution/Provenance, Documentary/Reference,
Comparative/Contrastive, Evolutionary/Versioning, Personal/Associative,
Social/Organizational, and Topical/Classification), each with a stable prefix-code
identifier (e.g., `EP-001` for "supports"). The full registry is
`docs/foundations/relation-vocabulary.md`. Custom relation types are also permitted
and assigned UUIDs at creation.

### Vault

The directory tree of Markdown files that constitutes the knowledge graph's source of
truth. The vault is human-readable, git-diffable, and tool-agnostic -- any text editor
can create and modify notes. The system imposes no proprietary format beyond standard
YAML frontmatter and wiki-link syntax. All file paths within the system are resolved
relative to the vault root and confined to it.

### Database

A derived SQLite index (`class GraphDatabase`, schema created in `__init__`)
operating in WAL (Write-Ahead Logging) mode for concurrent read access. It contains
four primary structures: a `nodes` table (metadata only — id, path, title, type,
tags, content_hash), an `edges` table (TEXT UUID ids, `relation` + `relation_id`),
a `nodes_fts` external-content FTS5 virtual table indexing **title and tags only**,
and a `sync_queue` table for deferred background jobs. The node's prose body is
**never stored in the database** — it stays on disk and is read from the vault when
needed. The FTS index is maintained explicitly inside `upsert_node` and
`delete_node` (FTS5 external-content `'delete'` + insert, in the same transaction).
The database is entirely expendable -- deleting it and re-indexing the vault
produces an identical result.

### EventBus

A thread-safe, in-process pub/sub message bus that decouples all components. Backed
by a `defaultdict(list)` of subscribers protected by a `threading.Lock`, it supports
three core operations: `subscribe`, `unsubscribe`, and `publish`. When an asyncio
event loop is registered via `set_loop`, the EventBus dispatches async handlers
using `asyncio.run_coroutine_threadsafe`; events that arrive for async subscribers
before `set_loop` is called are buffered and replayed once the loop is registered.
Key event types include `file_changed`, `file_deleted`, and `node_updated`.

### AkangaApp

The top-level orchestrator that wires every component together. AkangaApp owns the
Database, EventBus, VaultWatcher, and GitManager instances. On startup, it subscribes
to file events and coordinates the core pipeline: a file change triggers a parse, the
parse produces Node and Edge objects, those objects are upserted into the database
(which synchronizes the FTS index inside the same transaction), and the EventBus
notifies downstream consumers (TUI, API, git). AkangaApp is the single entry point
that interface layers delegate to.

---

## Data Flow

The system has two primary data paths: the **write path** (file changes flowing inward)
and the **read path** (queries flowing outward).

### Write Path

A user edits a Markdown file in their editor and saves it. The operating system emits a
filesystem event (inotify on Linux, FSEvents on macOS). The VaultWatcher captures this
event and forwards it to the Debouncer, which coalesces rapid successive events into a
single notification after a 500-millisecond quiet period. The debounced event is
published to the EventBus as `file_changed`. The indexing pipeline subscribes to this
event, reads the file, extracts the Node and its Edges, and upserts them into the
SQLite database; `upsert_node` synchronizes the FTS5 index in the same transaction.
In parallel, the GitManager subscribes to the same event and stages an auto-commit if
git integration is enabled.

### Read Path

Queries originate from the TUI, REST API, or MCP server. Full-text search hits the
FTS5 virtual table (title + tags). Graph traversals (BFS ego-graph) walk the edges
table from a seed node. The RAG Context Builder
(`build_context(node, db, vault, max_triples=80)`) reads the node's body from disk,
runs a BFS traversal, collects triples serialized in natural direction
(`Source --[relation]--> Target`), and assembles them into a bounded context string
(capped at `MAX_CONTEXT_CHARS = 12_000`) wrapped in `[KNOWLEDGE GRAPH CONTEXT]`
delimiters. The MCP server exposes this as tool calls (`search_nodes`, `get_node`,
`list_relation_types`, `get_context`, `create_node`) that Claude can invoke during a
conversation.

---

## System Boundaries

**Vault boundary.** All file operations are confined to the vault directory. Path
arguments are resolved to absolute paths and validated with `Path.resolve().is_relative_to()`
before any read or write. Symlinks that escape the vault root are rejected.

**Network boundary.** The MCP server uses HTTP transport bound exclusively to
`127.0.0.1` (default port 8001). The REST API defaults to localhost. Neither service is intended for network exposure, and there is no
authentication layer -- by design, the threat model assumes a single trusted local user.

**Query boundary.** User-supplied search terms passed to FTS5 are wrapped in double
quotes to neutralize FTS5 operator syntax (AND, OR, NOT, NEAR, column filters). This
prevents query injection through the search interface (SEC-06).

**Trust boundary.** All external input -- file content from the vault, search queries
from the user, context passed to the LLM -- is validated or sanitized before use. The
RAG context builder uses explicit `[KNOWLEDGE GRAPH CONTEXT]` delimiters to separate
graph data from the LLM prompt, reducing the surface for prompt injection.

---

## Diagrams Reference

The following diagram source files provide visual representations of this architecture.
They are written in DDSL (a declarative diagram DSL) and can be rendered with the
project's diagram tooling.

- `diagram/dsl/akanga-system-components.ddsl` -- High-level system components grouped
  by architectural layer, showing the major modules and their interconnections.

- `diagram/dsl/akanga-architecture.ddsl` -- Detailed class-level architecture showing
  fields and methods for each component, ownership relationships, and delegation paths.

- `diagram/dsl/akanga-data-flow.ddsl` -- The write path and read path through the
  system, from user file edits through the processing pipeline to consumer endpoints.

- `diagram/dsl/akanga-phase-progression.ddsl` -- How the system grows across the nine
  build phases, mapping each phase to its architectural layer and showing dependencies
  between phases.
