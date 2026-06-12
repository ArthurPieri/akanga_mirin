# Adversarial Analysis V3 — Akanga Mirin at Scale

> **Date:** 2026-06-11 · **Audience:** contributors — internal analysis, excluded from the published site
> **Lens:** Round 3 — *"What happens at scale, with real users, over time?"* Operations, emergent behavior, second-run effects. Rounds 1 (`adversarial-analysis.md`) and 2 (`adversarial-analysis-v2.md`, 14/14 resolved) covered fundamentals and mechanisms.
> **Method:** 5 parallel analysis agents (cohort dynamics, vault-at-scale, solution-code review, maintenance physics, outcomes & ecosystem) armed with **measured data**: a 1,000-node/4,681-edge synthetic vault benchmarked against the solution code, and md5 drift measurement across the 9 solution trees. Key claims reproduced by the orchestrator before acceptance.

---

## Verified measurements (ground truth for this round)

- 1,000-node vault: index 1.26s (1.3ms/node); FTS 0.7ms; ego depth-2 on densest node = **167 nodes / 184 edges** (18.6ms); depth-3 = 800 nodes (160ms); DB 1.08MB.
- Re-index of a **completely unchanged** vault: 1.07s — only ~15% cheaper than cold. Explained by finding #1.
- **Edge duplication reproduced**: 3 identical scans → 2 → 4 → 6 edge rows (linear corruption).
- Solution-tree drift (md5): `db.py`/`parser.py` byte-identical where copied; `graph.py` ×4 distinct versions, `watcher.py` ×4, `eventbus.py` ×3 — every copy green, none identical, and the deltas are **semantic** (see #2, #3).

**Corrections owned during synthesis:** A4's claim that CLAUDE.md still describes the pre-D1 world was **wrong** (fixed in Tier 0; verified) — withdrawn. A5 verified the phase-8 doc's "tests are being strengthened" note is stale in the *other* direction (they already were).

---

## Consolidated Findings

### 1. The index is append-only: every re-scan duplicates every edge [CRITICAL — reproduced]
*A2 + A3, independently; orchestrator-verified (2→4→6).*
`upsert_edge` is a blind `INSERT` with a fresh uuid4 PK; the schema (from the **skeleton's own DB_SCHEMA**) has no `UNIQUE(source_id, target_id, relation)`; `full_scan_and_index` pass 2 re-derives and re-inserts every edge unconditionally. Consequences: weekly refreshes for a year ≈ 243k duplicate rows; `get_neighbors` masks it with `DISTINCT` while ego graphs/RAG triples surface it inside capped budgets; the indexer's own docstring claims idempotence. The hash-skip saves only ~15% because `index_file` parses + hashes *before* comparing, and pass 2 never skips. Deletion is never reconciled (deleted notes live in FTS/RAG forever); a no-id Obsidian vault gets its UUIDs re-minted **every scan**, orphaning edges each time.
**The drift is the proof:** phase_08's db.py has the fix (`UNIQUE` + `INSERT OR IGNORE`); phases 02–07 and the skeleton don't.
**Fix:** backport constraint + `INSERT OR IGNORE` into the phase_02-family `DB_SCHEMA` (skeleton AND solutions); hash-before-parse; per-changed-node `DELETE FROM edges WHERE source_id=?` then re-derive; tombstone pass for deleted paths; write minted UUIDs back to frontmatter; add a re-index idempotency test (`scan; scan; assert count unchanged`) — the missing test class this round exposed.

### 2. The capstone tree (phase_08) silently reverts the curriculum's flagship lessons [CRITICAL]
*A3.* phase_08's eventbus **reintroduces BUG-04 verbatim** ("Skipping async handler… no running loop") plus the GC'd-task footgun and no done-callback; its watcher drops the macOS resolve() fix (on a `/var` vault, **every event is ignored**), starts its thread in `__init__`, can't restart after stop, and sleeps instead of `Event.wait`; the TUI live-refresh is dead code twice over (`call_from_thread` from own thread + nothing ever publishes) with a literal `# ... graph rendering logic ...` elision. It pre-dates the 04–07 lineage and was gated only by tests that don't exercise these paths.
**Fix:** promote phase_07's eventbus/watcher into phase_08 (with #3's lock fix); make `_on_node_updated` sync; wire `AkangaApp` into `run_tui.py`; render or delete the ego panel.

### 3. The "fixed" eventbus family still has a TOCTOU that strands events forever; `_fire` correctness varies by copy [SERIOUS]
*A3.* `publish()` checks `self._loop` outside the lock → a `set_loop` interleaving leaves the event in the buffer with nothing left to drain it — the exact "silent loss" the docstring promises can't happen. `_fire` grades: phase_04 correct (re-checks deadline); phase_07 fires early on re-schedule; phase_05/06 additionally resurrect cancelled events (`file_changed` *after* `file_deleted`). `stop()` joins the worker before stopping the observer in 04–07 (events leak after shutdown); phase_08 alone orders it right.
**Fix:** set/check `_loop` and buffer-append under one lock; canonicalize phase_04's `_fire`; observer-first stop ordering; these interleavings need 2–3 targeted stress tests.

### 4. At year-2 density, Graph RAG contains no graph [SERIOUS]
*A2, from verified numbers.* Entities are emitted first at ~530 chars each: 12,000 ÷ 530 ≈ **22 of 167 entities** consume the whole budget, selected by BFS-discovery (= DB insertion) order; relations come second and ~0 of 184 survive. `max_triples=80` never engages. The `[KNOWLEDGE GRAPH CONTEXT]` block degrades to flat RAG with arbitrary selection — the failure mode the phase exists to beat. `build_context` hardcodes `max_depth=2`, calibrated on a 3-entity toy.
**Fix:** relations-first or split budget (60/40); rank by depth-then-typed-edges; root snippet 500 / neighbor 120; make depth a parameter; one doc sentence on density math.

### 5. Real editor/sync write signatures break the write path over time [SERIOUS]
*A2.* Per-save GitPython commits never `gc` (GitPython doesn't auto-pack): 2 years of Obsidian autosaves ≈ 36k–150k commits, 1.5–6GB of loose objects **on the same Dropbox/iCloud folder the README markets**; doc promises a 5s batcher the solution doesn't implement. Dropbox conflict copies carry the same frontmatter id → node identity flaps between files (no duplicate-id guard). vim's rename-backup makes every save a `file_deleted` for the real path (deletes are un-debounced "because deletions never arrive in bursts" — false); harmless today only because the delete handler is a no-op. Zero mentions of iCloud/Dropbox/OneDrive anywhere in the docs.
**Fix:** idle-interval commit batcher + periodic `gc --auto`; debounce deletes with a create-cancels-delete grace window; duplicate-id guard (log loud, keep oldest path); a phase-04/07 sync-services callout.

### 6. The answer key shipped and the curriculum doesn't know it — a status-claim drift wave [SERIOUS]
*A5 + A4 + A1.* Three docs actively deny the 9 solutions exist (`README.md:4,82,129` "Phase 8 only"; `facilitator-guide.md:17`; `solutions/README.md` — *"publishing them early would defeat the learning purpose"*, plus it redirects contributors to noteapp as reference). `CONTRIBUTING.md` (7 lines) forbids modifying `solutions/` — the only legal fix path under D1 — and still references SENTINEL machinery. **The Makefile's failure path prints the escape hatch** (`To test the solution: make test-solution PHASE=N`) at the exact moment of maximum temptation. No compensating honor-system norms shipped: no reasonable/not-reasonable policy, no peek ritual, nothing distinguishing earned from copied green; the only copy detector is the workshop pair-review (solo learners — persona #1 — have nothing).
**Meta-pattern:** every work batch fixes the previous batch's status claims and mints its own; the contract lint catches signature drift but nothing catches status-claim drift.
**Fix:** sweep the 6 stale spots; rewrite CONTRIBUTING (~40 lines: D1 reality, canonical-tree rule, pointer to D1–D11); CS50-style reasonable/not-reasonable list in solutions/README; `make peek` with learner-local PEEKS.md log; post-green "diff the reference, write one vault node on a difference" ritual; invert the Makefile failure message to point at the remediation ladder; consider a status-claims CI check (grep for "Phase 8 only"-class assertions vs `make status` truth).

### 7. The N-tree problem reborn in solutions — with divergent half-fixes already [SERIOUS/STRUCTURAL]
*A4 + A3.* The drift is semantic on day one: phase_04's `_log_future_exception` has the cancellation guard but the wrong Future type; phase_06 has the right type but no guard — **each tree holds half the correct implementation**. `sync_forward.py`'s overwrite model finally fits solutions (post-introduction layers *should* be identical — db.py/parser.py prove the discipline) but: it's destructive on the diverged files, its drift detection is unwired in CI, its solutions-before-skeletons precedence **silently changed the meaning of the CLAUDE.md example** when solutions landed, it's forward-only, and exit codes conflate drift with error. Trajectory after 5 single-tree community PRs: 6–9 versions per file, no tree containing all fixes.
**Fix (recommended policy):** introduction-phase-canonical per module, encoded in `scripts/sync_manifest.toml`; one-time convergence commit (merge the half-fixes); `sync_forward --base` flag + `--check-all` mode + distinct exit codes; CI gate step; CONTRIBUTING rule. Single-source package is the eventual destination, not this week's step.

### 8. The phase-transition skeleton merge gap — every learner, every boundary [SERIOUS]
*A1.* Round 2 fixed overwrite; the other direction is unbridged: later phases ship new stubs *inside files the learner already owns* (phase_01 parser.py: 6→10 symbols), skip-existing never delivers them, the "Preserved 3 files… ls the skeleton" message points at filenames when the delta is symbols, and the facilitator failure-table maps the resulting ImportError to the wrong cause. The WHAT/WHY/HOW docstrings — the product's differentiator — reach continuing learners exactly once.
**Fix:** AST-aware `skeleton_merge` (append missing top-level stubs to preserved files, reusing skeleton_check's parsing); or minimally a per-file symbol-diff report + the ImportError row in the facilitator table.

### 9. Learner state is untracked: the 3-week return fails on every axis [SERIOUS]
*A1.* No resume signal; `make status` is titled for learners but shows the authoring matrix (actively wrong answer); 35–55h of work deliberately outside version control (`git clean -fdx` erases it) while Phase 7 *teaches* "git is the backup"; no accumulating progress feedback across a 9-phase journey with a 12–20h cliff.
**Fix:** `.akanga-progress` appended on green + `make resume`; learner-side nested git (`make checkpoint`); rename authoring matrix to `repo-status`, make `status` learner-facing.

### 10. Day-1 funnel: predictable variance, unbudgeted failures [MODERATE]
*A1.* `requires-python>=3.13` buys nothing and fails behind corporate proxies (uv fetches interpreters from GitHub releases) — facilitator failure-table has no row for it; `make setup --all-extras` pulls the graph stack no workshop uses; `.envrc`'s **relative** `AKANGA_SRC` makes subdir pytest emit *actively wrong* advice ("Create your src/ directory"); bare `pytest` collects all 9 phases; editing `skeletons/` instead of `src/` (fuzzy-finder order!) is undetectable; set-but-stale AKANGA_SRC in a second terminal warns nothing.
**Fix:** drop pin to >=3.12 (or document the real 3.13 need); `make setup-workshop` lean path + offline UV_CACHE_DIR contingency; absolute `.envrc` export; src-file==skeleton-file detector appended to NotImplementedError failures.

### 11. Green ≠ understood: the suite's three blind spots, and no can't-fake-it checkpoints [MODERATE]
*A5.* Plain `write_text()` **passes the atomicity test** (it only checks for leftover tmp files); deleting `threading.Lock` fails **zero** tests in the concurrency phase (and the WAL/Lock distinction is only a *Group* reflect — solo learners are never asked); phase-5 fallbacks let structure substitute for behavior. Phase-8 direction-rule hole is confirmed **closed**.
**Fix:** "predict the failure" mutation blocks per phase (zero test code — *"Delete the Lock. Predict which test fails. None do. Explain why, then write that limit into your Thread Safety vault node"* — copied solutions can't fake the prediction); one 20-line fault-injection test makes Phase 0's atomic write falsifiable; body-floor warning in vault-check.

### 12. Time rot: CI is frozen by uv.lock; drift lands as cliff events [MODERATE]
*A4 + A5.* No dependabot/renovate (`.github/` = ci.yml only); pillow in the always-installed extras with no CVE channel; `[graph]` extras still unpinned (acknowledged open item); textual 8.x already needed in-version workarounds and 8.x EOL lands inside 12 months — multiplied by N diverged TUI trees (#7); fastmcp's *protocol* path never executes anywhere (tests call tool functions directly); **the Claude Desktop config path in phase-08 is wrong today on macOS** (`~/.config/claude/` vs `~/Library/Application Support/Claude/`); CI's real integrity property (cumulative verify, O(N²) ≈ 46 sessions) isn't in CI; setup-uv has no cache and floats `latest`.
**Fix:** weekly canary job (`uv lock --upgrade` + `make test-all`, continue-on-error, auto-issue); dependabot.yml; pin extras; one stdio MCP round-trip smoke test (initialize + tools/list — the only thing that catches an MCP/fastmcp break); fix the config path now + version-stamp volatile claims; CI matrix over phases with cache → makes the cumulative gate affordable.

### 13. Exemplar-honesty defects in the persistence/API layer [MODERATE]
*A3.* FTS external-content dance misses the `UNIQUE(path)` displacement case (orphaned FTS rows → ghost matches); path convention forks inside phase_08 (relative taught; MCP stores absolute; `get_node` reads without vault join — empty bodies depending on cwd); route handlers reach into `db._lock`/`db.conn` with hand-written SQL (missing `delete_edge`/`get_edges_touching` methods); `close()` takes no lock; module-global `_app_state` contradicts its own factory docstring; phase_08 `search()` unbounded; deletions never git-committed.
**Fix:** displaced-row handling in the dance (both variants); one path convention asserted at the DB boundary; add the two missing DB methods; lock in `close()`; per-app state.

---

## What This Round Does NOT Challenge
The Round-2 settlements (D1–D11) and the resolved findings — this round attacked *new* surface (the solution trees), *emergent* behavior (density, duplication, drift), and *time* (rot, return, growth). The teaching architecture itself again survived: agents independently praised phase_07's parser as a model file, the single-worker debounce design, the SEC-02/SEC-06 doc↔code reinforcement, the remediation-ladder-as-anti-cheat, and the evidence-before-enforcement CI culture.

## Risk Matrix

| # | Risk | Severity | Requires |
|---|---|---|---|
| 1 | Edge duplication on every re-scan (reproduced) | CRITICAL | Schema fix skeleton+solutions + idempotency test |
| 2 | phase_08 tree reverts taught lessons (BUG-04 back) | CRITICAL | Promote phase_07 modules + TUI wiring |
| 3 | EventBus TOCTOU strands events; `_fire` race grades | SERIOUS | Lock-scope fix + canonical `_fire` + stress tests |
| 4 | Graph RAG emits no graph at real density | SERIOUS | Budget strategy + ranking |
| 5 | Editor/sync signatures: git bloat, id-flap, vim deletes | SERIOUS | Batcher+gc, delete grace window, dup-id guard |
| 6 | Answer key shipped; 6 stale docs; no honor-system norms | SERIOUS | Doc sweep + norms + peek ritual + message inversion |
| 7 | Solution-tree drift with divergent half-fixes | SERIOUS/STRUCTURAL | Canonical manifest + sync_forward rework + CI gate |
| 8 | Phase-transition stub delivery gap | SERIOUS | AST skeleton-merge |
| 9 | No learner state/resume/backup | SERIOUS | Progress file + resume + nested git |
| 10 | Day-1 funnel (3.13 pin, relative AKANGA_SRC, …) | MODERATE | Pin drop + path/message hardening |
| 11 | Green≠understood blind spots | MODERATE | Mutation blocks + atomic fault-injection test |
| 12 | Dependency/time rot; CI frozen; wrong Desktop path | MODERATE | Canary + dependabot + MCP smoke + path fix |
| 13 | Exemplar-honesty defects in persistence/API | MODERATE | Targeted code fixes |

## Suggested Priority

**Tier 0 — correctness of shipped artifacts (this week):** #1 (backport UNIQUE + idempotency test), #2 (phase_08 module promotion), #6's doc sweep (6 stale spots + CONTRIBUTING + Makefile message), #12's Desktop-path fix.
**Tier 1 — convergence before contributors arrive:** #7 (manifest + one-time merge + CI gate), #3 (lock fix rides the convergence commit).
**Tier 2 — scale calibration:** #4 (RAG budget), #5 (write-path), #13.
**Tier 3 — learner experience:** #8, #9, #10, #11, #12 remainder.

## Appendix — Agent Coverage
A1 cohort → #8 #9 #10 · A2 scale → #1 #4 #5 · A3 code → #1 #2 #3 #13 · A4 maintenance → #6 #7 #12 · A5 outcomes → #6 #11 #12. Cross-validation: #1 found independently by A2 (behavioral) and A3 (code-reading), reproduced by orchestrator; A4's CLAUDE.md sub-claim disproved and withdrawn.

---

## Resolution Log

*Status as of 2026-06-11 (W1–W6 batch + orchestrator integration complete). Verification: all 9 cumulative
legs green (leg 08: 176 passed — the capstone tree is fully cumulative for the first time), stdio MCP smoke
passes, duplication reproduced-then-fixed (2→4→6 became 2→2→2), drift gate 55 pairs / 0 drifting, ruff clean.*

| # | Finding | Status | Resolution |
|---|---|---|---|
| 1 | Edge duplication (reproduced) | **Resolved** | UNIQUE(source,target,relation)+INSERT OR IGNORE in skeleton+all trees; hash-first skip; per-node delete-rederive; tombstone pass; UUID write-back at index (W2); 4 idempotency tests (W3) |
| 2 | phase_08 reverts taught lessons | **Resolved** | Canonical eventbus/watcher promoted; then FULL lineage convergence — phase_08 now carries the 02–07 base byte-identical + adapted MCP/TUI layers (W1 + orchestrator) |
| 3 | EventBus TOCTOU; _fire variance | **Resolved** | Lock-scoped set_loop/buffer; canonical _fire; observer-first stop; stress tests (W1/W3). Bonus: W3's re-touch test exposed a REAL macOS phantom-delete (FSEvents coalesces atomic replace into a delete for the living target) — fixed with an exists-check on debounced deletes |
| 4 | Graph RAG emits no graph at density | **Resolved** | Relations-first, depth-then-typedness ranking, root 500/neighbor 120 snippets, depth param; verified: 80 triples + 65 snippets at 11,863/12,000 chars (W5) |
| 5 | Editor/sync write signatures | **Resolved** | 5s idle commit batcher + gc every 50 commits; delete grace window (create-cancels-delete); dup-id warning + displaced-row FTS handling (W1/W2); doc callouts (W4) |
| 6 | Answer key shipped; stale docs; no norms | **Resolved** | 6-spot sweep; CONTRIBUTING + solutions/README rewritten with CS50-style norms; make peek + PEEKS.md; failure message inverted to the remediation ladder (W4/W6) |
| 7 | Solution-tree drift | **Resolved** | sync_manifest.toml + sync_forward --base/--check-all + CI drift-gate; one-time convergence merged the half-fixes; 55 pairs byte-identical incl. phase_08 (W6 + orchestrator) |
| 8 | Phase-transition stub gap | **Resolved** | AST skeleton_merge.py wired into make skeleton; facilitator ImportError row (W6/W4) |
| 9 | No learner state | **Resolved** | .akanga-progress on green/red, make resume/checkpoint, learner-facing status hint (W6) |
| 10 | Day-1 funnel | **Resolved** (3.12 verification pending canary) | requires-python>=3.12; absolute .envrc; setup-workshop; remediation-ladder failure message (W6) |
| 11 | Green ≠ understood | **Resolved** | Mutation blocks phases 00/02/04; atomic fault-injection test (write_text now fails it) (W4/W3) |
| 12 | Time rot; frozen CI; wrong Desktop path | **Resolved** | dependabot + weekly canary; CI matrix with cumulative legs + cache; stdio MCP smoke (passes); Desktop path fixed + stamped; extras pinned (W6/W3/W4) |
| 13 | Exemplar-honesty defects | **Resolved** | close() under lock; get_edges_touching/delete_edge methods; displaced-row FTS dance; one path convention (vault-relative) asserted at the boundary; search limits (W2 + convergence) |

**Corrections owned this round:** A4's CLAUDE.md-stale claim disproved pre-synthesis; the venv pytest binary went
missing mid-batch (uv lock without sync), silently falling back to the asdf global stack — caught because the
stdio smoke skipped on missing fastmcp; venv restored, full gate re-run green.
