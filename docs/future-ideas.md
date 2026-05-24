# Future Ideas — Parking Lot

These are deliberately **out of scope for MVP, V1, and V2**. They are captured here so they are not lost, but they require significantly more design thinking before any implementation.

---

## Active / Executable Nodes

**Status:** Parked. Not in MVP, V1, or V2.

The original health-check framing (`type: active`, HTTP/TCP ping) is too narrow. The full vision is a node that can *run something* — and the results of that run become part of the knowledge graph.

What "run something" could mean, and why each needs more design:

- **HTTP health checks** — simplest case. Still requires thinking about: auth headers, response schema validation (not just status code), retry policy, alert routing.
- **TCP reachability** — even simpler, but same policy questions.
- **Code execution** — run a Python/shell snippet and store the output as a result. Immediately raises: sandbox model (can the node overwrite files?), secrets injection (how do you pass a DB password?), output schema (structured vs raw text), timeout and resource limits.
- **Data validation** — run a query (SQL, HTTP, CLI) and assert something about the result. Useful for "is this S3 bucket still empty?" or "does this API still return the expected schema?" Requires a query language or templating system.
- **Cron-style scheduling** — interval-based is the obvious model, but: what if the user wants cron expressions? What about timezone handling? What about triggered (event-driven) execution vs polling?
- **Result schema** — a bare `status: up/down` is insufficient for code execution. Results need to carry structured payloads, be queryable, and be diffable across runs.

**The diagram/canvas subtype** (see below) is also an active-style node — it runs a renderer rather than a health check.

**Minimum design questions to answer before any implementation:**
1. What is the execution model? (same process, subprocess, container, external agent?)
2. What is the secrets/auth model?
3. What is the result schema for each action type?
4. What does failure/retry look like?
5. How does this interact with the EventBus and git auto-commit?

---

## Diagram / Canvas Nodes

**Status:** Parked. Likely V4 or a separate tool in the Akanga ecosystem.

A node type that renders a diagram rather than prose. The diagram definition lives in the node body (as code — Mermaid, BPMN XML, Terraform HCL, draw.io XML, etc.) and the node displays a rendered visual in the TUI graph view or a dedicated canvas screen.

**Subtypes being considered:**
- **BPMN** — business process maps. Render via a BPMN parser + SVG/PNG output.
- **Infrastructure maps** — Terraform/Pulumi state → topology diagram. Nodes become services, edges become dependencies.
- **Mermaid diagrams** — flowcharts, sequence diagrams, ER diagrams. Most accessible; Mermaid CLI already exists.
- **Architecture diagrams** — C4 model, system context, container diagrams.

**Why this is complex:**
- The rendering pipeline (definition → image → TUI display) requires the Kitty/Ghostty graphics protocol (Phase 5 Layer 1 renderer) to be mature first.
- The node body format needs a diagram-type discriminator — you can't mix Mermaid and BPMN in one frontmatter field without a sub-schema.
- Editing a diagram node in the TUI requires a code editor mode, not just a markdown TextArea.
- The diagram as a *graph node* means it can have edges to other nodes — but what does "this architecture diagram `depends_on` this service node" mean semantically? Needs a clear edge vocabulary extension.

**Relationship to active nodes:** A diagram node could be *generated* by an active node (run Terraform, parse state, emit a diagram node). That integration is even further out.

**Minimum prerequisite:** The two-layer graph renderer (Phase 5) must be stable and the Kitty graphics protocol layer must be working before diagram rendering is worth designing.

---

## Graph Visualisation Enhancements

**Status:** Parked. V3 or V4 — requires the two-layer graph renderer (Phase 5) to
be stable first.

The current graph renderer uses force-directed layout with uniform node sizes and
unweighted edges. A richer visual encoding would make the graph genuinely informative
at a glance:

- **Node sizing** — size proportional to connection count (hub nodes appear larger),
  or to recency (recently edited nodes appear more prominent), or to a user-defined
  importance score in frontmatter.
- **Gravity / force weighting** — edges weighted by relation strength or by how
  recently the relationship was created. Closely related nodes cluster; distantly
  related ones stay apart.
- **Visual relation encoding** — edge colour or thickness encodes relation category
  (epistemic = blue, structural = gray, causal = orange). Requires the renderer to
  read the relation category prefix (EP-001, SC-001, etc.) from the vocabulary.
- **Node colour by type** — already partially implemented in `demo_tui.py`; could be
  extended to encode node age, tag membership, or workspace.
- **Temporal animation** — replay the graph's evolution over git history. Each commit
  adds/removes nodes and edges; the graph animates forward in time.

**Minimum prerequisites:** Two-layer renderer stable + sufficient vault size to make
visual differentiation meaningful (at least ~50 nodes).

---

## Other Parked Ideas

- **Semantic search / vector embeddings** — `sentence-transformers` over node bodies as a complement to FTS5. Useful for fuzzy/synonym queries. Can be added as a Phase 9+ enhancement without changing any Phase 1–8 architecture. (Research note from AI integration work: FTS5 + BFS is sufficient for MVP; embeddings only improve the seed-node retrieval step.)
- **Akanga Cloud / sync** — vault sync across devices via a self-hosted or managed backend. Requires conflict resolution model (CRDTs? git-based?). Entirely separate infrastructure concern.
- **Mobile / web client** — a browser or mobile UI over the REST API. The REST API (Phase 6) is the foundation; the client is out of scope for the current learning path.
- **Multi-user / collaborative vaults** — shared knowledge graphs with per-user attribution. Requires auth, access control, and a conflict model. Not compatible with the "single local SQLite" architecture without significant rework.
- **Relation inference** — if A `supports` B and B `contradicts` C, infer that A `contradicts` C (transitively). Requires a formal inference engine and a way to distinguish asserted vs inferred edges. The `symmetric` and `inverse_id` fields in the relation registry (Phase 1) are the foundation for lazy inverse inference, but full transitivity is a research problem.
