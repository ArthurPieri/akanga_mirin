# Adversarial Analysis V2 — Akanga Mirin Learning Path

> **Date:** 2026-06-09 · **Audience:** contributors — internal analysis, not learner content
> **Purpose:** Round 2 adversarial analysis. Round 1 (`adversarial-analysis.md`) asked "is this the right thing?" — this round asks **"are the mechanisms sound?"**, with Round-3 flavor (what happens when real learners hit this).
> **Method:** 10 parallel analysis agents (pedagogy, contracts, test coverage, infrastructure, security+privacy, software architecture, product, UI/UX+accessibility, KG/ontology, tech-writing/IA) over the full repo, the noteapp reference implementation, and the Claude Code session history. Every quantitative claim verified by direct execution where possible (pytest runs, make targets, git inspection, SQLite inspection).

---

## Scope and Prior Rounds

**Not retreaded (decided in Round 1, recorded in CLAUDE.md §Key design decisions):** Phase 1A/1B split · solutions-on-branch decision · Solo/Group reflect tracks · prerequisite self-assessments · open-ended vault exercises. Where this round touches them, it attacks *execution*, not the decision.

**Verified ground truth this round established (corrects several stale beliefs):**
- All 11 phase docs, all 9 skeletons, **145 test functions across all 9 phases** exist (CLAUDE.md/README/implementation-plan all claim otherwise).
- `pytest tests/` (full suite) fails collection with 5 errors; per-phase runs work.
- The learner's own `./src` Phase 0 implementation passes all 14 phase-0 tests **with `create()` still raising NotImplementedError** — confirming `create()` is untested.
- noteapp (reference impl) has **no** `create()`, **no** `graph.py`, **no** MCP/RAG module, **no** workspace registry → phases 1B, 3, 8 are unproven designs.
- noteapp security fixes verified present: SEC-02 (`server.py:217-222`), SEC-06 (`db.py:214`), 127.0.0.1 binding (`cli.py:31`).
- `solutions/phase_08/*.db`: **NOT tracked in git, never were; both databases are empty** (0 rows / 0 bytes). No personal-data leak. Working-tree cleanup still warranted.

---

## Consolidated Critiques

*38 raw critiques from 10 agents, deduplicated into 14. Sources noted as [A1..A10]. Severities: CRITICAL (failure/harm) · SERIOUS (reduces success probability) · MODERATE (needs design attention) · STRUCTURAL (systemic).*

---

### 1. `make skeleton PHASE=N` silently destroys learner work for every phase after the first [CRITICAL] — A4

`Makefile:304-314` does `cp -r "$SKEL/src/." src/` with no overwrite guard. Later-phase skeletons ship 3-line "marker" files (`skeletons/phase_03/src/akanga_core/parser.py:1-3`) that share names with the learner's completed modules. A learner finishing Phase 2 who runs `make skeleton PHASE=3` (the README-trained gesture) replaces 15–25h of work with placeholder comments — and `/src/` is gitignored, so there is **no recovery**. Phase 5's skeleton ships an empty `akanga_core/__init__.py` that can shadow the learner's real package [A2]. `sync_forward.py --apply` would compound it by overwriting marker files with prior-phase stubs.

**Fix:** never overwrite existing files in `skeleton` (`cp -n` / skip-existing + "preserved N files" message); copy only new-module stubs; make `sync_forward.py` refuse marker files and exit non-zero on drift.

---

### 2. Docs, skeletons, and tests describe different programs — systemically [CRITICAL] — A1, A2, A3, A8

The single largest cluster. The deliverable contract diverges in both directions in at least 6 of 9 phases:

- **Three irreconcilable `Node` contracts** in phases 0/1/2 under the same import path; the 01→02 transition deliberately breaks the learner's phase-1 tests (`skeletons/phase_02/.../parser.py:1-10`). `Edge` changes shape three times. [A2, A6]
- **`NodeType` has no `"reference"` member** while phase 1B's entire deliverable is reference nodes — a skeleton-conformant parser raises `ValueError` on curriculum-mandated input. [A2]
- **Doc-faithful learners fail tests on renames:** doc `depth=` vs test `max_depth=` fails **all 12 phase-3 tests** on a correct algorithm; phase-6 doc's `NodeCreate` schema (no `path` field) makes the SEC-02 security test **unpassable**; phase-8 doc says `init_server` "does not exist" while skeleton defines it and tests prefer it. [A2]
- **Phase 5 is three different apps:** doc specs inline TextArea editing, skeleton suspends to `$EDITOR`; doc forbids ASCII graphs, skeleton suggests them; `G` double-bound; `graph_screen.py`/`graph_renderer.py` have no skeletons, no deps, no tests. [A8]
- Phase-0 doc deliverable tests are fiction (all built on untested `create()`); tests enforce 5 behaviors the doc never states (UUID generation on missing/invalid id, type default, dir creation, malformed-YAML raise). [A1, A3]
- **Phase 07 is the proof the right pattern exists** — doc, skeleton, and tests agree symbol-for-symbol. Eight phases predate it.

**Fix paths:** (1) declare skeleton+tests normative, sweep all doc signature snippets (~10 enumerated edits in A2's appendix); (2) pick ONE Node shape (phase-02's + keep `frontmatter`) and make it monotonic from Phase 0; (3) CI lint diffing doc code-fence signatures against skeleton ASTs — this defect class is mechanically detectable.

---

### 3. Each phase's self-declared "most important" deliverable is exactly what's untested [CRITICAL] — A2, A3, A1

- `create()`: promised by 3 docs, stubbed in 1 phase, carried forward by 0, tested by 0 (dead `create_fn`/`tmp_vault` fixtures).
- Phase 2: `test_db_is_expendable` ("proves the core architectural promise") — missing. Two-pass edge resolution — `test_indexer.py` never creates a single edge; an indexer that extracts zero edges passes the whole phase, silently breaking phases 3/5/8 three phases later. Thread-safety: zero tests.
- Phase 4: the async bridge (`set_loop` + `run_coroutine_threadsafe`) and `SyncWorker.drain` — the two hard concurrency artifacts — zero tests.
- Phase 6: WebSocket + node-file-written tests ("the most important") — missing; `/templates` tested but undocumented.
- Phase 5: 2 of 6 required keyboard actions tested; live-update pipeline untested; unconfirmed `d`-delete passes the phase.
- Error paths (CCR-9): genuinely closed in 7/9 phases; phase 01 has zero; phase 08's is vacuous.

**Fix:** port the doc-specified tests that already exist as sketches (`test_db_is_expendable`, `test_two_pass_edge_resolution`, async-bridge test, drain test, 2–3 `create()` tests); or rewrite Deliverable sections to enumerate actual test names (phase-07 pattern).

---

### 4. Vacuous and self-defeating test assertions — including security tests weaker than the prose [CRITICAL] — A3, A5b

- **SEC-04 punishes correct work:** `test_mcp.py:424` asserts `"0.0.0.0" not in source`, but the skeleton's own security comments contain "0.0.0.0" three times — every skeleton-following learner auto-fails.
- **BUG-03 "coverage" is vacuous:** `test_serialize_triples_outgoing_direction` passes even with inverted semantics; no test exists for incoming/inverse rendering.
- **BUG-02 self-referential:** `getattr(rag, "MAX_CONTEXT_CHARS", 12_000)` lets the learner define their own cap. 71-relation-types test accepts ≥10. Nonexistent-node error test accepts any string.
- **SEC-06 passable by exception-swallowing** (`try/except: return []` passes both FTS-injection tests); no embedded-double-quote test, though the reference impl needed that exact handling.
- **SEC-02 passable by the doc-banned `".." in path` check**; no absolute-path, slug-traversal, or symlink test — though SECURITY.md lists symlink escape as in-scope and only `resolve()` defeats it.
- **OS-dependent verdicts:** read-only-DB test (chmod after fd open + WAL) likely fails the curriculum's own prescribed architecture; 4 residual timing gambles in phase 4; TUI title-scrape misses `DataTable`/`OptionList` implementations. [A3]

**Fix:** semantic assertions (search for literal `OR` term must match a node titled with it; whole-triple-line asserts; `MAX_CONTEXT_CHARS == 12_000`; symlink fixture); AST-parse instead of substring for SEC-04.

---

### 5. The concurrency model codifies BUG-04 instead of fixing it; the bridge is taught three contradictory ways [CRITICAL] — A6

- `architecture-overview.md:71-74` teaches `call_soon_threadsafe` (wrong as written), `architecture-detailed.md:248-250` a lambda/create_task variant, phase-04 + skeleton + tests `run_coroutine_threadsafe`.
- The skeleton's fallback ("if loop not set, call handler directly", `eventbus.py:120-127`) **is** the BUG-04 race — and the canonical startup sequence (`phase-04:199-211`) never calls `set_loop()` at all.
- Async handler exceptions vanish (un-retrieved Futures) — contradicting the phase's own "error isolation" invariant.
- Doc and skeleton prescribe contradictory debounce designs (Timer-per-path vs single worker), and the worker has no stub, no stop signal, no join.
- Self-write echo loop (drain → watcher → reindex → commit) and macOS `os.replace`→`on_moved` (BUG-05) remain untaught.

**Fix:** make `publish()` before `set_loop` loud (raise or buffer); add `set_loop` to the canonical sequence + one deliverable test; done-callback logging on the Future; reconcile the debounce design.

---

### 6. The relation vocabulary's core contracts are broken by the curriculum's own artifacts [CRITICAL] — A9, A6

- **"IDs are stable forever" is violated three ways:** vocabulary says `EP-001 = supports`; phase-8 `SERVER_INSTRUCTIONS` teaches `EP-001 = "contradicts"`; the plan doc gives a third assignment with a phantom inverse (`EP-002 is_contradicted_by`).
- **Relation IDs never reach the DB** — edges are keyed by display name only (`upsert_edge(..., relation="...")`); "filter by EP-002", the entire payoff of stable IDs, is unimplementable; phase-8 dedup by `relation_id` (uniformly `""`) collapses distinct relations between the same pair.
- **BUG-03 is a vocabulary-design gap:** 51 of 71 directed types have no defined inverse, so incoming-edge rendering has no sanctioned label; the phase-8 `<-[rel]-` comment is the literal textual source of the bug.
- **Phase 3 sanctions `relation=""`** (forced by Phase 2's API returning Nodes, not edges) → every phase-8 RAG triple degrades to `relates_to`; the 71-type vocabulary never reaches the LLM. `EgoEdge.direction` is built in phase 3 and never consulted in phase 8. [A6]
- YAML key drift: `relation-id` (doc) vs `relation_id` (test fixtures).

**Fix:** declare `relation-vocabulary.md` the single registry + audit every `XX-NNN` literal (CI-checkable); adopt "EgoEdge always stores natural direction; serialization always renders `src --[rel]--> tgt`"; spec `get_edges_from/to` in Phase 2 so relations are free in Phase 3.

---

### 7. The solutions strategy is in a three-way contradictory state; the one shipped solution fails its own tests [CRITICAL/STRUCTURAL] — A4, A5b

- Decision says `solutions` branch; no branch exists; tooling (Makefile, CI) reads `solutions/` from the working tree; only `solutions/phase_08/` exists on main — violating the decision the repo records. CLAUDE.md's "don't modify solutions/ — the branch is authoritative" makes contribution impossible.
- README quickstart's `make test-solution PHASE=0` fails on day one; CI quietly certifies 1/9 phases while looking green.
- **The phase-08 solution would fail the phase-08 tests:** wrong delimiters (`<graph_context>` vs SEC-01's `[KNOWLEDGE GRAPH CONTEXT …]`), no anti-injection sentence, stores prose `body` in the DB (the phase-2 architectural violation), no SEC-02 code, 2 of 5 MCP tools. It teaches the anti-patterns the tests prohibit. (Its two `.db` files: verified untracked + empty — delete from working tree.)
- Phases 1B/3/8 solutions can't be "derived from the reference" — noteapp never built those modules.

**Decision required:** abandon the branch decision (recommended — all tooling already assumes directory-on-main) or implement it; either way fix README:58, make CI loud about coverage, and replace or delete the failing phase-08 solution.

---

### 8. The 1A/1B split exists only in prose — every tool routes learners to the superseded doc [SERIOUS/STRUCTURAL] — A1, A4, A10

`Makefile:109`/`study.sh:45` glob `phase-01-*.md`, which matches **only** the superseded doc (whose schema fails the shipped tests); `PHASE=1a` crashes on `printf %02d`; `make docs-all` silently skips phase 1; mkdocs nav lists superseded + 1A + 1B as siblings; both 1A and 1B Quick Starts tell learners to run the command that opens the wrong doc; tests are monolithic so a 1A learner has no green stopping point.

**Fix:** archive the superseded doc + glob `phase-01[ab]-*` (or accept `PHASE=1a|1b`); split or `-k`-filter the tests; add 1A/1B rows to `make status`.

---

### 9. Status-layer rot: the repo's front pages describe a repo that no longer exists [SERIOUS] — A4, A7, A10

- CLAUDE.md wrong on ≥4 load-bearing claims (tests/skeletons "not written"; solutions branch; AKANGA_SRC "falls back to solutions" — actual behavior is fail-fast; sprint mapping). It is auto-loaded into every Claude Code session — sessions will recreate existing tests or chase phantom behavior.
- **README "380 hours" is almost certainly a 10× typo** (per-phase table sums 32–48h; 38h ±30% = 26.6–49.4h). README claims a facilitator guide "ships" — it doesn't exist. "Coming soon" labels on shipped artifacts. Three estimate systems across two hubs. "Nine phases" vs 10/11.
- implementation-plan arithmetic (CCR-2) confirmed worse: 270h header vs 230h sprint-sum vs 192.5h category-sum vs ~181h unique (MKT items double-counted).
- Commit e9209ff contaminated main: tracked `.pyc` binaries, `src/` learner code, `src/.claude/settings.local.json`, `my_implementations/` — and registered `my_implementations` as a uv workspace member, so every learner's `make setup` syncs the author's scratch project. `.gitignore` rules are inert for already-tracked files.
- CI exists but is defanged: `ruff check || true` can never fail; no tracked-vs-gitignore check; no binary/size check.

**Fix:** 1–2h editorial sweep (CLAUDE.md, README:26/36/58/121-123, plan status flips); `git rm -r --cached` the contamination; remove `|| true`; add CI guards (`git ls-files -i -c --exclude-standard`, >1MB check, `*.db` tracked check).

---

### 10. The planned security curriculum was written but never inserted; phase docs claim teaching that doesn't exist [SERIOUS] — A5b

S1 (parameterized SQL → phase 2), S2 (CORS → phase 6), S3 (YAML safe-load → phase 0), S4 (auto-push/remote trust → phase 7) are fully drafted in `plan-security-and-deployment.md` with exact insertion points — none was inserted (~1.5h total per the plan's own estimate). Phase 6's learning objective promises CORS teaching that never appears (the skeleton imports `CORSMiddleware` and never uses it — inviting the wildcard config S2 warns against). Phase 7 auto-commits the personal vault with **zero** warning about permanent history, no `auto_push: false` default, no remediation guidance.

**Fix:** execute T2–T5 of the existing plan (insertion task); add `auto_push: false` to phase-7's What You Build; until S2 lands, drop the CORS objective or the dangling import.

---

### 11. Phase 8 connects the personal vault to a cloud LLM without one sentence on data egress [MODERATE] — A5b

Seven phases teach "local-first, nothing leaves your machine"; phase 8 inverts this silently. No "what leaves your machine" callout, no scoping mechanism (e.g., a `private` tag excluded from MCP tools), no local-model mention; SECURITY.md's single-user threat model never updates. The 127.0.0.1 lesson can create false comfort — data leaves via the client, not the socket.

**Fix:** egress callout (5–8 sentences); a `private`-tag exclusion as a tested deliverable; local-model note; threat-model update.

---

### 12. The prescribed study environment breaks the flagship Phase 5 feature — a trap the author personally hit and never wrote down [SERIOUS] — A8

`make study` always wraps in tmux; the Kitty graphics protocol (Layer 1 graph renderer) doesn't survive tmux by default (needs `allow-passthrough on`, tmux ≥3.3, and detection inside tmux is unreliable). The author's own multi-hour tmux/TUI fight (May 24 session: "I don't want you to fix tmux any more") was never documented. Compounding: `make run`/`make serve`/`make mcp` don't exist; `textual-kitty`/`textual-canvas`/NetworkX not in pyproject; skeleton has no `__main__`; `templates/project-makefile`'s `init-vault` writes an `akanga.yaml` schema nothing else can parse [A7]. Foundation tmux doc teaches a phantom env var and wrong session names; `study.sh` validates the doc path but none of its 4 binary deps. Accessibility: color-only node-type encoding; one backlog row total. [A8]

**Fix:** tmux/Kitty callout in phase-5 (spend the war story); phase-aware `study.sh` warning or `allow-passthrough`; real `run` target + optional `[graph]` dep group; fix `init-vault` schema; preflight check in study.sh; "shape + color, never color alone" in the renderer spec.

---

### 13. "The vault is the proof of understanding" — and nothing ever looks at it; the value curve is inverted [SERIOUS] — A1, A7, A3

- No test, target, or rubric touches the vault; `validate_vault.py` exists but is wired to nothing and can't check the per-phase tables. Phase 0's table demands typed edges taught in 1A using tools not yet built (`akanga init` doesn't exist anywhere); "Plus 7 nodes" under an 8-row table. Learners optimizing for green tests will skip the curriculum's differentiator — and learn that non-tested instructions are optional, corroding doc authority for the instructions that matter.
- The roadmap's own MVP (0→1→2→6, ~10–14h) proves phases 3–5 aren't prerequisites for usefulness, yet the linear path inserts a ~20h dry stretch (phases 3→4→early-5: nothing the learner can open or show) terminating at the 12–20h Phase 5 cliff — directly contradicting "ship a working artifact every phase." [A7]
- Effort signaling: phase docs carry no time estimates in headers; the 5× phase-5 jump is acknowledged but unscaffolded (no internal checkpoints; tests certify only the first slice). [A1]

**Fix:** `make vault-check PHASE=N` running the learner's own indexer over their vault (the dogfooding loop *is* the pedagogy); re-scope phase-0's table to untyped wikilinks; publish the 0→1→2→6 fast path officially; give phases 3/4 a 20-minute "see it work" capstone; checkpoint phase 5 internally (5.1/5.2/5.3 mirroring the 1A/1B precedent).

---

### 14. Knowledge-graph integrity has three open loops; the architecture docs describe a third system [SERIOUS/STRUCTURAL] — A9, A6, A10

- **Integrity loops [A9]:** typos silently mint new relation types with fresh UUIDs (no validation anywhere — the learner's own `edges.py` TODO flags it); node deletion dangles edges forever (no repair, no report — phase-8 serializer silently drops them); rename convergence is "guaranteed" but provably isn't (out-of-order drain of A→B, B→C converges wrong permanently; no anti-entropy scan exists in any phase).
- **Vocabulary factoring [A9]:** the curriculum's own vault tables use 14 of 71 types; five types mean "supersedes"; four mean "weak link"; `instance_of` is missing while exercises misuse `subtype_of` for it (Nhamandu is an *instance* of Guaraní Deity); both members of inverse pairs are first-class with no canonicalization rule.
- **Architecture docs [A6]:** `architecture-detailed.md` still has `body` in the DB schema (the documented *origin* of BUG-01), `Database.setup()` vs `GraphDatabase`, `<graph_context>` delimiters, `call_soon_threadsafe`, wrong `build_context` signature — an 8-row divergence table; these are the tie-breaker docs a confused learner opens, and they lose every tie. The WAL "deadlock" claim is wrong (it's `SQLITE_BUSY`; WAL's real payoff here is cross-process).
- **Foundation docs [A10]:** `sqlite-basics.md`'s capstone example teaches prose-in-DB + FTS-on-content — the exact phase-2 violation; several foundation docs reference noteapp file paths that don't exist here. Four self-assessment remediation links point at sections that don't exist (LPG, Graph Traversal, queue patterns, HTTP security). MkDocs builds+indexes all 42 docs: learners searching "sync queue" surface the Round-1 bug list with no "historical" banner; the designated "start here" hub (`docs/README.md`) is unreachable on the site (index.md shadows it).

**Fix:** soft validation + nearest-match warning at write-back; `dangling_edge` job type + one deliverable test; `akanga sync --full` anti-entropy command (drain should re-read current truth by `entity_id`); tiered "core 15" vocabulary + `instance_of` + canonical-member rule; regenerate/banner the architecture docs ("phase docs win on conflict"); rewrite noteapp-voiced foundation sections; `exclude_docs` or `docs/_internal/` quarantine for planning artifacts.

---

## What This Analysis Does NOT Challenge

- The **core pedagogy design**: build-to-learn, WHAT/WHY/HOW skeleton docstrings (preempting wrong solutions at expert level), teaching-quality test failure messages, the Solo/Group reflect prompts, self-assessment checklists. All ten agents independently praised these.
- The **file-first / derived-index architecture** and its teaching (where tests exist, e.g. SEC-01 delimiter-survives-truncation is exemplary security pedagogy).
- The **dual-key (name/ID) pattern** itself — sound SKOS practice; the failures are registry discipline, not design.
- **Phase 07's contract alignment** and **phase 06's test suite** — the templates the other phases should converge to.
- The **AKANGA_SRC harness** — Round 1's CCR-3 silent failure modes are substantially fixed (fail-fast with copy-pasteable remediation).
- The **Makefile's engineering** (status matrix, TESTED=0 guard, loud warnings) — failures are state drift around it, not in it.
- Round-1 decisions: 1A/1B split, solutions branch (as a decision — its execution is critiqued), reflect tracks, self-assessments.

---

## Risk Matrix

| # | Risk | Severity | Requires |
|---|------|----------|----------|
| 1 | `make skeleton` destroys learner work, unrecoverably | CRITICAL | Code fix (Makefile guard) |
| 2 | Doc↔skeleton↔test divergence in 6/9 phases (Node fork, renames, NodeType) | CRITICAL | Decision (source of truth) + sweep + CI lint |
| 3 | Flagship deliverables untested (`create`, db-expendable, async bridge, drain) | CRITICAL | Test authoring (sketches exist in docs) |
| 4 | Vacuous/self-defeating tests incl. SEC-04 auto-fail, BUG-02/03 non-coverage | CRITICAL | Test fixes |
| 5 | BUG-04 codified in skeleton; bridge taught 3 ways; startup omits `set_loop` | CRITICAL | Spec decision + skeleton/doc fix |
| 6 | Relation-ID contract broken; vocabulary IDs contradict across docs; `relation=""` guts Phase 8 RAG | CRITICAL | Registry decision + audit + Phase-2 API addition |
| 7 | Solutions strategy 3-way contradiction; shipped solution fails own tests | CRITICAL/STRUCTURAL | **Decision required** (branch vs dir) |
| 8 | 1A/1B split unexecuted in tooling; learners routed to superseded spec | SERIOUS/STRUCTURAL | Small code+doc fixes |
| 9 | Status-layer rot (CLAUDE.md/README/plan); repo contamination (e9209ff); defanged CI | SERIOUS | Editorial sweep + git cleanup + CI teeth |
| 10 | Security curriculum S1–S4 drafted, never inserted; CORS objective is a false claim | SERIOUS | ~1.5h insertion task |
| 11 | Phase-8 data egress unaddressed | MODERATE | Doc callout + 1 tested mechanism |
| 12 | tmux/Kitty trap on the most expensive phase; phantom targets; missing deps | SERIOUS | Doc callout + Makefile/pyproject fixes |
| 13 | Vault-proof mechanic unenforced; inverted value curve; phase-5 cliff unscaffolded | SERIOUS | Tooling (`vault-check`) + path restructure decision |
| 14 | KG integrity loops (typo-minting, dangling edges, non-converging renames); architecture/foundation docs teach the wrong system; MkDocs audience leakage | SERIOUS/STRUCTURAL | Design decisions + doc regeneration + nav quarantine |

---

## Suggested Priority for Resolution

**Tier 0 — before anyone else clones this (hours, mostly mechanical):**
1. Makefile `skeleton` overwrite guard (#1) — the only finding that destroys work.
2. Status-layer sweep: CLAUDE.md rewrite, README 380h/facilitator/coming-soon fixes, `git rm --cached` contamination, delete empty `.db` files, CI `|| true` removal (#9, part of #7).
3. 1A/1B glob fix + archive superseded doc (#8).
4. Phantom make targets: add `run`/`serve`/`mcp` or delete the Quick Start lines (#12, #13).

**Tier 1 — decisions that unblock everything else (discussion, then execution):**
5. Solutions: branch or directory? (#7) — blocks solution authoring for 8 phases.
6. Source of truth: skeleton+tests normative? One Node shape? (#2) — blocks the doc sweep.
7. EgoEdge orientation rule + relation-ID registry authority (#6) — blocks BUG-03 closure and Phase-8 correctness.
8. EventBus bridge pattern + loud-failure mechanism (#5).

**Tier 2 — test debt (Sprint-2-shaped work):**
9. Port the missing flagship tests (#3); fix the vacuous/self-defeating ones (#4); insert S1–S4 (#10).

**Tier 3 — curriculum quality (larger arcs):**
10. Vault-check tooling + fast-path route + phase-5 checkpoints (#13).
11. KG integrity mechanisms + vocabulary tiering + architecture-doc regeneration + MkDocs quarantine (#14, #11).

---

## Appendix — Agent Coverage Map

| Agent | Perspective | Critiques contributed |
|---|---|---|
| A1 | Pedagogy & onboarding | #2, #3, #8, #13 |
| A2 | Contract consistency (full per-phase table in its report) | #2, #3, #8 |
| A3 | Test coverage (full traceability matrix in its report) | #3, #4, #13 |
| A4 | Infrastructure & ground truth | #1, #7, #8, #9 |
| A5b | Security & privacy | #4, #7, #10, #11 |
| A6 | Software architecture | #2, #5, #6, #14 |
| A7 | Product strategy | #9, #12, #13 |
| A8 | UI/UX & accessibility | #2, #12 |
| A9 | Knowledge-graph/ontology | #6, #14 |
| A10 | Tech writing / information architecture | #8, #9, #14 |

Raw agent reports preserved in the session transcript. Verification corrections made during synthesis: D1's "phases 3–8 tests are empty" claim was false (class-based tests; 145 total); A5b's "personal data in committed DBs" worst case did not materialize (untracked + empty).

---

## Resolution Log

*Status as of 2026-06-10 (batch 2 complete). Tier 0 → commit `afcaa4b`; batch 1 → `b9db63b`; batch 2 → this commit. Verification gate: phase-8 solution 23/23 green, skeleton_check 9/9, ruff clean, mkdocs builds, doc-contract lint OK.*

| # | Finding | Status | Resolution |
|---|---------|--------|------------|
| 1 | `make skeleton` destroys learner work | **Resolved** 2026-06-10 (Tier 0) | Skeleton copy now skip-existing with a "preserved N files" message; `sync_forward.py` refuses marker files and exits non-zero on drift |
| 2 | Doc↔skeleton↔test divergence | **Resolved** 2026-06-10 | Skeleton+tests normative (D2/D3); doc sweep done (R3–R5); monotonic Node landed (R2); `scripts/check_doc_contracts.py` CI lint guards against regrowth (R14) — caught+fixed 2 drifts on first run |
| 3 | Flagship deliverables untested | **Resolved** 2026-06-10 | R1: 3 `create()` tests, `test_db_is_expendable`, `test_two_pass_edge_resolution`, `test_sync_worker.py`, set_loop/buffering tests, phase-01 error paths (110+ tests collect) |
| 4 | Vacuous/self-defeating test assertions | **Resolved** 2026-06-10 | R1: AST-based SEC-04, whole-line direction asserts + incoming-edge test, `MAX_CONTEXT_CHARS==12_000` pinned, 71-type floor, semantic SEC-06, absolute-path+symlink SEC-02, monkeypatched read-only test |
| 5 | BUG-04 codified; bridge taught 3 ways | **Resolved** 2026-06-10 | D6: deque buffering specced in skeleton + doc (R2/R4); startup sequence includes `set_loop`; Future done-callback logging; single-worker debounce; architecture docs corrected (R6) |
| 6 | Relation-ID contract broken | **Resolved** 2026-06-10 | D5: vocabulary = single registry; ID literals fixed in phase-08/plan docs (R5/R6); `get_edges_from/to` specced (R2/R3); `instance_of` + core-15 tier added (R6); BUG-03 guidance deleted (R2/R5) |
| 7 | Solutions strategy 3-way contradiction | **Resolved** 2026-06-10 | Branch decision reversed (D1); `solutions/phase_08` now passes its full suite **23/23** (R7c) |
| 8 | 1A/1B split unexecuted in tooling | **Resolved** 2026-06-10 (Tier 0) | Makefile/study.sh accept `PHASE=1a`/`1b` and glob `phase-01[ab]-*`; superseded doc archived |
| 9 | Status-layer rot; repo contamination | **Resolved** 2026-06-10 (Tier 0, partial) | CLAUDE.md/README editorial sweep done; git contamination removed; remaining CI-teeth items tracked in the remediation batch |
| 10 | Security curriculum S1–S4 never inserted | **Resolved** 2026-06-10 | S1→phase-02, S2→phase-06, S3→phase-00, S4→phase-07 inserted (R3/R5); CORS objective now backed by teaching + skeleton guidance |
| 11 | Phase-8 data egress unaddressed | **Resolved** 2026-06-10 | "What leaves your machine" callout + `private`-tag mechanism specced (R5); SECURITY.md threat model gains LLM-egress channel (R16) |
| 12 | tmux/Kitty trap; phantom targets; missing deps | **Resolved** 2026-06-10 | Targets + tmux warnings in doc and `make run` (R4/Tier 0); `[graph]` extra; init-vault canonical schema; study.sh preflight (R8); tmux foundation doc synced (R6b) |
| 13 | Vault mechanic unenforced; inverted value curve | **Resolved** 2026-06-10 | `vault-init`/`vault-check` + per-phase manifests + relation validation (R8); fast path in README + phase-02 closer; phase-3 capstone; phase-5 checkpoints 5.1–5.3 (R4); facilitator guide written (R13) |
| 14 | KG integrity loops; architecture docs teach wrong system | **Resolved** 2026-06-10 (anti-entropy `sync --full` deferred to V1) | Relation-hygiene + convergence contract in 1B, dangling-edge policy in phase-04 (R16); architecture docs subordinated + corrected (R6); foundation docs re-voiced; MkDocs quarantine via `exclude_docs` (R6b) |
