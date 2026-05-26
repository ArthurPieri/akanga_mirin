> **⚠ SUPERSEDED — This document has been replaced.**
> Phase 1 is now split into:
> - [Phase 1A — Data Modeling & Edge Schema](phase-01a-data-modeling-edge-schema.md)
> - [Phase 1B — Workspace Registry & Sync Queue](phase-01b-workspace-and-sync.md)
>
> This file is kept for reference only. Do not use it as the authoritative spec.
> The table schema in this file uses deprecated column names (`title_sync_queue`, `node_id`).
> The current schema uses `sync_queue` and `entity_id`. See Phase 1B for the correct spec.

# Phase 1 — Data Modeling

**Core concept:** Deciding what the data *is* before deciding how to store it. Phase 0
gave you a file with metadata. Phase 1 asks: how do you represent a *connection* between
two nodes as plain text? What does a typed edge look like inside a file? And what happens
when a user writes connections informally in prose, or renames a node that other nodes
reference?

The central decisions are already made from the product discussion. This phase is about
understanding why those decisions were made and building the code that enforces them.

---

## Quick Start

```bash
make skeleton PHASE=1    # copy the starting code into ./src/
make test PHASE=1        # run the tests (they will fail initially)
make study PHASE=1       # open the tmux study session
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### Directed Graph

A graph where edges have direction: A → B is not the same as B → A. "Fast Thinking
`contradicts` Blink" is a different statement than "Blink `contradicts` Fast Thinking."
The direction carries meaning. This matters for traversal (Phase 3) and ego-graph
display: outgoing edges (this node makes a claim about something else) are shown
differently from incoming edges (something else makes a claim about this node).

> Akanga node: `Directed Graph`

### Labeled Property Graph (LPG)

A graph model where edges carry a type label — the relation — rather than being anonymous
connections. "A links to B" is a hyperlink graph. "A *supports* B" is a knowledge graph.
The label is what gives the edge semantic value: you can ask "what does this node
contradict?" or "what does this node depend on?" and get meaningful, filtered answers.
Akanga stores Tier 2 semantics: every edge has a `relation` field drawn from the
71-type vocabulary.

> Akanga node: `Labeled Property Graph`

### Source of Truth

The single authoritative record of a fact. All other copies are derived and expendable.
In Akanga, the frontmatter `edges:` block is the source of truth for a node's
connections. The SQLite index is derived from it. The inline `[[wikilinks]]` in prose
are a convenience shorthand — not authoritative on their own. When there is a conflict
between prose and frontmatter, frontmatter wins. When prose declares an edge not yet
in frontmatter, write-back adds it.

> Akanga node: `Source of Truth`

### Eventual Consistency

A consistency model where replicas of the same data may diverge temporarily but are
guaranteed to converge given enough time and no new updates. In Akanga, inline prose
and the frontmatter `edges:` block can be out of sync between sync events (file save,
TUI open, explicit trigger, schedule). This is acceptable because convergence is
guaranteed — the write-back process will run. The alternative (strong consistency,
where every inline edit immediately updates frontmatter) would require the editor to
be Akanga-aware, which kills the "any text editor" promise.

> Akanga node: `Eventual Consistency`

### Two-Pass Parsing

Parsing an Akanga node requires two distinct passes with different tools. Pass 1:
extract the YAML frontmatter block into structured data — a YAML parser handles this.
Pass 2: scan the Markdown body for inline edge shorthand `[[Target | relation]]` —
a regex handles this. The results are merged and deduplicated. Keeping the passes
separate keeps responsibilities clean: the YAML parser never sees prose, the regex
never sees structured data.

> Akanga node: `Two-Pass Parsing`

### Node Types as Schema Variants

Not all nodes have the same shape. A `note` has a body and edges. A `reference` has
a URL, an external type, and a short description — and may have a minimal body. Both
share the common frontmatter fields (id, title, type, tags, author, created_at,
updated_at, meta, edges). The `type` field determines which additional fields are
expected. This is a schema variant pattern — one base schema, multiple typed extensions.

> Akanga node: `Node Types as Schema Variants`

### Reference Integrity via UUID

Reference integrity is the guarantee that a reference always points to something that
exists and is correctly identified. In a relational database, a foreign key constraint
enforces this at write time — the DB rejects invalid references. In Akanga, enforcing
this at write time is impossible: files are edited by any text editor, outside Akanga's
control.

The UUID is what makes this safe. Every edge stores both `target-id` (UUID, never
changes) and `target` (title, human-readable display cache). When a node is renamed,
the UUID still points to the correct node — the graph remains structurally correct.
Only the `target` display name becomes stale. This is a deliberate tradeoff: human
editability over strict consistency.

**Path changes are free:** No node stores another node's path. Moving a file costs
nothing — the indexer finds it at the new location by UUID and updates the DB. Zero
other files need editing.

**Title changes create stale display names:** When "Blink — Gladwell" is renamed to
"Blink by Malcolm Gladwell", every edge with `target: Blink — Gladwell` has a stale
display name. Not broken — the UUID still resolves correctly — but misleading when a
human reads the raw file. A background sync queue resolves this lazily without blocking
the save path.

> Akanga node: `Reference Integrity`

### Background Sync Queue

A queue of pending work items that are too expensive to execute on the critical path
(file save, TUI render) but must eventually be completed. In Akanga, the sync queue
holds two kinds of jobs: node title changes ("update all edges pointing to node X to
display the new title") and workspace renames ("update the workspace name display
cache in all nodes belonging to workspace Y"). The queue is stored in the DB so it
survives restarts.

The queue decouples *detection* (cheap, happens on every title or workspace rename)
from *execution* (expensive, involves reading and writing multiple files). Triggers
for draining: TUI opens, a specific node is opened (drains only jobs relevant to
that node), explicit sync command, or a background schedule. This keeps
initialization and save times fast regardless of vault size.

> Akanga node: `Background Sync Queue`

### Workspace Registry

Workspaces are named, UUID-identified entities stored in `akanga.yaml` — not in
the vault's node files. This is the same dual-key pattern as edges: `name` is the
human-readable display cache, `id` is the authoritative UUID generated once at
workspace creation and never changed. When a workspace is renamed, only `akanga.yaml`
changes; a sync queue job lazily updates the `name` display field in all node
frontmatter files that belong to that workspace.

The default workspace is **Nhamandu** (Mbya Guaraní: the primordial being whose
unfolding thought gave rise to the cosmos). Its UUID is generated at `akanga init`.
The name is configurable in `akanga.yaml` — changing it enqueues a workspace name
sync job without breaking any node's graph membership.

Every node's `graph` field follows the same structure as edges — `name` + `id`:

```yaml
graph:
  - name: Nhamandu
    id: a3f7c2be-1234-5678-abcd-ef0123456789
  - name: ProjectX
    id: b2c3d4e5-abcd-ef01-2345-678901234567
```

Absent or empty `graph` auto-populates with the default workspace on first
write-back. The universal workspace (Nhamandu) always shows all nodes in the TUI
regardless of `graph` field — named workspaces are additive filters on top.

> Akanga node: `Workspace Registry`

---

## The Edge Format

The canonical frontmatter edge block:

```yaml
edges:
  - relation: contradicts
    relation-id: EP-002
    target: Blink — Malcolm Gladwell
    target-id: d4e1f9cc-5678-1234-efab-012345678901
  - relation: supports
    relation-id: EP-001
    target: Kahneman System 1 and System 2
    target-id: b2c3d4e5-abcd-ef01-2345-678901234567
```

The dual-key pattern applies to both fields:
- `relation` — human-readable display cache; may be stale after a relation rename
- `relation-id` — stable ID from the vocabulary (`EP-002`, `CT-005`, etc.); never changes
- `target` — human-readable title; may be stale after the target node is renamed
- `target-id` — UUID of the target node; stable forever; empty string if unresolved

For custom relation types not in the built-in vocabulary, `relation-id` is a UUID
generated at first use. Built-in IDs use the category-prefix format (`EP-001`…`TC-004`)
— see `docs/foundations/relation-vocabulary.md` for the full table.

**Inline shorthand in prose:** `[[Target Title | relation]]`

On write-back, this becomes an entry in the `edges:` block. `target-id` is resolved
by looking up the title in the DB index — left empty if the target node does not exist
yet (dangling reference, resolved on next sync after the target is created).

**The reference node type** adds three top-level fields:

```yaml
type: reference
url: https://www.example.com
external_type: webpage   # webpage | github | paper | book | api | file
description: Short description of the resource
```

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Directed Graph` | note | `subtype_of` → `Graph`; `contrasts_with` → `Undirected Graph` |
| `Labeled Property Graph` | note | `subtype_of` → `Directed Graph`; `implements` → `Semantic Edge Types` |
| `Source of Truth` | note | `qualifies` → `Frontmatter Edge Block`; `contrasts_with` → `Derived Index` |
| `Eventual Consistency` | note | `qualifies` → `Write-Back Sync`; `contrasts_with` → `Strong Consistency` |
| `Two-Pass Parsing` | note | `is_applied_in` → `Akanga Parser`; `enables` → `Inline Edge Shorthand` |
| `Node Types as Schema Variants` | note | `is_applied_in` → `Node Data Model`; `subtype_of` → `Schema Design Pattern` |
| `Reference Integrity` | note | `qualifies` → `Edge Target Field` |
| `UUID` | note | `solves` → `Reference Integrity` |
| `Background Sync Queue` | note | `solves` → `Stale Title Display`; `solves` → `Stale Workspace Name`; `enables` → `Lazy Sync` |
| `Workspace Registry` | note | `is_part_of` → `Vault Configuration`; `implements` → `Named Graph Scoping`; `uses` → `UUID` |
| `Nhamandu` | note | `subtype_of` → `Guaraní Deity`; `is_applied_in` → `Akanga Default Workspace`; `is_analogous_to` → `Primordial Source` |
| `Akanga` | note | `subtype_of` → `Tupi-Guaraní Word`; `is_applied_in` → `Personal Knowledge Graph Tool`; `has_context` → `Tupi-Guaraní Language` |

### Seed Notes

**Nhamandu** — full body for the vault node:

> Nhamandu (also written Ñamandú or Nhamandu Tenonde, "Our Father Who Comes First")
> is the primordial being in Mbya Guaraní cosmology. Before the cosmos existed,
> Nhamandu unfolded his own thought — and from that thought arose language, then the
> earth, then all living things. He is not a creator who builds from outside, but a
> source from whom existence unfolds from within.
>
> In Akanga, *Nhamandu* is the name of the default universal workspace — the container
> that holds all knowledge before it is organized into named workspaces. Just as
> Nhamandu precedes all things, the Nhamandu workspace encompasses all nodes.
>
> Source: Cadogan, León (1959). *Ayvu Rapyta: Textos míticos de los Mbyá-Guaraní del
> Guairá*. University of São Paulo. The foundational academic text on Mbya cosmology.

**Akanga** — full body for the vault node:

> Akanga is a word from Tupi-Guaraní, one of the most widely spoken indigenous
> language families in South America (Brazil, Paraguay, Bolivia, Argentina). It means
> "head" or "mind" — the seat of thought, knowledge, and identity.
>
> In Tupi-Guaraní languages, the head is not merely an anatomical part but the locus
> of the person's inner life — thought, memory, will. The word appears across the
> Tupi-Guaraní language family with closely related forms.
>
> In this project, *Akanga* is the name of the personal knowledge graph tool: the
> external mind, the structured record of what you know and how things relate.
> The name reflects the core purpose — building a second mind outside your head,
> organized not as documents but as a graph of connected, meaningful relationships.

---

## What You Build

Extensions to `parser.py` from Phase 0, plus a queue module.

**`Edge` dataclass:**

```python
@dataclass
class Edge:
    relation: str      # display cache — human-readable name, may be stale after rename
    relation_id: str   # authoritative ID (e.g. "EP-002") — stable forever
    target: str        # display cache — target node title, may be stale after rename
    target_id: str     # authoritative UUID — stable forever, empty if unresolved
```

The dual-key pattern applies to both the relation and the target: `relation` and
`target` are human-readable display caches; `relation_id` and `target_id` are the
stable machine keys. The relation registry (in `akanga.yaml` or `vocabulary.yaml`)
maps IDs to names, descriptions, and flags (symmetric, inverse pair).

**New functions in `parser.py`:**

| Function | What it does |
|---|---|
| `extract_inline_edges(body) → list[Edge]` | Regex scan for `[[Target \| relation]]`; skips code blocks |
| `merge_edges(existing, inline) → list[Edge]` | Deduplicate: add inline edges not already in existing |
| `write_back(path)` | parse → extract inline → merge → write atomically if changed |

**Deduplication rule:** an edge is a duplicate if `(relation, target)` matches an
existing edge. `target_id` is not part of the key — an empty `target_id` in an inline
edge does not override a resolved `target_id` in frontmatter.

**`create()` extended** to handle reference nodes:

```python
def create(title: str, type: str, vault: Path,
           url: str = "",
           external_type: str = "",
           description: str = "") -> Node:
    ...
```

**`sync_queue.py`** — a new module, two operations at this phase:

| Function | What it does |
|---|---|
| `enqueue_title_sync(db, node_id, new_title)` | Add a pending job when a title change is detected |
| `pending_sync_jobs(db) → list[dict]` | Return all unprocessed jobs — consumed by Phase 4 |

The queue is stored in the DB as a `title_sync_queue` table (defined in Phase 2):

```
title_sync_queue — id, node_id, new_title, enqueued_at, processed_at (nullable)
```

Processing logic — scanning referencing files and updating their `target` fields —
is implemented in Phase 4 alongside the file watcher and event bus.

---

## Deliverable

```python
def test_inline_edge_extraction():
    body = "This idea [[Blink — Gladwell | contradicts]] fast thinking."
    edges = extract_inline_edges(body)
    assert len(edges) == 1
    assert edges[0].relation == "contradicts"
    assert edges[0].target == "Blink — Gladwell"

def test_inline_inside_code_block_ignored():
    body = "```\n[[Some Node | supports]]\n```"
    assert extract_inline_edges(body) == []

def test_merge_deduplicates():
    existing = [Edge(relation="contradicts", target="Blink", target_id="abc")]
    inline   = [Edge(relation="contradicts", target="Blink", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 1            # not doubled
    assert merged[0].target_id == "abc"  # resolved target_id preserved

def test_merge_adds_new_inline_edge():
    existing = [Edge(relation="contradicts", target="Blink", target_id="abc")]
    inline   = [Edge(relation="supports", target="Kahneman", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 2

def test_writeback_roundtrip():
    # File with inline edge in body but empty frontmatter edges block.
    # After write_back(), frontmatter edges block contains the inline edge.
    node = create(title="Test", type="note", vault=tmp_path)
    node.path.write_text(node.path.read_text() + "\n[[Blink | contradicts]]")
    write_back(node.path)
    re_parsed = parse_node_file(node.path)
    # Edges live in frontmatter, not as a dedicated Node field. In Phase 02+,
    # edges are stored in the DB edges table — access them via db.get_neighbors().
    # For Phase 01, read edges from the parsed frontmatter dict:
    edges = re_parsed.frontmatter.get("edges", [])
    assert len(edges) == 1
    assert edges[0]["relation"] == "contradicts"

def test_writeback_is_idempotent():
    node = create(title="Test", type="note", vault=tmp_path)
    node.path.write_text(node.path.read_text() + "\n[[Blink | contradicts]]")
    write_back(node.path)
    write_back(node.path)  # second call must not duplicate the edge
    re_parsed = parse_node_file(node.path)
    edges = re_parsed.frontmatter.get("edges", [])
    assert len(edges) == 1
```

Plus 8 vault nodes with typed edges. The vault is the proof of understanding,
not just the tests.
