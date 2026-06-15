# Graph Algorithms Beyond BFS

**Audience:** learners who finished Phase 3 and want to know what their graph can do next — enrichment, no phase requires this · **Read time:** ~15 min

---

## Why this doc exists

Phase 3 ends at BFS on purpose; this is the map beyond, scoped to a 100–5,000-node vault. Scoring the note you're ON — link-prediction candidates over its 2-hop neighbourhood — is sub-millisecond, and Personalized PageRank converges in well under 100 ms; whole-vault passes are slower — all-pairs Adamic-Adar runs milliseconds to low seconds at 5k nodes, structural-hole constraint takes seconds. Of the "what next" list at the end, the orphan/island scan is pure SQL; Adamic-Adar and PPR are NetworkX one-liners; the structural-gap capstone composes a few NetworkX calls on top of community output.

The companion doc `graph-theory-basics.md` covers the vocabulary — nodes, edges, degree, paths, components. This one assumes you have that, plus the iterative BFS ego-graph you built in Phase 3. Everything here is optional. It is the answer to "I have a typed graph in a SQLite `edges` table — now what can I *compute* on it?"

The repo ships NetworkX in the `[graph]` extra. You build the in-memory graph from your `edges(source_id, target_id, relation, relation_id)` table once, then run these algorithms over it. None of them needs the heavy machinery you might expect from a "graph algorithms" course — at vault scale, the interesting ones are one-liners.

---

## Centrality — "which notes matter most?"

Centrality scores structural importance, but "important" has several non-equivalent meanings. Take a small path graph:

```
A — B — C — D — E
```

| Measure | What it asks | Gloss | On this graph |
|---|---|---|---|
| Degree | How many direct links? | popularity | B, C, D tie at 2; A, E at 1 |
| Closeness | How few hops to reach everyone? | broadcast speed | C wins — it sits in the middle |
| Betweenness | How many shortest paths pass through me? | brokerage | C dominates; A and E are 0 |
| PageRank | How important are my neighbours? | influence by association | flows toward well-linked hubs |

**Degree** is a single pass over the adjacency structure — O(n + m), trivial. It is the baseline the others refine. On the path graph it cannot tell the middle three apart.

**Closeness** is the reciprocal of average shortest-path distance. C's distances are (2, 1, 1, 2), average 1.5, so closeness ≈ 0.67; B's are (1, 1, 2, 3), average 1.75, so ≈ 0.57. C wins because a message starting there reaches the rest of the graph fastest. Computing it means one BFS per node.

**Betweenness** counts, for each node, the fraction of all-pairs shortest paths running *through* it. Every path between {A, B} and {D, E} crosses C, so C's betweenness dominates; A and E lie on no one else's paths, so they score 0. The intuition is brokerage — remove a high-betweenness note and two regions of your vault stop talking. Brandes' algorithm computes this exactly without materializing every path; it is what InfraNodus uses to size nodes in its graph view.

**PageRank** scores a note by the importance of the notes pointing at it — "it's not how many you know, it's *who*." A random surfer follows an out-link with probability `d` (the damping factor, usually 0.85) and teleports to a random note with probability `1 − d`. Damping is what stops dead-end notes and tight little citation loops from breaking the math.

NetworkX exposes all four: `nx.degree_centrality`, `nx.closeness_centrality`, `nx.betweenness_centrality`, `nx.pagerank`. At 5k sparse nodes each returns in well under a second.

---

## Community detection — "what clusters did I actually write?"

Your tags are the clusters you *declared*; community detection finds the ones you *actually wrote* — the topic neighbourhoods that emerge from how your notes link, whether or not you ever named them.

The objective these methods optimize is **modularity** `Q`: the fraction of edges that fall *inside* communities, minus the fraction you'd expect if the same edges were rewired at random while preserving each node's degree. It ranges over [−1/2, 1]; higher means denser-than-chance clusters.

The barbell graph makes it concrete — two triangles joined by a single edge. Put each triangle in its own community and 6 of the 7 edges stay internal, giving high `Q`. Merge everything into one community and `Q` collapses to 0 by construction. Split a triangle and you waste internal edges, dropping `Q`. The partition that maximizes `Q` is the obvious one: two communities.

**Louvain** finds that partition by greedy hill-climbing in two repeating phases: *local moving* (each node joins whichever neighbouring community most raises `Q`) and *aggregation* (collapse each community into a super-node and repeat on the smaller graph). It scales to millions of edges. Its flaw is that it can produce communities that are internally *disconnected* — well over a tenth of them in some experiments. **Leiden** fixes this by inserting a refinement phase that splits communities into well-connected sub-communities before collapsing, and it guarantees connected output while running faster than Louvain. If you reach for one, reach for Leiden.

**Label propagation** is the cheap alternative: every node starts with its own label, then in each round adopts the label held by the majority of its neighbours (ties broken at random). Dense regions reach consensus in a round or two; on the barbell, the single bridge edge is never a majority for either side, so two labels stabilize. It is near-linear and among the fastest methods — at the cost of nondeterminism, since random tie-breaking means runs can disagree. It is the community method the popular Obsidian Graph Analysis plugin ships.

One caveat worth knowing: modularity optimization has a *resolution limit* — below a certain size it merges small communities even when they are clearly distinct. At vault scale this rarely bites, but it explains why two genuinely separate small topics sometimes land in one cluster.

---

## Link prediction — "you should probably connect these notes"

This is the highest-leverage thing your graph can do: score pairs of notes that *aren't* linked yet by how likely an edge should exist, using topology alone — no NLP, no embeddings. It directly targets the core PKM failure: ideas that belong together but never got connected.

**Common Neighbors** simply counts how many notes two candidates both link to. It works, but it favours high-degree hubs — being co-linked from your sprawling "Index" MOC counts the same as being co-linked from a tiny niche note.

**Adamic-Adar** fixes that by weighting each shared neighbour by `1 / log(degree)`. A shared link from a focused, low-degree note contributes a lot; a shared link from a giant hub everyone points at contributes almost nothing. The reasoning: a co-link from a specialist note is real evidence of kinship, while a co-link from your index is just noise. This is the flagship algorithm of the Graph Analysis plugin, and in NetworkX it is one call:

```python
import networkx as nx

# G built from your edges table; score the pairs you care about
scores = nx.adamic_adar_index(G, [(note_a, note_b), (note_a, note_c)])
for u, v, score in scores:
    print(u, v, round(score, 3))
```

Scoring the current note against its 2-hop candidates is sub-millisecond; scoring all pairs across a 5k-node vault is milliseconds to low seconds, because PKM graphs are sparse (average degree ~3–10).

---

## Personalized PageRank — the ego-graph, upgraded

Your Phase 3 ego-graph treats every neighbour within N hops as equally relevant, then falls off a cliff at the depth cutoff. **Personalized PageRank** (PPR) replaces that hard edge with a smooth, weighted "relatedness halo." Instead of teleporting to a *random* note, the random surfer always restarts at your seed note — so the resulting scores measure proximity *relative to that seed*.

```python
scores = nx.pagerank(G, personalization={seed_id: 1.0})
related = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
```

Two upgrades follow naturally. First, your edges are *typed* — the 72-relation vocabulary means a `supports` edge can carry more weight than a bare `wikilink`; feed those weights to PPR and relatedness respects the kind of connection, not just its existence. Second, the personalization dict takes *several* seeds — set mass on three notes and ask "what is related to all of these together?", which a single-seed BFS can't express.

This is the obvious successor to Phase 3's ego-graph for a "Related Notes" sidebar, and it is also exactly the seed-selection step a Phase 8 RAG layer wants: pick the notes most related to the query's anchors, then feed their text to the model. Over a 5k-node sparse graph it converges in well under 100 ms, and results cache cleanly — invalidate them off the same watcher events that already trigger re-indexing.

---

## What your Phase 3 graph can do next

In rough value-per-effort order:

1. **Orphan / island scan** — degree-0 notes, dangling wikilinks, and small disconnected components. This is *pure SQL* over your `nodes` and `edges` tables; you don't even need to build a graph object. Table stakes, and your link resolver already knows which targets failed to resolve.
2. **Adamic-Adar "suggested links"** — a NetworkX one-liner over the in-memory graph, run against the current note's 2-hop neighbourhood. Highest value of anything here.
3. **Personalized PageRank "related notes"** — another NetworkX one-liner; upgrades the ego-graph from binary BFS to ranked relatedness.
4. **Structural-gap capstone** — the differentiator. Run community detection, count the edges *between* each pair of communities, rank pairs by (size × size) / edge-count to find well-developed clusters that barely talk, then surface the top Adamic-Adar candidates *across* that gap as "ideas to bridge." It is a few NetworkX calls composed on top of community output — no new algorithm, just assembly.

Everything in this list runs in well under a second at 5k nodes on one core and fits the "build the graph from SQLite on demand" model you already have.

> **Solo:** Build the in-memory graph from your own vault and run `nx.adamic_adar_index` over the current note's candidate pairs. Look at the top three suggestions — do they make sense? Now create an "Index" MOC that links to a dozen notes and re-run it. Watch how the `1/log(degree)` weighting quietly discounts that new hub: it stops the index note from dominating every suggestion.

> **Group:** Walk through the damping-factor random-walk story together. With `d = 0.85`, the surfer follows a link 85% of the time and teleports 15% of the time — why does *teleporting* make the ranking more stable than a pure walk? Then discuss: if you run Personalized PageRank seeded on a single note in your shared vault, which note do you each predict ranks #2 (right after the seed itself), and why?

---

## Further Reading

- Brandes, U. — "A Faster Algorithm for Betweenness Centrality," *Journal of Mathematical Sociology* 25 (2001)
- Brin, S. & Page, L. — "The Anatomy of a Large-Scale Hypertextual Web Search Engine" (1998) — the original PageRank
- Traag, V., Waltman, L. & van Eck, N. J. — "From Louvain to Leiden: guaranteeing well-connected communities," *Scientific Reports* 9 (2019)
- Liben-Nowell, D. & Kleinberg, J. — "The Link-Prediction Problem for Social Networks"
- NetworkX documentation — link prediction, link analysis (pagerank), and centrality algorithm references
