# Graph Theory Basics

**Audience:** Python devs who know dicts, lists, and basic SQL — no prior graph theory · **Read time:** ~15 min

---

## 1. You have already built a graph

If you have finished Phase 1A, you have built a graph. You just called it something else.

Every `.md` note in your vault is a **node**. Every wikilink (`[[Other Note]]`) or typed relation in a note's frontmatter is an **edge** pointing from one node to another. The moment you wrote a parser that turns `[[Systems Thinking]]` into a `(source_id, target_id, relation)` row, you built the core of a graph database — a set of **vertices** `V` (your notes) and a set of **edges** `E` (the links between them).

This doc names what you built. None of it is new machinery; it is the vocabulary and the small number of disciplines that make a pile of links into something you can traverse, query, and reason about. Once you have the names, the Phase 3 ego-graph code (`build_ego_graph` in `graph.py`) reads as exactly what it is: a textbook breadth-first search over an adjacency list that happens to live in SQLite.

---

## 2. A graph is just the general case

The reason graphs feel harder than the structures you already use is that they are *more general*. The familiar ones are graphs with constraints removed:

- A **linked list** is a graph where every node has at most one outgoing edge.
- A **tree** is a graph where every node has exactly one parent and there are no cycles.

Drop those constraints — let a node point to *any number* of others, allow cycles (note A links B, B links back to A), allow many disconnected islands — and you have a general graph. In Akanga, all three freedoms are real data: a single note links to a dozen others, two notes legitimately cite each other, and an orphan note links to nothing at all.

That generality is the whole difficulty. Nothing guarantees a starting point, an ordering, or that a walk ever terminates. Everything below — representations, traversal, the bounded queries — is about re-imposing *just enough* discipline to work with that freedom without spinning forever or running out of memory.

---

## 3. Four representations + a cheat sheet

There is no single "graph data structure." There are four common encodings, and choosing wrong costs you memory or asymptotic performance.

**Adjacency list** — the default. A map from each node to the list of its neighbours:

```python
graph = {
    "systems-thinking": ["feedback-loops", "complexity"],
    "feedback-loops":   ["complexity"],
    "complexity":       [],
}
```

Space is O(V + E) — you pay only for edges that exist. Iterating a node's neighbours is O(deg(v)), which is why adjacency lists are the default for BFS, DFS, and topological sort: those algorithms spend nearly all their time walking neighbours. The weakness: asking "is there an edge u→v?" means scanning u's list, O(deg(u)).

**Adjacency matrix** — a V×V grid where `m[u][v]` says whether u→v exists. Edge lookup and insert are O(1), but space is O(V²) no matter how few edges exist, and listing a node's neighbours is O(V) even if it has two. Matrices only win for small or genuinely *dense* graphs. A personal knowledge graph is overwhelmingly sparse, so you will almost never reach for one.

**Edge list** — the wire format. A flat list of `(source, target, relation)` triples. O(E) space, terrible for queries (finding neighbours means scanning everything), but it is the natural *serialization* shape — it is exactly what the Phase 3 Mermaid export emits, one `source --relation--> target` line at a time. You typically load an edge list and *build* an adjacency structure from it.

**CSR (Compressed Sparse Row)** — named here so you recognise it, not built in this curriculum. CSR concatenates every adjacency list into one array plus an offsets array marking where each node's neighbours begin. Traversal is cache-friendly and per-edge overhead is tiny, but it is effectively immutable: inserting an edge means shifting everything after it. It is what high-performance graph engines use internally — build once, query millions of times. A constantly-mutating vault is the wrong fit.

### Cheat sheet

| | Space | Neighbours of v | Edge u→v exists? | Add/remove edge |
|---|---|---|---|---|
| Adjacency list | O(V+E) | O(deg v) | O(deg u) | O(1) / O(deg u) |
| Adjacency matrix | O(V²) | O(V) | O(1) | O(1) |
| Edge list | O(E) | O(E) | O(E) | O(1) / O(E) |
| CSR | O(V+E), compact | O(deg v), cache-hot | O(log deg u) if sorted | rebuild |
| **SQL edge table** | **O(V+E) + indexes** | **index range scan** | **index lookup** | **one INSERT/DELETE** |

That last row is the one Akanga ships. The next section is why.

---

## 4. Your `edges` table *is* an adjacency list

Here is the schema you build in Phase 2 (`db.py`):

```sql
CREATE TABLE edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL,
    target_id TEXT,
    relation TEXT,
    relation_id TEXT,
    UNIQUE (source_id, target_id, relation),
    FOREIGN KEY (source_id) REFERENCES nodes(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_edges_source ON edges(source_id);
CREATE INDEX IF NOT EXISTS idx_edges_target ON edges(target_id);
```

This is an adjacency list materialized as rows. Each row is one directed edge `source_id → target_id`. The two indexes are not incidental — they are precisely what make adjacency queries fast:

- `idx_edges_source` turns **"what does X link to?"** into a range scan over rows where `source_id = X`. That is `get_edges_from` / `get_neighbors`.
- `idx_edges_target` turns **"what links to X?"** (backlinks) into a range scan where `target_id = X`. That is `get_edges_to` / `get_backlinks`.

Without those indexes both queries degrade to a full table scan — O(E) per lookup — which is the edge-list weakness. With them, you have the adjacency-list strength inside a transactional, durable store you already operate.

The `relation` column gives you a **multigraph for free**. Two notes can be related by both `cites` (CT-prefix) and `contradicts` at once: two rows, same `(source_id, target_id)`, different `relation`. The `UNIQUE (source_id, target_id, relation)` constraint is what makes that work — it dedups *re-derivations* of the same typed edge while still allowing genuinely different relations between the same pair. A plain `dict[node, set[node]]` cannot represent that; your edge table can.

The neighbour-traversal contract the rest of the codebase relies on: `get_edges_from(node_id)` and `get_edges_to(node_id)` each return a list of `(neighbour_NodeRecord, relation, relation_id)` tuples — the relation label travels *with* every neighbour, which is what lets Phase 3 ego graphs and Phase 8 RAG serialize real `src -[relation]-> tgt` triples instead of bare backlinks.

### Multi-hop: bounded BFS in one query

Single-hop neighbours are one index scan. For "everything within 2 hops of this note" you need recursion, and SQLite gives it to you with a recursive CTE:

```sql
WITH RECURSIVE reachable(id, depth) AS (
  SELECT :root_id, 0
  UNION
  SELECT e.target_id, r.depth + 1
  FROM edges e JOIN reachable r ON e.source_id = r.id
  WHERE r.depth < 2 AND e.target_id IS NOT NULL
)
SELECT DISTINCT n.* FROM nodes n JOIN reachable r ON n.id = r.id;
```

Three load-bearing details, each guarding against one of the freedoms from Section 2:

1. **The depth cap IS the cycle guard.** `WHERE r.depth < 2` is not just a feature knob — it is what makes the recursion *terminate*. On a cyclic graph (A→B→A is legal Akanga data) a recursion with no cap revisits the cycle forever. The cap bounds the walk regardless of cycles. This is the same role the `visited` set plays in `build_ego_graph`'s in-memory BFS.
2. **`UNION`, not `UNION ALL`.** `UNION` deduplicates rows as it goes, so a node reachable by two different paths is processed once. `UNION ALL` would keep both and, combined with a cycle, balloon the working set.
3. **`target_id IS NOT NULL`.** Edge targets are nullable in the schema for a reason: an unresolved wikilink — `[[Note That Does Not Exist Yet]]` — is recorded with a NULL `target_id`. Skipping NULL targets keeps dangling links out of the traversal so they cannot poison a join.

Swap `< 2` for `< 1` and you get immediate neighbours; raise it and you widen the ego graph. The depth parameter is the only thing standing between a clean query and an unbounded crawl.

---

## 5. Flavours of graphs

- **Directed.** Every Akanga edge has a direction: `source_id → target_id`. "A explains B" is not the same as "B explains A". You store and query each edge from a definite source. Undirected relationships, when you want them, are just two directed rows (or a query that checks both ends).
- **Weighted / typed.** A classic weighted graph attaches a number — distance, cost, similarity — to each edge. Akanga instead attaches a *type*: the `relation` column drawn from the 72-relation vocabulary. Typed edges are what let a future ranking pass weight a `supports` link differently from a casual `mentions` — the on-ramp to Personalized PageRank, covered in the companion ranking doc.
- **DAGs and topological sort.** A directed acyclic graph has no cycles, which means its nodes can be put in an order where every edge points "forward" — a topological sort. This is the workhorse behind build systems, package managers, and task schedulers. A knowledge graph is *not* a DAG (cross-references make cycles normal), which is exactly why you cannot assume an ordering exists and must lean on depth caps and visited sets instead.

---

## 6. Supernodes: skew is inevitable

Real graphs are wildly uneven. Most notes have a handful of links; a few hub notes — a daily-index note, a broad topic like "Systems Thinking" — accumulate hundreds. This skew is not a bug to design away; it is the shape of how people actually think and link.

The cost lands on traversal. A depth-2 ego graph around a hub can reach roughly 170 nodes at 1k-note scale (the curriculum's own published figure). What is a few-millisecond query around a leaf note becomes a much larger fan-out around a hub, and the rendered ego graph stops being legible long before that.

Mitigations, in rough order of reach:

- **Bound depth and result size.** A depth cap plus a `limit` keeps the worst case predictable no matter which node is the root.
- **Query from the sparse end.** If you are joining a hub against a leaf, drive the query from the leaf's side.
- **Break up the hub.** Introduce intermediate grouping nodes so a single super-hub becomes several smaller ones.

The rule that follows: **if you expose an ego/neighbours API, give it `limit` and `depth` from day one.** Retrofitting bounds after a hub note already exists means every caller has already learned to expect unbounded results. This is exactly the Phase 3 **Node Budget** concept — a hard ceiling on how many nodes an ego graph may include — made concrete.

---

## 7. The library landscape

You do not need a graph library for this curriculum, but you should know the map:

- **NetworkX** (pure Python) — the friendliest API and best docs, already available in this repo's `[graph]` extra. It is also roughly 40–250× slower than C-backed libraries on algorithm-heavy workloads. Fine for graphs up to tens of thousands of nodes, prototyping, and one-off analysis — which covers a personal vault comfortably.
- **igraph / rustworkx** (C / Rust cores with Python bindings) — same algorithms, orders of magnitude faster. Reach for these only when a graph hits 10⁵+ nodes or you run heavy centrality analytics.
- **Graph databases (Neo4j and friends)** — justified when multi-hop relationship queries are your *core product*, you need a graph query language across a team, and the data outgrows one machine. They bring real operational cost: another server, another query language, another backup story.

For Akanga's scale — one person's notes, one process, the graph as one feature among many — the SQL edge table with two indexes and recursive CTEs is the right default. It covers neighbours, backlinks, bounded BFS, and reachability inside the transactional store you already run.

**Decision shortcut:** in-memory and mutable → dict of lists; in-memory and read-heavy at scale → CSR via igraph/rustworkx; persistent and app-integrated → SQL edge table; persistent and graph-native at scale → graph database.

---

## Further Reading

- SQLite — *The WITH Clause* (recursive CTEs, BFS vs DFS ordering) — https://sqlite.org/lang_with.html
- Brandes, U. (2001) — *A Faster Algorithm for Betweenness Centrality* — https://doi.org/10.1080/0022250X.2001.9990249
- GeeksforGeeks — *Adjacency List vs Adjacency Matrix* — https://www.geeksforgeeks.org/dsa/comparison-between-adjacency-list-and-adjacency-matrix-representation-of-graph/
- graph-tool — *Performance comparison* — https://graph-tool.skewed.de/performance.html
- Neo4j Developer Blog — *Graph Modeling: All About Super Nodes* — https://medium.com/neo4j/graph-modeling-all-about-super-nodes-d6ad7e11015b
- Diestel, R. — *Graph Theory* (Springer GTM 173) — https://diestel-graph-theory.com/
