# User Stories — Akanga Knowledge Graph

This document captures the full product vision for Akanga as user stories. Every story
is tagged with the version in which it is delivered:

- `[MVP]` — parser, indexer, SQLite DB, basic REST API
- `[V1]` — full TUI with graph renderer, WebSocket events, git auto-commit
- `[V2]` — MCP server, Graph RAG, Claude / Claude Code integration
- `[V4+]` — active nodes, diagram nodes, vector embeddings, multi-user vaults, Akanga Cloud

Stories are grouped by persona. A single story may cross multiple concerns; it is
placed under the persona whose primary motivation drives it.

---

## Persona: Developer

A software engineer who captures technical insights, architecture decisions, code
review findings, and project notes as they work. Uses the terminal daily and is
comfortable with CLI tools.

---

**D-01** `[MVP]`
As a developer, I want to capture a technical insight as a Markdown file in my vault
so that the knowledge is preserved in a format I own and can edit in any editor.

**D-02** `[MVP]`
As a developer, I want to link a note to another note using wikilinks or Markdown links
so that related concepts are explicitly connected and discoverable together.

**D-03** `[MVP]`
As a developer, I want to search my vault with a full-text query from the command line
so that I can find any note that contains a term without browsing the file tree.

**D-04** `[MVP]`
As a developer, I want my notes stored as plain Markdown files with YAML frontmatter
so that I can open, edit, and version them with any text editor or git repository,
without vendor lock-in.

**D-05** `[MVP]`
As a developer, I want a REST API over my vault so that I can query and update notes
from scripts, CI pipelines, and other tools I already use.

**D-06** `[V1]`
As a developer, I want a terminal UI where I can browse, search, and edit notes without
leaving the keyboard so that note-taking does not interrupt my flow state.

**D-07** `[V1]`
As a developer, I want to see an ego-graph of a selected node in the TUI so that I can
immediately understand which concepts a note connects to and how deeply.

**D-08** `[V1]`
As a developer, I want every save to my vault automatically committed to git with a
descriptive message so that I have a full edit history I can inspect or revert without
manual discipline.

**D-09** `[V1]`
As a developer, I want rapid saves to the same file debounced into one git commit so
that my history is meaningful (one logical change = one commit) rather than full of
sub-second noise.

**D-10** `[V1]`
As a developer, I want the TUI to reflect file changes made in an external editor
(nvim, VS Code) within one second so that switching between tools does not cause stale
views or data loss.

**D-11** `[V2]`
As a developer, I want Claude to be able to query my knowledge graph via MCP so that
when I ask Claude about a topic I have notes on, it draws on my actual recorded
thinking rather than general training data.

**D-12** `[V2]`
As a developer, I want Claude Code to search my vault and create new nodes from
within a coding session so that insights from code review and debugging are captured
immediately in context.

**D-13** `[V2]`
As a developer, I want the MCP `get_context` tool to return structured typed triples
(not raw text) so that Claude can reason about the explicit relationships in my graph,
not just surface-level word similarity.

**D-14** `[V4+]`
As a developer, I want semantic search over node bodies using vector embeddings so
that queries like "notes about decision-making under uncertainty" return relevant
results even when they use different vocabulary.

**D-15** `[V4+]`
As a developer, I want to define an active node that periodically pings a service URL
and stores the result in the graph so that service health history is part of my
knowledge graph, not a separate monitoring dashboard.

**D-16** `[V4+]`
As a developer, I want to plug Akanga into a LlamaIndex pipeline as a PropertyGraphStore
so that AI applications I build can use my personal knowledge graph as their retrieval
layer.

---

## Persona: Researcher / Knowledge Worker

An academic, analyst, or writer who builds a second brain over months and years.
Cares deeply about the structure of relationships between ideas, not just search.

---

**R-01** `[MVP]`
As a researcher, I want to tag notes with typed edge relations (e.g., `contradicts`,
`supports`, `is_evidence_for`) so that my knowledge graph encodes the intellectual
structure of my thinking, not just a flat list of documents.

**R-02** `[MVP]`
As a researcher, I want each node to store free-form Markdown body content so that
the actual substance of an idea — arguments, quotations, evidence — lives in the same
place as its connections.

**R-03** `[V1]`
As a researcher, I want to view the full vault as a force-directed graph in the TUI
so that I can identify clusters, hubs, and isolated islands in my knowledge base at
a glance.

**R-04** `[V1]`
As a researcher, I want to navigate through backlinks (nodes that link to me) so that
I can discover which ideas are referenced most often and understand the structure of
argument chains.

**R-05** `[V1]`
As a researcher, I want to recover a previous version of a note using git history so
that I can revisit earlier thinking when a line of reasoning evolves or I want to
see what changed.

**R-06** `[V1]`
As a researcher, I want to create a virtual node that represents an external resource
(paper, GitHub repo, website) so that external references participate in my graph's
edge topology without requiring me to copy content into my vault.

**R-07** `[V2]`
As a researcher, I want to ask Claude a multi-hop question ("what does my graph say
about the relationship between System 1 thinking and cognitive bias?") and receive an
answer grounded in my actual typed edges, not a hallucinated synthesis.

**R-08** `[V2]`
As a researcher, I want the Graph RAG context injected into prompts to include
relation labels and node types so that the LLM can distinguish between "A supports B"
and "A contradicts B" rather than treating all connections as equally positive
associations.

**R-09** `[V4+]`
As a researcher, I want to define a diagram node (Mermaid, BPMN) whose source lives
in the vault and renders in the TUI so that visual knowledge (process maps, argument
diagrams) is a first-class citizen of my graph.

**R-10** `[V4+]`
As a researcher, I want Akanga to surface temporal patterns in my editing history
so that I can understand which areas of my knowledge base I am actively developing
versus neglecting.

---

## Persona: Workshop Facilitator

A teacher, trainer, or learning designer who uses Akanga as the subject of a
project-based learning workshop. Participants build Akanga themselves, phase by phase.

---

**F-01** `[MVP]`
As a workshop facilitator, I want each phase of the learning path to have runnable
pytest tests so that participants can verify their implementation is correct at each
checkpoint without needing manual review.

**F-02** `[MVP]`
As a workshop facilitator, I want a reference implementation for each phase so that
participants who get stuck have something concrete to compare against rather than
abandoning the workshop.

**F-03** `[MVP]`
As a workshop facilitator, I want skeleton code files (stubs with docstrings) for each
phase so that participants have a clear entry point and do not spend their time
on boilerplate instead of the core learning objective.

**F-04** `[MVP]`
As a workshop facilitator, I want time estimates on each phase so that I can structure
a multi-session workshop and participants can plan their study time.

**F-05** `[V1]`
As a workshop facilitator, I want each phase to end with reflection prompts so that
participants consolidate their learning and the workshop has explicit debrief
structure.

**F-06** `[V1]`
As a workshop facilitator, I want a "Common Pitfalls" section in each phase so that
I can proactively address the mistakes that consistently block intermediate learners
and avoid losing workshop time to repeated debugging.

**F-07** `[V1]`
As a workshop facilitator, I want a standalone facilitator guide covering session
timing, pairing strategies, and common sticking points per phase so that I can run
the workshop consistently across different cohorts.

**F-08** `[V1]`
As a workshop facilitator, I want micro-example scripts (one concept, ~30 lines,
immediately runnable) for each phase so that visual and hands-on learners can see
a concept work before they build on it.

**F-09** `[V2]`
As a workshop facilitator, I want intermediate checkpoints within the longer phases
(TUI, REST API) so that participants can validate sub-deliverables without waiting
for the full phase to be complete.

**F-10** `[V2]`
As a workshop facilitator, I want a prerequisite foundations library (short explainers
on dataclasses, asyncio, SQLite, etc.) that phase docs link to, so that learners with
gaps can self-remediate without blocking the group.

---

## Persona: AI Agent

An LLM-based agent (Claude, Claude Code, or a custom agent built with the Anthropic
SDK or LlamaIndex) that uses Akanga as its knowledge store.

---

**A-01** `[V2]`
As an AI agent, I want a `get_context` MCP tool that combines FTS search and ego-graph
expansion in a single call so that I can retrieve relevant structured knowledge with
minimal round-trips.

**A-02** `[V2]`
As an AI agent, I want MCP tool responses capped at a defined character limit so that
I do not overflow my context window when the vault is large or the graph is dense.

**A-03** `[V2]`
As an AI agent, I want a `create_node` MCP tool that writes a file to the vault and
indexes it atomically so that insights I generate during a session are durably
persisted to the knowledge graph.

**A-04** `[V2]`
As an AI agent, I want the MCP server instructions to guide me to the correct tool
for each task (and explicitly list anti-patterns) so that I avoid expensive call chains
and use the graph efficiently.

**A-05** `[V2]`
As an AI agent, I want to read a node's raw Markdown via the `akanga://nodes/{id}`
MCP resource URI so that I can access the full body content when the summary returned
by `get_context` is insufficient.

**A-06** `[V2]`
As an AI agent, I want to list all available relation type IDs before adding an edge
so that I create semantically correct relationships rather than freeform strings that
degrade graph quality.

**A-07** `[V4+]`
As an AI agent, I want to query Akanga via a LlamaIndex PropertyGraphStore interface
so that I can be embedded in LlamaIndex pipelines without a custom integration layer.

**A-08** `[V4+]`
As an AI agent, I want seed-node retrieval in Graph RAG to be augmented by vector
embeddings so that my graph context retrieval is robust to paraphrase and vocabulary
variation, not just FTS5 keyword matches.

---

## Persona: Platform Operator

A user or team that runs Akanga as a persistent background service, or who needs to
operate multiple vaults across devices.

---

**O-01** `[V1]`
As a platform operator, I want Akanga to run as an unattended background service
(macOS launchd, Linux systemd) so that the watcher, active manager, and REST API
are always available without a manual start command.

**O-02** `[V2]`
As a platform operator, I want structured JSON logs from Akanga so that I can route
logs to a file, a log aggregator, or a monitoring system without parsing unstructured
text.

**O-03** `[V2]`
As a platform operator, I want a `--verbose` / `--debug` CLI flag so that I can
increase log verbosity for a specific run without changing any configuration file.

**O-04** `[V2]`
As a platform operator, I want a structured health endpoint (`GET /health`) that
reports sub-system status (DB connection, watcher state, git repo) not just a single
200/500 response so that I can diagnose partial failures without log diving.

**O-05** `[V4+]`
As a platform operator, I want vault sync across devices via an Akanga Cloud backend
so that my knowledge graph is available everywhere without manual rsync or git push.

**O-06** `[V4+]`
As a platform operator, I want multi-user vault support with per-user attribution so
that a team can share a knowledge graph while maintaining clear ownership of individual
nodes and edges.

---

## Notes on Scope Boundaries

Stories tagged `[MVP]` are required for Akanga to be a usable personal tool — anything
less is a prototype. Stories tagged `[V1]` make Akanga a daily-use tool for a terminal
user. Stories tagged `[V2]` unlock AI-native workflows that differentiate Akanga from
a plain Zettelkasten tool. Stories tagged `[V4+]` require significant additional design
work (documented in `docs/future-ideas.md`) and are not blocked by the learning path
phases.

The formal version scope boundaries are defined in `docs/roadmap.md`.
