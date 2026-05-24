# Knowledge Graph Theory and Cross-Cutting Integration
## Implementation Plan — Section: K1, K2, K3 + Integration Analysis

_Pre-implementation planning artifact. All items below are ready to be applied directly to the phase documents. No items here have been implemented yet._

---

## Part 1 — K1: "Extending the Vocabulary" Section Content

### Target location

`docs/learning/phase-01-data-modeling.md` — new section added after the "The Edge Format" block and before "Vault Nodes to Create".

---

### Section text (complete, ready to insert)

---

### Extending the Vocabulary

The 71 built-in relation types are not a ceiling — they are a starting point. Akanga is designed so that adding new relation types to your vault is safe, reversible, and does not break existing edges. This section explains exactly what the schema contains, what safe extension looks like, and what makes a change dangerous.

#### How relation types are defined

Relation types live in `akanga.yaml` (or a companion `vocabulary.yaml` if you prefer to keep them separate). Each entry has the following shape:

```yaml
relation_types:
  - id: EP-001
    name: contradicts
    description: "Asserts that the target claim is false or substantially wrong."
    category: epistemic
    symmetric: false
    inverse_id: EP-002        # optional — the ID of the inverse relation type

  - id: EP-002
    name: is_contradicted_by
    description: "The passive form of 'contradicts'."
    category: epistemic
    symmetric: false
    inverse_id: EP-001

  - id: MY-001
    name: inspires
    description: "The source node sparked the idea in the target node."
    category: creative
    symmetric: false
    inverse_id: MY-002

  - id: MY-002
    name: is_inspired_by
    description: "The target node was the spark for this node's idea."
    category: creative
    symmetric: false
    inverse_id: MY-001
```

The built-in IDs use the category-prefix format (`EP-`, `SC-`, `CT-`, `TC-`, etc.). Custom relation types you add should use a distinct prefix — `MY-`, `WK-` (for a project-specific vocabulary), or a UUID — to avoid colliding with future built-in IDs.

The ID is the machine key. The `name` is a display cache. The `description` is shown in the TUI relation picker and in `list_relation_types` MCP output. The `inverse_id` is optional but enables lazy inverse lookup (covered in Phase 3).

#### The dual-key pattern applies to relation types too

Every edge in a node's frontmatter stores both `relation` (the display name) and `relation-id` (the authoritative ID):

```yaml
edges:
  - relation: contradicts
    relation-id: EP-001
    target: Blink — Malcolm Gladwell
    target-id: d4e1f9cc-5678-1234-efab-012345678901
```

The `relation-id` is what Akanga's code actually uses for lookup, filtering, and traversal. The `relation` field is a human-readable display cache — it is what you see in the TUI and in raw file reads. This separation is what makes vocabulary evolution safe.

#### Additive changes: always safe

Adding a new relation type to `akanga.yaml` is a purely additive change. It has exactly zero effect on existing edges. The existing edges do not reference the new ID; no file is touched; no migration runs. You can add a thousand new relation types and nothing breaks.

Adding a new edge that uses the new relation type is equally safe. The edge gets written to one file's frontmatter, the indexer updates the DB, and the new `relation-id` is live.

**Safe changes (do these freely):**
- Adding a new relation type with a new ID
- Adding or updating a `description` for any relation type
- Adding an `inverse_id` to a relation type that previously lacked one
- Adding a new category prefix
- Adding a `symmetric: true` flag to a relation type that was not previously marked symmetric

#### Renaming a relation type's display name: safe

If you change only the `name` field of a relation type (keeping the `id` unchanged), the change is safe but creates display-name drift in existing edges. Every edge that was written with the old name will now show the old display string in the raw file, while the system will resolve the relation correctly via the unchanged `id`.

This is the same stale-title pattern you saw for node renames. The fix is the same: a background sync job queued when the rename is detected, lazily updating the `relation` display field in every edge that uses the old name. The edges are not broken — they are just cosmetically stale.

**Rule:** rename `name` freely. Enqueue a `relation_name_sync` job. Let it drain lazily. Do not rename `id`.

#### Changing a relation type's ID: a breaking change

Renaming an `id` — for example changing `MY-001` to `CR-001` because you decided to introduce a `creative` category prefix — is a breaking change. Every edge stored in the vault that carries `relation-id: MY-001` will now fail to resolve to a known relation type. In the TUI, these edges will show as `unknown (MY-001)`. The edges are not lost — the ID is still stored — but they are no longer associated with any known relation type's name or description.

**Never do this silently.** If you must change an ID, you need to run a migration.

#### Migrating edges when you must change a relation ID

Migration is a two-step file operation:

1. **Update `akanga.yaml`**: change the `id` value from the old string to the new string, and update any `inverse_id` references.
2. **Scan all vault files**: for every `.md` file with a frontmatter `edges:` block, replace every occurrence of `relation-id: OLD-ID` with `relation-id: NEW-ID`.

In code, this is a direct bulk rewrite — read each file, replace the ID string, write it back atomically. Because `relation-id` is a precise key (it appears only in edge blocks), a simple string replacement is safe. If you use Akanga's parser module:

```python
def migrate_relation_id(vault: Path, old_id: str, new_id: str) -> int:
    """Rewrite every edge in the vault that uses old_id to use new_id instead.
    Returns the count of edges rewritten."""
    changed = 0
    for md_file in vault.rglob("*.md"):
        node = parse(md_file)
        updated_edges = []
        file_changed = False
        for edge in node.edges:
            if edge.relation_id == old_id:
                updated_edges.append(
                    Edge(relation=edge.relation, relation_id=new_id,
                         target=edge.target, target_id=edge.target_id)
                )
                file_changed = True
                changed += 1
            else:
                updated_edges.append(edge)
        if file_changed:
            node.edges = updated_edges
            write_node(node)   # atomic write
    return changed
```

After running the migration, re-index the vault so the DB reflects the new IDs.

**Always dry-run first:** print every file that would be changed and the count of edges affected before writing. A vault of 500 nodes with a heavily-used relation type could touch 200+ files.

#### Concrete example: adding "inspires" to a vault with 500 nodes

Scenario: you have a 500-node vault. You want to add a new relation type `inspires` (and its inverse `is_inspired_by`) to capture the creative lineage between ideas.

**Step 1 — Add to `akanga.yaml`:**

```yaml
relation_types:
  # ... existing 71 entries unchanged ...
  - id: MY-001
    name: inspires
    description: "The source node sparked the idea in the target node."
    category: creative
    symmetric: false
    inverse_id: MY-002

  - id: MY-002
    name: is_inspired_by
    description: "The passive form of 'inspires'."
    category: creative
    symmetric: false
    inverse_id: MY-001
```

**Step 2 — Nothing else.** No migration runs. No existing file is touched. The 500 existing nodes are unaffected.

**Step 3 — Start using it.** In any node, write:

```yaml
edges:
  - relation: inspires
    relation-id: MY-001
    target: Akanga Data Model
    target-id: <uuid>
```

or inline in prose: `[[Akanga Data Model | inspires]]`

The relation resolver finds `MY-001` in the registry and returns the correct name and description. The TUI shows the relation correctly in the relation picker.

**Total cost: one addition to `akanga.yaml`. Zero file migrations. Zero risk to existing data.**

---

## Part 2 — K2: "Traversal Tradeoffs" Section Content

### Target location

`docs/learning/phase-03-graph-algorithms.md` — new section added after the "What You Build" block and before the "Deliverable" block.

---

### Section text (complete, ready to insert)

---

### Traversal Tradeoffs

The BFS implementation in `ego_graph()` already traverses both directions — it calls `db.get_edges_from()` for outgoing edges and `db.get_edges_to()` for incoming edges in the same loop, tagging each result with `EdgeDirection.OUTGOING` or `EdgeDirection.INCOMING`. This gives the TUI its two-arrow visual: solid arrows for what this node claims about others, dotted arrows for what others claim about this node.

That is the current implementation. But the design question — **what direction to traverse by default in a non-ego-graph context** — involves a tradeoff that is worth understanding explicitly, because it affects Graph RAG (Phase 8), the REST API (Phase 6), and the MCP `get_neighbors` tool.

#### The outgoing-only default and what it means semantically

When a user calls `get_neighbors(node_id, direction="out")` or traverses the graph starting from a node, outgoing-only traversal means: **follow what this node asserts, not what asserts about it.**

Consider a two-node graph:

```
Fast Thinking is Unreliable  --[contradicts]-->  Blink by Gladwell
```

With outgoing-only traversal:
- Traversing from **Fast Thinking**: `Blink by Gladwell` is reachable (it's a direct outgoing neighbor).
- Traversing from **Blink by Gladwell**: `Fast Thinking is Unreliable` is **not reachable** unless you traverse incoming edges or add an explicit reverse edge.

This is the intended behavior for semantic queries. "What does this node assert?" is a different question from "What asserts about this node?" They should be queryable separately. The `direction` parameter in `get_neighbors` — `"out"`, `"in"`, or `"both"` — exposes this choice to the caller.

The outgoing-only default is not an oversight. It reflects a modeling principle: in a directed knowledge graph, the source of an assertion carries the semantic weight. `A contradicts B` is a claim made by the author of A. Whether the author of B wants to make the reverse claim is a separate decision.

#### The tradeoff: explicit reverse edges vs computed inverses

There are two ways to make `Blink by Gladwell` reachable from itself in the context of the contradiction:

**Option 1 — Explicit reverse edge (more data, clearer semantics):**

Write a second edge in Blink's frontmatter:

```yaml
edges:
  - relation: is_contradicted_by
    relation-id: EP-002
    target: Fast Thinking is Unreliable
    target-id: <uuid>
```

Now `Blink by Gladwell` has its own outgoing edge pointing back to `Fast Thinking`. Outgoing-only traversal from Blink reaches Fast Thinking. The graph is symmetric in data, and both nodes carry their relationships explicitly. Reading either file in raw Markdown shows the full relationship from that node's perspective.

Downside: data duplication. If the original edge changes (say, the relation type is updated), you must update two files instead of one. In a personal vault managed by one person, this is rarely a problem. At scale or with multiple editors, it creates synchronization obligations.

**Option 2 — Lazy inverse lookup via `inverse_id` (less data, more complex queries):**

The `inverse_id` field on relation types (defined in `akanga.yaml` and introduced in Phase 1) enables a different approach: when you encounter an edge with `relation-id: EP-001` (contradicts), you can look up its inverse: `EP-002` (`is_contradicted_by`). Rather than querying for "edges where source = Blink", you can query for "edges where target = Blink AND relation-id = EP-001, then present them as EP-002 edges pointing in the other direction."

This is lazy inverse resolution. The `get_edges_to()` DB method already enables this — it returns all edges whose `target_id` matches the node. The question is whether to re-label them with their inverse relation name before returning.

The ego-graph implementation uses this approach for the INCOMING result set: it fetches edges pointing to the root node and tags them `EdgeDirection.INCOMING`. Whether it also re-labels the relation to its inverse (`is_contradicted_by` instead of `contradicts`) is a UI decision — the relation is semantically the same edge seen from the other side.

**The `inverse_id` field enables this re-labeling without storing a second edge.** It is the foundation of lazy inverse inference, and it is why the `symmetric` and `inverse_id` fields were introduced in Phase 1 even though Phase 3 does not yet use them fully.

#### When to add explicit reverse edges vs rely on `inverse_id`

| Scenario | Recommendation |
|---|---|
| Personal vault, < 1000 nodes | Explicit reverse edges are fine. They make raw files self-documenting and eliminate the need for inverse resolution logic. |
| Shared or growing vault, > 1000 nodes | Prefer `inverse_id` lazy lookup. Explicit reverse edges double the write surface and create sync obligations across editors. |
| The relation is `symmetric: true` (e.g., `is_related_to`) | Never add reverse edges — the edge already reads the same in both directions. Rely on the `get_edges_to()` query for the other side. |
| The relation has no `inverse_id` defined | You must use explicit reverse edges if you want the relationship to be discoverable from the target side without bidirectional traversal. |
| Graph RAG context at depth 2+ | Use bidirectional BFS regardless — `direction="both"` ensures the full neighborhood is captured. The missed-neighbor problem compounds at each additional hop. |

#### How the ego-graph implementation already handles both directions

The `ego_graph()` function you built already solves this correctly for the TUI case — it traverses both outgoing and incoming edges in the same BFS pass. This means the ego-graph shown in the TUI is always complete: no edges are invisible to either party in a relationship.

The issue is narrower: **non-ego-graph traversal** (the REST API's `GET /nodes/{id}/neighbors`, the MCP's `get_neighbors` tool, and the Graph RAG seed expansion) defaults to outgoing only, unless the caller explicitly requests `direction="both"`. For Phase 8 Graph RAG, the recommendation is `direction="both"` for the BFS expansion step — you want the full neighborhood for context injection, not half of it.

#### Practical summary

For the Phase 3 deliverable, the ego-graph traversal is correct as written. The bidirectionality is already implemented. The takeaway is:

1. Outgoing-only BFS is semantically correct for "what does this node assert?" queries.
2. Bidirectional BFS (already implemented in ego_graph) is correct for "what is this node's full neighborhood?" — which is what you want for display and for RAG.
3. The `inverse_id` field is the mechanism for lazy inverse resolution — it defers the decision of whether to add explicit reverse edges to vault scale and use-case.
4. For small personal vaults: explicit reverse edges are the pragmatic choice. For large vaults or multi-editor contexts: `inverse_id` keeps the data lean.

---

## Part 3 — K3: Graph Validation Paragraph Content

### Target location

`docs/learning/phase-01-data-modeling.md` — new paragraph inserted into the "Concepts" section, after the "Labeled Property Graph" concept block and before the "Source of Truth" concept block.

---

### Paragraph text (complete, ready to insert)

---

### Graph Validation — an Intentional Absence

Akanga does not enforce logical consistency between edges. Nothing in the data model, the parser, or the indexer prevents a vault from containing both `A supports B` and `A contradicts B` simultaneously. This is a deliberate design decision, not an oversight.

In formal knowledge systems — OWL ontologies, Description Logic reasoners, formal knowledge bases used in enterprise data integration — contradictory assertions are treated as errors. The system detects the inconsistency and either rejects the new assertion or triggers a resolution workflow. This is appropriate when the knowledge graph represents facts that must be correct (a product catalog, a regulatory compliance system, a medical record).

Akanga is a thinking tool, not a formal logic system. A personal knowledge graph often captures unresolved intellectual tension as a feature, not a bug. Consider: a researcher reading two papers that make opposing claims is not experiencing an error — they are experiencing the actual state of the field. The correct representation is `Paper A supports Claim X` and `Paper B contradicts Claim X`, both present in the graph simultaneously. Removing one to satisfy a consistency constraint would falsify the researcher's understanding.

Contradictions are also temporally meaningful. `I supports approach Y` written in January and `I contradicts approach Y` written in March is not a mistake — it is a record of changed understanding over time. A node that contradicts its own earlier node is a form of intellectual autobiography that a consistency-enforcing system would destroy.

The practical consequence: the `contradicts` relation type in Akanga is epistemic metadata, not a logical assertion that triggers inference. Two contradicting edges coexist in the DB as sibling rows. The TUI surfaces them together in the ego-graph — it is up to the human to decide what the contradiction means and whether to resolve it. Akanga holds the contradiction; the human does the reasoning.

If you want contradiction detection as a tool (not a constraint), it is achievable as a query: `SELECT * FROM edges WHERE source_id IN (SELECT source_id FROM edges WHERE relation_id = 'EP-001') AND relation_id = 'EP-003'` — a "show me nodes that both support and endorse the same target" query. That is a lens on the data, not enforcement on the writes.

> The `symmetric` and `inverse_id` fields in the relation registry are the closest Akanga comes to constraint-like metadata — they are structural assertions about how a relation type behaves, not consistency constraints on the graph. They enable lazy inverse resolution (Phase 3) and future relation inference (future-ideas.md), but they never reject an edge that a human chose to write.

---

## Part 4 — Cross-Cutting Integration Analysis

The nine phases build a system where each layer's design decisions ripple forward and backward through the stack. The integration points below are the ones learners most consistently miss — not because the code is complex, but because the connection is not made explicit in either phase document.

### Integration 1: EventBus (Phase 4) → Git auto-commit (Phase 7) → MCP write tools (Phase 8)

**What happens structurally:**

The EventBus (Phase 4) is the message bus that decouples file system events from their consumers. When the file watcher detects a change, it publishes a `file_changed` event. Phase 7's `GitManager` subscribes to this event and schedules a debounced auto-commit (5 seconds). Phase 8's MCP `create_node` tool writes a file to the vault — which triggers the watcher, which fires the event, which triggers the auto-commit. The MCP tool does not need to know that git exists; git does not need to know that MCP exists.

**What learners miss:**

Learners implementing Phase 8 often try to add a direct `git_manager.commit()` call inside `create_node`. This is correct behavior achieved via the wrong mechanism. The EventBus subscription makes the commit automatic for any write, from any source — TUI, REST API, MCP, direct file edit. A direct call in `create_node` only covers MCP writes and creates a maintenance problem when a new write path is added.

**Where to highlight this:**

- Phase 4: add a forward reference — "The EventBus subscription pattern you are implementing here is the mechanism by which Phase 7 (git) and Phase 8 (MCP writes) automatically trigger commits without coupling to either of those systems."
- Phase 7: add a backward reference — "The GitManager subscribes to the EventBus from Phase 4. This is why the auto-commit fires for file changes from any source — TUI edits, REST API calls, and MCP tool calls all flow through the same event."
- Phase 8: add a backward reference — "The MCP `create_node` tool does not call git directly. It writes a file; the watcher fires; the EventBus propagates; the GitManager's debounced commit runs. The chain you built across Phases 4 and 7 is silently doing work here."

### Integration 2: FTS5 index (Phase 2) is the foundation of Graph RAG (Phase 8)

**What happens structurally:**

Phase 2 builds the `GraphDatabase` with an FTS5 virtual table (`nodes_fts`) that indexes node titles and bodies. This is optimized for text search — it is not a vector index, it is an inverted term index. Phase 8's `context_for_query()` function calls `db.search(query, limit=5)` as its first step, which runs an FTS5 query. The Graph RAG pipeline is: FTS5 seed search → BFS expansion → triple serialization. FTS5 is not a detail of Phase 2 — it is the entry point of the entire AI integration.

**What learners miss:**

FTS5's `MATCH` queries use a specific syntax that differs from SQL `LIKE`. Learners who implement FTS5 mechanically in Phase 2 without testing edge cases will hit silent failures in Phase 8 when the query string contains characters that FTS5 treats as syntax (hyphens, asterisks, quotes). The `LIKE` fallback that Phase 2 recommends for malformed queries is not just a defensive measure — it is essential infrastructure for Phase 8's reliability.

The other missed connection: FTS5 scores results by term frequency (BM25 in SQLite's implementation). The order of seed nodes returned by `db.search()` affects which nodes become the BFS roots in Phase 8. A poorly tuned FTS5 query returns lower-relevance seeds, which produces lower-quality graph context. The indexer design decision in Phase 2 directly determines Graph RAG quality.

**Where to highlight this:**

- Phase 2: add a forward reference — "The FTS5 virtual table you are building here is the entry point for Graph RAG in Phase 8. The quality of your seed nodes (determined by this index) directly determines the quality of the structured context injected into an LLM prompt."
- Phase 8: add a backward reference — "The `db.search()` call at the top of `context_for_query()` runs an FTS5 query against the index built in Phase 2. If that index is missing or malformed, Graph RAG silently returns no context. The FTS5 `LIKE` fallback from Phase 2 is why the pipeline degrades gracefully rather than crashing."

### Integration 3: Ego-graph BFS (Phase 3) appears in both the TUI (Phase 5) and MCP `get_context` (Phase 8)

**What happens structurally:**

The `ego_graph()` function in `graph.py` (Phase 3) is called in at least three different contexts:

1. **Phase 5 TUI**: the `G` key renders the vault graph; the `g` key renders the ego-graph of the selected node. Both call `ego_graph()` and pass the result to the ASCII renderer or the Textual canvas widget.
2. **Phase 6 REST API**: `GET /api/v1/nodes/{id}/neighbors` is a simplified form — `get_edges_from()` and `get_edges_to()` are the DB calls that power it, which is what `ego_graph()` uses internally.
3. **Phase 8 MCP**: `ego_graph_tool()` and `context_for_query()` both call `ego_graph()` directly. The Graph RAG pipeline runs one `ego_graph()` call per seed node, deduplicates the results, and serializes the merged subgraph.

`ego_graph()` is the most reused function in the system. Its correctness, its handling of cycles, and its `depth` parameter behavior are not just Phase 3 concerns — they are correctness requirements for everything built on top of it.

**What learners miss:**

Learners often implement `ego_graph()` to pass Phase 3's tests and then treat it as done. The `test_cycle_does_not_loop` test is the critical one — a missed cycle in the visited-set logic does not affect Phase 3 tests (which use small graphs) but will cause the Phase 8 MCP `ego_graph_tool(hops=3)` to hang or exhaust memory on a real vault with cyclic relationships.

The `depth` boundary behavior is equally important: `if current_depth >= depth: continue` includes the node at the boundary in the result but does not expand it further. Learners who accidentally write `>` instead of `>=` will produce depth-1 ego-graphs that include no direct neighbors — a bug that passes naive Phase 3 tests (if the test only asserts `assert len(nodes) > 1`) but breaks Phase 8's multi-hop context (which relies on depth=2 returning a true two-hop neighborhood).

**Where to highlight this:**

- Phase 3: add a forward reference — "The `ego_graph()` function you are building here is called by the TUI (Phase 5), the REST API (Phase 6), and the Graph RAG pipeline (Phase 8). The `test_cycle_does_not_loop` and `test_depth_boundary` tests are the most important in the suite — they guard correctness for everything built on top."
- Phase 5: add a backward reference — "The graph rendering here calls `ego_graph()` from Phase 3. If cycles are not correctly handled in that function, the TUI will hang on a vault with cyclic relationships."
- Phase 8: add a backward reference — "Both `ego_graph_tool()` and `context_for_query()` call `ego_graph()` from Phase 3. The depth=2 default for Graph RAG is a practical compromise: depth 1 misses multi-hop reasoning, depth 3+ can include hundreds of triples on a well-connected vault. The depth boundary behavior you implemented in Phase 3 directly controls this."

### Integration 4: WAL mode (Phase 2) enables the concurrent reader pattern used by REST API + TUI running simultaneously (Phase 6)

**What happens structurally:**

Phase 2 enables WAL (Write-Ahead Logging) on the SQLite database with `PRAGMA journal_mode=WAL`. WAL allows multiple concurrent readers while a single writer holds the write lock — the readers read from the last committed checkpoint, not from the in-progress write. Without WAL, SQLite uses the default rollback journal, where any write operation locks the database file entirely, causing all readers to block or receive a `database is locked` error.

Phase 6 describes the REST API and TUI running simultaneously against the same `.akanga.db` file. Phase 8 adds the MCP server as a third concurrent reader. In practice, a typical Akanga session has: the Textual TUI open (reading frequently), the REST API serving (reading on each request), and the file watcher triggering indexer writes (writing periodically). Without WAL mode, this three-process setup reliably deadlocks.

**What learners miss:**

WAL mode appears in Phase 2 as a one-line `PRAGMA` with a brief explanation. Learners copy it correctly and move on. The consequence of removing it is not visible in Phase 2 (which uses a single connection). The consequence appears in Phase 6 when the TUI and REST API are run together and requests begin failing with `OperationalError: database is locked`.

This is the most common Phase 6 debugging error — and its root cause is in Phase 2. Without the explicit connection to WAL mode, learners spend significant time debugging the REST API before realizing the issue is in the database initialization code they wrote four phases earlier.

The `threading.Lock` in `GraphDatabase` and WAL mode address different concurrency problems: the `Lock` serializes writes from multiple threads within the same process; WAL mode allows reads from a different process while writes are happening in the indexer process. Both are needed; neither is sufficient alone.

**Where to highlight this:**

- Phase 2: add a forward reference — "The `PRAGMA journal_mode=WAL` line you are adding here is the prerequisite for running the REST API and TUI simultaneously in Phase 6, and for the MCP server in Phase 8. Without it, multiple processes accessing the same `.akanga.db` file will deadlock. A good test for this phase: open two SQLite connections to the test database and run a read on one while a write is in progress on the other — WAL mode should allow the read to succeed."
- Phase 6: add a backward reference — "If you encounter `OperationalError: database is locked` when running the TUI and REST API together, the root cause is almost certainly the WAL mode setting from Phase 2. Verify that `GraphDatabase.connect()` runs `PRAGMA journal_mode=WAL` immediately after opening the connection."

---

## Part 5 — Theoretical Depth Assessment

### Formal KG concepts taught implicitly but never named

The learning path teaches several foundational knowledge graph concepts through practical implementation without naming the theoretical construct. This is a deliberate choice in PBL — learners build intuition before encountering terminology — but there is a point at which unnamed concepts become harder to look up and build on.

**RDF triples (Subject, Predicate, Object):**
Phase 1 introduces the `(source, relation, target)` edge structure. Phase 8 explicitly uses the term "triple serialization" and shows the `S --[P]--> O` format. The connection to the formal RDF triple model is implicit. Learners who later encounter SPARQL, Turtle, or JSON-LD will have to make the conceptual bridge themselves.

**Property graphs vs RDF graphs:**
The distinction between Property Graph (edges and nodes have arbitrary key-value properties) and RDF (edges are triples, no properties on edges) is foundational in the KG ecosystem. Akanga implements a Labeled Property Graph (LPG) — the `relation` field on an edge is a label, and the edge dataclass could carry additional properties. Phase 1 mentions "Labeled Property Graph" in its concepts section, which is good. But it does not contrast LPG with RDF, so learners who read Neo4j documentation or Wikidata's data model will be confused by the different edge structure.

**Ontology:**
The relation type vocabulary in `akanga.yaml` is a lightweight ontology — it defines a controlled vocabulary for edge types, with structural metadata (`symmetric`, `inverse_id`). Phase 1 never uses the word "ontology." Learners who encounter OWL or RDFS later will not immediately recognize that the vocabulary they built is a simplified equivalent.

**Knowledge Graph Embeddings:**
Phase 8 mentions vector embeddings as a future enhancement for seed retrieval, but the broader field of Knowledge Graph Embeddings (TransE, RotatE, etc. — methods for learning vector representations of entities and relations jointly) is not mentioned. For a PBL course this is appropriate scope-keeping, but an advanced learner extending Akanga to use embeddings for traversal will encounter this literature.

**Named graphs:**
The `graph` field in node frontmatter (the workspace membership field) is functionally equivalent to the "named graph" concept in RDF datasets. A named graph is a set of triples with an identifier — exactly what a workspace is in Akanga. Again, this connection is implicit.

### Should the path include more formal theory?

No. The pragmatic approach is correct for this PBL course, for three reasons:

1. **The audience is intermediate Python developers, not knowledge representation researchers.** Formal theory (Description Logic, OWL expressivity, SPARQL algebra) adds learning overhead that does not pay off until learners are extending Akanga far beyond what the course covers.

2. **The practical implementations already encode the concepts correctly.** A learner who understands why `target-id` is authoritative and `target` is a display cache has internalized reference integrity more durably than one who read a definition of it. The PBL approach produces deeper retention of fewer concepts.

3. **Named concepts can be introduced at the end, not during.** A brief "where this fits in the broader KG ecosystem" section at the end of Phase 1 (or as an appendix to the learning path) can name the formal concepts without making them prerequisites. Learners who want to go deeper have the vocabulary to search the literature; learners who do not can skip it.

**Recommended addition:** A single "Broader Context" sidebar in Phase 1 — 150 words — that names RDF triples, LPG, and ontology, and places Akanga in the landscape. Not a teaching section; a navigation aid.

### Connections to the broader KG ecosystem that would enrich without adding complexity

**Wikidata:** Wikidata is a public LPG with ~100M items and ~2B statements. Its relation types (called "properties", prefixed `P`) are structurally analogous to Akanga's relation type IDs. The Wikidata property `P31` ("instance of") is the semantic equivalent of Akanga's `is_a` relation. Pointing learners to `https://www.wikidata.org/wiki/Q42` and asking "what would this node look like in Akanga?" is a five-minute exercise that makes the abstract concrete without adding any implementation.

**Microsoft GraphRAG (2024):** The Phase 8 section already cites the 35%+ accuracy improvement from GraphRAG research. This is worth naming explicitly as a research result, because it answers the question "why not just use a vector store?" for AI-literate learners. The citation is brief — it does not require reading the paper — but it grounds Akanga's architecture in active research.

**Neo4j Cypher vs. Akanga's BFS:** Neo4j uses a declarative query language (Cypher) where `MATCH (a)-[r:CONTRADICTS]->(b)` expresses a graph pattern match. Akanga implements the same query as Python BFS code. A one-paragraph note comparing the two approaches — declarative pattern matching vs. imperative traversal — would give learners context for why graph databases exist and when Akanga's simpler approach is sufficient.

**These three additions are all reference-level, not prerequisite-level.** They can be added as footnotes or "Further Reading" callouts without restructuring any phase.

---

## Part 6 — Task List

All items below are derived directly from the K1/K2/K3 decisions in `analysis-and-enhancements.md`. Each item has: the specific artifact to modify, the effort estimate for an editor who has read the phase documents, and the acceptance criteria.

---

### TASK-K1: Add "Extending the Vocabulary" section to Phase 1

**Artifact:** `docs/learning/phase-01-data-modeling.md`

**Insert location:** After the "The Edge Format" block, before "Vault Nodes to Create"

**Effort estimate:** 0.5h (section is complete above; insert and verify formatting)

**Acceptance criteria:**
- Section is present in phase-01 immediately after the Edge Format block
- Contains all six topics: how relation types are defined in `akanga.yaml`, safe addition procedure, what breaks on ID vs name rename, migration procedure with code, additive vs breaking change distinction, concrete `inspires` example
- The `migrate_relation_id()` code example is syntactically correct Python
- No changes to any other section of phase-01

---

### TASK-K2: Add "Traversal Tradeoffs" section to Phase 3

**Artifact:** `docs/learning/phase-03-graph-algorithms.md`

**Insert location:** After "What You Build", before "Deliverable"

**Effort estimate:** 0.5h (section is complete above; insert and verify formatting)

**Acceptance criteria:**
- Section is present in phase-03 immediately before the Deliverable block
- Covers all six topics: outgoing-only default rationale, semantic meaning of missing reverse edges, explicit-reverse vs inverse_id tradeoff, how `inverse_id` enables lazy resolution, scale-based recommendation table, confirmation that the current ego-graph implementation already handles both directions
- The recommendation table (personal vault vs scale) is rendered as a Markdown table
- No changes to the existing BFS code block or Deliverable tests

---

### TASK-K3: Add graph validation paragraph to Phase 1

**Artifact:** `docs/learning/phase-01-data-modeling.md`

**Insert location:** In the "Concepts" section, after the "Labeled Property Graph" concept block, before "Source of Truth"

**Effort estimate:** 0.25h (paragraph is complete above; insert as a new concept block with the standard heading format)

**Acceptance criteria:**
- Paragraph is present in the Concepts section at the correct location
- States clearly that Akanga does NOT enforce consistency
- Explains the intentional design reason (contradictions as meaningful intellectual tension)
- Contrasts with OWL/formal systems without making formal theory a prerequisite
- Includes the concrete researcher example (two papers making opposing claims)
- Includes the example SQL query for contradiction detection as a lens, not a constraint
- Does not add a new "Vault Nodes to Create" entry (this is a design rationale, not a vault node)

---

### TASK-K3b: Confirm graph visualisation additions to future-ideas.md

**Artifact:** `docs/future-ideas.md`

**Status:** Already complete — the "Graph Visualisation Enhancements" section was added to future-ideas.md as part of the K3 decision. Verify it is present and marked V3/V4.

**Effort estimate:** 0.1h (verification only)

**Acceptance criteria:**
- `future-ideas.md` contains a "Graph Visualisation Enhancements" section
- Section is marked as V3 or V4 scope
- Lists: node sizing by connection count or recency, gravity/force weighting by relation strength, visual relation encoding by category prefix, temporal animation via git history
- Section notes the prerequisite: two-layer renderer (Phase 5) must be stable first

---

### TASK-INT1: Add cross-cutting forward/backward references to phase documents

**Artifacts:** phase-02, phase-03, phase-04, phase-05, phase-06, phase-07, phase-08

**Effort estimate:** 1.5h total (4 integration points × ~20 min each across 2–3 files per integration)

**Breakdown:**

| Sub-task | Files | Content |
|---|---|---|
| INT1-A: EventBus chain | phase-04, phase-07, phase-08 | Forward ref in 04; backward refs in 07 and 08 |
| INT1-B: FTS5 → RAG | phase-02, phase-08 | Forward ref in 02; backward ref in 08 |
| INT1-C: ego-graph reuse | phase-03, phase-05, phase-08 | Forward ref in 03; backward refs in 05 and 08 |
| INT1-D: WAL → concurrent readers | phase-02, phase-06 | Forward ref in 02; backward ref in 06 |

**Acceptance criteria per integration point:**
- Each forward reference appears near the bottom of the relevant concept block (not as a standalone section — one sentence in a callout block)
- Each backward reference appears at the point of first use (e.g., in phase-06's "multiple processes" discussion)
- References use the format: `> Forward: You will see this again in Phase X — [one-sentence preview of how it is used there].`
- References use the format: `> Backward: This uses [component] from Phase X. If you see [symptom], the root cause is in [specific location in phase X].`
- No cross-reference adds more than 2–3 sentences to any phase document

---

### TASK-THEORY: Add "Broader Context" sidebar to Phase 1

**Artifact:** `docs/learning/phase-01-data-modeling.md`

**Insert location:** End of the Concepts section, as the final concept block before "The Edge Format"

**Effort estimate:** 0.5h

**Content guidance:** 150–200 words naming RDF triples (and contrasting with Akanga's LPG), OWL ontologies (and contrasting with Akanga's vocabulary), and placing the `inverse_id` / `symmetric` fields in the context of the broader inference literature. Include three "Further Reading" links: Wikidata (public LPG at scale), Microsoft GraphRAG paper (2024), Neo4j "What is a graph database?" (Cypher vs BFS contrast).

**Acceptance criteria:**
- Sidebar is clearly marked as optional ("Further Context — skip if you want to stay focused on building")
- Does not introduce new vocabulary that learners must understand to complete Phase 1 deliverables
- All three external links are real and accessible
- Does not exceed 250 words

---

### Summary

| Task | Artifact(s) | Effort | Priority |
|---|---|---|---|
| TASK-K1 | phase-01-data-modeling.md | 0.5h | P2 (K1 decision) |
| TASK-K2 | phase-03-graph-algorithms.md | 0.5h | P2 (K2 decision) |
| TASK-K3 | phase-01-data-modeling.md | 0.25h | P2 (K3 decision) |
| TASK-K3b | future-ideas.md | 0.1h | P2 (K3 decision — verify only) |
| TASK-INT1 | phase-02 through phase-08 | 1.5h | P2 (cross-cutting) |
| TASK-THEORY | phase-01-data-modeling.md | 0.5h | P3 (enrichment, not critical gap) |
| **Total** | | **~3.35h** | |

All tasks are editorial (writing into existing documents). None require new files. None change any existing code examples, test specs, or deliverable requirements. The K1/K2/K3 tasks are additive-only — they insert new sections without modifying existing content.
