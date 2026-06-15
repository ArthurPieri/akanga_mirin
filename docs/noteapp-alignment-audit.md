# Noteapp Alignment Audit — 2026-06-12

Four parallel audit agents compared the curriculum against the noteapp reference
implementation (`../noteapp`, HEAD `60c5cf2`), its June 11–12 session history, and
its Round 2/3 analyses. This is the consolidated findings log — no fixes applied yet.

Audit dimensions: code/feature alignment, docs/explanation coverage, explanation
quality, decision/session-history impact.

---

## 1. What changed in noteapp (June 11–12)

- **Round 2 adversarial analysis** (13 perspectives, 30 merged critiques — explicitly
  consumed akanga_mirin's v1–v3 findings) + all fixes in two waves (`ab69426`,
  `5aa5399`, merged `96c0521`): indexer self-healing (UUID write-back, tombstone
  reconciliation, hash-skip incrementality, macOS delete-echo guard), the **alias
  rule** for typed wikilinks, **manual edges persisted file-first** to the frontmatter
  `edges:` block (DB rebuildable end-to-end), 71-relation registry + difflib soft
  validation, `akanga new` + `akanga export` (json/graphml/mermaid), Nhamandu brand
  theme, web reskin, ADR-0001 (web replaces Tauri).
- **Live TUI session**: crash fixes (`_render` shadowing, `_DismissOnce`), the
  **Obsidian-style interactive pixel vault graph** (Kitty protocol, PIL renderer,
  pan/zoom/select/drag/drag-to-connect), note preview panels in vault + ego graphs.
- **Comprehensive documentation suite** (`docs/guide/`, `docs/product/`, features,
  architecture, troubleshooting, docs-map) + a docs-verification bug batch.
- **Round 3 readability/DRY** (all 9 findings): canonical `textutil.slugify`,
  `edges.create_manual_edge`, `links.split_pipe_segment` as THE wikilink grammar,
  cross-language conformance test suite, `graph.py` 1,015→508 lines.
- **Parser fix** (`b52da84`): unknown node type degrades to `note` instead of vanishing.
- **Graph theory research suite** (`docs/research/graphs/01–05`): algorithms,
  PKM network algorithms, and 3-level explainers (dummies / engineers / mathematical).
- **Design discussions (session history only, recorded nowhere in either repo):**
  (a) "why functional instead of OOP?" → dataclasses + services defended over
  Node/Edge god-classes; (b) `FRONTMATTER_SCHEMA` with `extra="allow"` sketched and
  **rejected** — frontmatter stays `dict[str, Any]`.

---

## 2. Code/feature divergences (PORT candidates)

| ID | Finding | Evidence | Class | Priority |
|---|---|---|---|---|
| F1 | **Manual edges DB-only — violates the curriculum's own files-are-truth doctrine.** `POST /api/v1/edges` calls `db.upsert_edge` only; `_reindex_edges` (`solutions/phase_08/src/akanga_core/indexer.py:180`, delete-then-rederive) silently destroys API-created edges on the next file change; `rm *.db && scan` loses them — contradicting `phase-02:5-7` ("DB is expendable") and `phase-01a:83-85` (frontmatter `edges:` is source of truth). This is byte-for-byte noteapp R2 #4, fixed there file-first (`edges.py` → `add_fm_edge_to_file`, 409/400 guards, `RESERVED_RELATIONS`, deterministic uuid5 edge ids). `tests/phase_06/test_server.py:201-260` currently pins the broken behavior. | `solutions/phase_06/src/akanga_core/server.py:363-388` vs noteapp `edges.py` | PORT | **P0** |
| F3 | **Three divergent slugify rules + one silent-overwrite data loss.** `parser.py:173` (`create`) deletes chars and silently overwrites an existing `slug.md`; `akanga_mcp/server.py:129-138` collapses runs + suffixes; `akanga_core/server.py:235` keeps punctuation + 409s. Same title → different filename + collision behavior per surface. noteapp single-sources via `textutil.py` + a JSON conformance case table. | three curriculum sites vs noteapp `textutil.py` | PORT | P1 |
| F4 | **Pass-2 edge re-derivation misses newly-resolvable links in unchanged files** ("A links to B; B created later" stays unresolved until A changes). Curriculum documents this as a known limit (`indexer.py:32-34`); noteapp fixed it with `rederive_all = new_files or removed > 0` (`indexer.py:163-168`). Small change, big correctness win. | curriculum `indexer.py:32-34` | PORT | P1 |
| F2 | **No alias rule in the wikilink pipe grammar.** Curriculum treats ANY pipe content as a relation (`parser.py:38`) — an imported Obsidian `[[Note\|My Display Alias]]` mints relation `"My Display Alias"`. noteapp: slug-shaped → relation; spaces/uppercase/escaped `\|` → display alias, plain wikilink edge. Also: inline code not stripped, two near-duplicate wikilink regexes across modules. The divergence is recorded in NO decision log entry (contradiction-by-omission). | `solutions/phase_0N/.../parser.py:38`, `links.py:26` vs noteapp `links.py:55-123` | PORT + TEACH | P1 |
| F10 | **`[[A\|relation]]` produces TWO edges** (untyped wikilink + typed frontmatter edge) in the curriculum vs one in noteapp. Decide: intended pedagogy (document it) or accident (port single-edge). | curriculum `links.py:22` + `indexer.py:183-200` | design review | P2 |
| F5 | Unresolved wikilinks silently dropped (no log). noteapp logs a warning ("never silently evaporate a link the user wrote") and optionally auto-creates stub nodes. Port the warning; stub creation = good Phase 2 stretch. | curriculum `links.py:44-47` | PORT (log) + TEACH (stubs) | P2 |
| F6–F8 | TEACH-tier: relation soft validation ("did you mean `supports`?" via difflib) — fits Phase 1A/8; CLI `export` (json/graphml/mermaid) — rich cheap stretch for Phase 3/6; ego-graph **node budget** `?limit=` + `truncated` flag (noteapp R2 #26) — Phase 3 `build_ego_graph` has only `max_depth`, Phase 6 stretch endpoint has no limit param. | — | TEACH | P2 |
| F9, F11 | DIVERGE-OK: interactive pixel graph / previews already parked in `future-ideas.md:84-92`; brand theme out of scope. The cross-language conformance-table technique is a transferable testing sidebar candidate. | — | DIVERGE-OK | — |

**Already aligned / immune (no action):** parser unknown-type fix not needed
(curriculum `type` is a plain `str` per D3 — nothing can vanish); indexer Round 2
robustness all present (plus a duplicate-id guard noteapp lacks); watcher delete-echo
handling arguably better than noteapp's; `_DismissOnce` + YAML-date ports confirmed;
**71-vs-72 reconciled** — noteapp registry = 71 unique slugs, curriculum 72 = 71 +
`instance_of`, and `relation-vocabulary.md:11` already pre-explains the delta
(curriculum is ahead; noteapp is the one missing `instance_of`).

---

## 3. Explanation-quality defects (fix these — explanations that are wrong)

1. **Phase 3's flagship reference traversal does not run** (`phase-03:211-227`):
   does `edge.target_id` attribute access on what Phase 2 defines as tuples
   (`get_edges_from → list[tuple[Node, str, str]]`, confirmed in
   `solutions/phase_03/.../db.py:439`). Doc bills it as "written out explicitly,
   because this is the learning." Transcribing it → `AttributeError`.
2. **`sqlite-basics.md:173-220` teaches the WRONG FTS5 external-content sync
   pattern** (plain DELETE + INSERT instead of the `'delete'`-command dance) and
   indexes the prose body, contradicting Phase 2's "title and tags only" rule. The
   correct mechanism currently lives ONLY in skeleton docstrings
   (`skeletons/phase_02/.../db.py:154-196`).
3. **`yaml-and-markdown-frontmatter.md:471-544` tail describes the noteapp-era
   schema** (node types `active`/`virtual`/`diagram`, `path`-keyed workspaces) —
   contradicts Phase 0's canonical `note|reference` + UUID-workspace config.
4. **Stale "71 relation types"** in phase-1A (`:73,79`), 1B (`:157`), 3 (`:241`),
   8 (`:17,237,439,534` incl. "51 of the 71" inverse claim) vs the declared
   source of truth (`relation-vocabulary.md` = 72).
5. **`asyncio-primer.md` drift**: references `ActiveNodeManager`/`aiohttp`/`active.py`
   (never built in this path), and its `publish()` pseudocode (`:204-218`) drops
   events with a warning — contradicting Phase 4's binding startup-buffering contract.
6. **Active-manager ghost**: `phase-04:6` and `phase-06:314,317` (lifespan sketch)
   reference a component no phase builds.
7. Smaller: Phase 7 `:324` calls debounce "the same per-key timer pattern from
   Phase 4" (that's Phase 4's named anti-pattern); Phase 2 `:247` "exact DB_SCHEMA"
   claim omits the UNIQUE constraint + indexes; `http-fundamentals.md:247` uses
   `vars(node)` which Phase 6 explicitly bans; Phase 0 `:129` "renames the inode"
   (it swaps the directory entry); Phase 1B Relation Hygiene (`:151-174`) written
   as built but unimplemented in solutions; undefined-at-first-use terms: ripgrep,
   slugify, Tauri, anti-entropy, Bresenham/force-directed/supersampling (stretch).

Per-phase quality scores: 00 → 4.5 · 1A → 4 · 1B → 4 · 02 → 4.5 · 03 → 3.5 ·
04 → 5 · 05 → 4.5 · 06 → 4.5 · 07 → 4 · 08 → 4.5. Skeleton WHAT/WHY/HOW
docstrings: best-in-class (genuinely teach, e.g. `phase_02/db.py` close-under-lock
and FTS5 rationale).

---

## 4. Explanation GAPS (things that still need explaining)

1. **No graphs foundation doc** — 15 foundations explainers (even direnv, MkDocs)
   but none for the curriculum's core domain. Missing: representation tradeoffs
   (adjacency list/matrix/CSR), "the SQL edge table IS an adjacency list +
   recursive CTEs do bounded BFS in SQLite", supernode blowup, library landscape
   (NetworkX is used in Phase 5 with zero scaling discussion). noteapp's
   `04-graphs-for-engineers.md` targets exactly this audience.
2. **Ego-graph budgeting** — node-count limit + `truncated` flag + hub-explosion
   rationale absent at the moment learners build that exact API (Phases 3/6);
   noteapp learned this in its own Round 2 (#26).
3. **"What can this graph compute?"** — zero curriculum mentions of centrality,
   PageRank, community detection, link prediction. Phase 3 ends at BFS. noteapp's
   research suite 01+02 is ready-made source material (incl. Personalized PageRank
   as the ego-graph upgrade narrative).
4. **Edge-lifecycle / failure-mode taxonomy** — "body-derived edges are re-derived
   every index; frontmatter edges persist; here's every way an edge can disappear"
   stated once, in one place (noteapp's troubleshooting doc has the model). Includes
   the unspecified duplicate-title resolution policy (noteapp: oldest-wins + warning).
5. **FTS5 external-content sync** (see defect #2 — explain, don't just fix).
6. **Vector RAG / embeddings primer** — Phase 8 defines Graph RAG by contrast to
   vector RAG, which is never explained anywhere.
7. **Prompt injection explainer** (Phase 8 bare prerequisite) + Pydantic foundation
   link (Phase 6 prerequisite).
8. **Regex technique for skipping fenced code blocks** — Phase 1A's hardest
   mechanical step has zero guidance.

---

## 5. Quick-vs-complete explanations — recommendation

**Do NOT tier everything.** The curriculum already has an unnamed two-tier system:
phase-doc Concepts sections (quick) → `docs/foundations/` (complete) →
WHAT/WHY/HOW skeleton docstrings (point-of-use), routed by the prerequisite
self-assessment. Duplicating parallel quick/complete files would recreate the
multi-copy drift problem Round 5 + `sync_forward.py --check-all` just eliminated.
The audience is one tier wide (Python devs = noteapp's "for engineers" tier);
noteapp needs 3 tiers because its docs serve users, engineers, AND researchers.

**Adopt from the pattern:**
- The **audience/effort contract header** — one line atop each foundation doc:
  *"Audience: Python devs, no prior graph theory. ~15 min."* (the genuinely good
  feature, costs one line per doc).
- Tier ONLY the heaviest topic (graphs), where the complete tier is missing:
  - `docs/foundations/graph-theory-basics.md` (NEW) — adapt noteapp
    04-for-engineers: representations + cheat sheet, SQL-edge-table-as-adjacency-list,
    recursive CTEs, supernodes/budgets, library landscape; end with a further-reading
    link-out for the formal tier (link, don't port).
  - `docs/foundations/graph-algorithms-beyond-bfs.md` (NEW, enrichment) — condensed
    noteapp 01+02: centrality table, community detection, link prediction,
    Personalized PageRank as "what your Phase 3 graph can do next", with Solo/Group
    Reflect prompts.

---

## 6. Highest-value content additions from the session discussions

1. Graph-theory foundations docs + Phase 3 budgeting extension (above).
2. **"Why dataclasses + services, not OOP?" design sidebar** (Phase 1A or
   `design-patterns.md`) — the session has the full arc: god-classes vs anemic
   dataclasses + services, "graphs seem like a perfect OOP example" counterpoint,
   resolution. Currently recorded nowhere in either repo.
3. **Alias-rule tradeoff lesson** (R2 #7) as a Phase 1A design-decision sidebar
   (interop vs typed-edge semantics, "decide before data accretes", the accepted
   import residual) — AND record the curriculum's any-pipe-is-a-relation divergence
   in the decision log (currently undocumented).
4. **Resolve F1** — either port file-first persistence, or (arguably better
   pedagogy) add a Phase 6 pitfall + test showing the DB-only edge FAILS
   `test_db_is_expendable`'s invariant, turning noteapp R2 #4 into a taught lesson.
5. **Schema-vs-open-dict sidebar** — the FRONTMATTER_SCHEMA considered-and-rejected
   story (when a typed interface earns its keep vs an open dict + normalization
   boundary, which the curriculum already ported as `_normalize_fm`).

---

## Suggested execution order

1. **P0**: F1 manual-edge file-first (or doctrine-violation lesson) + un-pin
   `tests/phase_06/test_server.py:201-260`.
2. **P1 correctness**: Phase 3 broken reference code · sqlite-basics FTS5 section ·
   yaml doc noteapp-era tail · F3 slug consolidation + silent-overwrite fix · F4
   rederive trigger · F2 alias rule (+ decision-log entry) · 71→72 propagation ·
   asyncio-primer drift · active-manager ghost.
3. **P2 content**: two graphs foundation docs · ego budgeting · audience headers ·
   design sidebars (OOP, alias tradeoff, schema-vs-dict) · edge-lifecycle box ·
   vector-RAG/prompt-injection primers · F5/F6/F7 TEACH items · glossary one-liners.
