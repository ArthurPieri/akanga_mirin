# STATUS — Adversarial-Analysis Remediation (V2 + V3 + V4 + V5)

> **Audience:** contributors / future Claude Code sessions. Updated 2026-06-12 (ALL rounds complete — Rounds 2+3: 27/27, Round 4: 14/14, Round 5: 9/9 findings resolved).
> Handoff doc for the remediation of `docs/adversarial-analysis-v2.md`, `-v3.md`, `-v4.md`, and `-v5.md` findings (all complete).
> Authoritative finding-by-finding status: the Resolution Log at the end of each doc.

## Commits

- `afcaa4b` — Tier 0: skeleton overwrite guard, status sweep, 1A/1B routing,
  run/serve/mcp targets, CI teeth, personal work → `arthur/phase-work` branch.
- `b9db63b` — Remediation batch 1 (R1–R8; R3/R4/R5/R8 complete, others partial).
- *(this commit)* — Remediation batch 2 (R6b/R7c/R12/R13/R14/R15/R16): **all 14 findings resolved**
  (one sub-item deferred: `akanga sync --full` anti-entropy → V1).

## Adopted decisions (D1–D11) — recorded, do not re-litigate

D1 solutions = `solutions/` dir on main (branch decision REVERSED 2026-06-10).
D2 skeletons+tests normative; docs match; EXCEPTION phase-5 doc keymap wins.
D3 one monotonic Node from phase 0 (`id:str, title, type:str "note"|"reference",
   tags, content_hash="", content="", path="", frontmatter:dict`) — no NodeType enum.
D4 EgoEdge natural direction; render `src --[rel]--> tgt` both directions (BUG-03 closed).
D5 `relation-vocabulary.md` = single registry; `instance_of` added; core-15 tier.
D6 EventBus: `run_coroutine_threadsafe`; pre-`set_loop` publish buffers to deque;
   done-callback logging; single-worker debounce (BUG-04 closed at spec level).
D7 `upsert_edge(source_id, target_id, relation, relation_id)` positional;
   `get_edges_from/get_edges_to` → (Node, relation, relation_id).
D8 `MAX_CONTEXT_CHARS = 12_000`, `max_triples = 80` spec constants (BUG-02 closed).
D9 security callouts S1–S4 inserted (phases 02/06/00/07).
D10 phase-0 vault table = untyped wikilinks.
D11 phase-5: doc keymap canonical; Kitty renderer = stretch goal (`uv sync --extra graph`).

## Final verification gate (all green 2026-06-10)

- `AKANGA_SRC=solutions/phase_08/src pytest tests/phase_08` → **23/23 passed**
- `skeleton_check` → 9/9 phases OK
- `ruff check tests/ skeletons/ scripts/ solutions/ examples/` → clean
- `pytest tests/ --collect-only` → 110 tests (5 known cross-phase import errors when
  src/ lacks later-phase modules — by design; per-phase runs are the workflow)
- `mkdocs build` → clean; planning docs quarantined via `exclude_docs`
- `scripts/check_doc_contracts.py` → no drift (caught + fixed 2 on first run)
- `AKANGA_SRC=./src pytest tests/phase_00` → 14 pass + **3 create() tests fail with
  NotImplementedError — expected**: create() is now a real deliverable the author-learner
  hasn't implemented yet (their work lives on `arthur/phase-work`)

## Remaining open items (small, tracked)

1. ~~CI doc-contract lint `--warn-only`~~ — **flipped to enforcing 2026-06-10** after
   first clean run (27286025295).
2. **Anti-entropy `akanga sync --full`** — specced as deferred V1 work in phase-01b.
3. ~~Solutions~~ — **ALL 9 phases complete and green** (2026-06-11): cumulative gates
   0:17 · 1:37 · 2:71 · 3:83 · 4:107 · 5:115 · 6:132 · 7:145 · 8:23/23 standalone.
   `make status` shows a full ✓ matrix.
4. **Phase-5 stretch renderer** — `[graph]` extra deps are unpinned; pin after first use.
5. ~~Push to origin~~ — **pushed 2026-06-10** (main `e9209ff..96a003c` + `arthur/phase-work`); CI green.
6. The author's own learning path continues from Phase 0 `create()` on `arthur/phase-work`.

---

# ROUND 3 — Adversarial-Analysis-V3 Remediation (2026-06-11, COMPLETE)

> Findings: `docs/adversarial-analysis-v3.md` — 13 findings from 5 analysis agents
> armed with measured data (1,000-node benchmark vault, md5 drift across solution
> trees). Finding **#1 was reproduced by the orchestrator** before acceptance:
> 3 identical scans → 2 → 4 → 6 edge rows (the index is append-only; linear
> corruption on every re-scan).
>
> Remediation runs as six parallel work batches **W1–W6**. W4 = docs (README,
> CONTRIBUTING, solutions/README, facilitator-guide, `docs/learning/**`, this file).
> Siblings own the Makefile (`peek`/`resume`/`progress` targets), scripts
> (sync manifest, skeleton merge), tests (idempotency, fault-injection, stress),
> and solutions code (schema, module promotion, RAG budget).

## Adopted decisions (E1–E10) — recorded, do not re-litigate

- **E1** Edge schema gains `UNIQUE(source_id, target_id, relation)` +
  `INSERT OR IGNORE`, in the skeleton AND all solution trees; a re-index
  idempotency test (`scan; scan; assert count unchanged`) becomes mandatory (#1).
- **E2** Minted UUIDs are **written back to frontmatter at index time** — no
  re-minting on re-scan, no orphaned edges for no-id vaults (#1).
- **E3** Canonical concurrency = the **phase_04 lineage** (eventbus + watcher):
  lock-scoped `set_loop`/buffer-append, phase_04's `_fire` (re-checks deadline),
  observer-first stop ordering; promoted into phases 05–08 including the
  capstone (#2, #3).
- **E4** Graph RAG is **relations-first**: relations before entity snippets,
  root snippet 500 chars, neighbor snippets 120 chars, depth parameterized (#4).
- **E5** Write-path hardening: idle-interval commit batcher + periodic `gc`;
  delete grace window (create-cancels-delete); duplicate-id guard — warn loud,
  keep the oldest path (#5).
- **E6** Honor-system norms instead of hiding solutions: CS50-style
  reasonable/not-reasonable list in `solutions/README.md`, `make peek` with
  learner-local `PEEKS.md`, post-green diff-the-reference ritual (#6).
- **E7** **Introduction-phase-canonical** modules: each module is fixed in the
  phase that introduces it and propagated byte-identical via `sync-forward`;
  manifest + `--check-all` drift gate in CI; one-time convergence commit merges
  the existing half-fixes (#7).
- **E8** `make skeleton` reports and merges **new stubs inside preserved files**
  at phase transitions (AST-aware symbol diff) (#8).
- **E9** Learner-state targets: `.akanga-progress` appended on green,
  `make resume`, `make peek`; learner-facing `status` (#9).
- **E10** `requires-python` pin drop to **>=3.12 — CLOSED 2026-06-12**: verified
  live in Round 4 on a cold 3.12.8 environment — all 9 phases green, 177 tests
  including the stdio smoke test (v4 claims ledger) (#10).

## Finding status (Round 3)

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Edge duplication on every re-scan (**reproduced**: 2→4→6) | CRITICAL | **Resolved** — see v3 Resolution Log |
| 2 | phase_08 tree reverts taught lessons (BUG-04 back) | CRITICAL | **Resolved** — see v3 Resolution Log |
| 3 | EventBus TOCTOU / `_fire` variance by copy | SERIOUS | **Resolved** — see v3 Resolution Log |
| 4 | Graph RAG emits no graph at real density | SERIOUS | **Resolved** — see v3 Resolution Log |
| 5 | Editor/sync write signatures break write path | SERIOUS | **Resolved** — see v3 Resolution Log |
| 6 | Stale status claims; no honor-system norms | SERIOUS | **Resolved** — see v3 Resolution Log |
| 7 | Solution-tree drift, divergent half-fixes | SERIOUS | **Resolved** — see v3 Resolution Log |
| 8 | Phase-transition stub delivery gap | SERIOUS | **Resolved** — see v3 Resolution Log |
| 9 | No learner state / resume / backup | SERIOUS | **Resolved** — see v3 Resolution Log |
| 10 | Day-1 funnel (3.13 pin, relative AKANGA_SRC, …) | MODERATE | **Resolved** — see v3 Resolution Log |
| 11 | Green ≠ understood (suite blind spots) | MODERATE | **Resolved** — see v3 Resolution Log |
| 12 | Time rot; wrong Claude Desktop path; frozen CI | MODERATE | **Resolved** — see v3 Resolution Log |
| 13 | Exemplar-honesty defects in persistence/API | MODERATE | **Resolved** — see v3 Resolution Log |

---

# ROUND 4 — Adversarial-Analysis-V4 Remediation (2026-06-12, COMPLETE — 14/14 findings resolved)

> Findings: `docs/adversarial-analysis-v4.md` — "verify the verifiers": 5 parallel
> agents attacked the remediation layer itself (tests, tooling, CI, doc patches)
> plus the live runtime (REST/MCP/3.12). Four findings were reproduced by the
> orchestrator before acceptance (setup false-green, dead AKANGA_SRC warning,
> phantom test name, manifest self-contradiction). The claims ledger **closed E10**
> (3.12 confirmed: cold 3.12.8 env, all 9 phases green, 177 tests) and confirmed
> every SEC property under live fire.
>
> Remediation runs as a parallel work batch **F1–F5**. F5 = docs (CLAUDE.md,
> README, `docs/**`, mkdocs.yml, solutions/README, this file). Siblings own the
> Makefile/shell flags, scripts (sync_forward manifest awareness, skeleton_merge
> imports, doc-contract test-name check), tests (timing margins, monotonic), and
> solutions code (MCP argv, lifespan indexing, write_back wiring).

## Adopted decisions (V1–V8) — recorded, do not re-litigate

- **V1** Makefile recipes use `.SHELLFLAGS := -ec` (fail on first error) plus a
  `need-uv` preflight — no more false-green `make setup`/`vault-init` (#1).
- **V2** `akanga_mcp/server.py.__main__` parses `--vault`/`--db` argv with
  argparse and **fails loudly** if the DB is unset/unopenable — never a
  healthy-looking server over `db=None` (#2).
- **V3** Both runtime lifespans (FastAPI `create_app` lifespan and MCP startup)
  call the hash-first idempotent `full_scan_and_index` and log
  "serving N indexed nodes" — `make serve`/`make mcp` work cold (#2).
- **V4** `write_back` is wired into the runtime: the indexer folds typed inline
  edges into frontmatter on changed-file index, covered by a new
  `test_inline_typed_edge_folds_on_index` (#7a).
- **V5** Watcher deadlines use `time.monotonic()` in the reference solution;
  timing-test margins widened and flake messages split so a flake cannot
  impersonate the early-fire bug (#10).
- **V6** Phase-5 stretch renderer dependency is **textual-image** (textual-kitty
  0.4.0 ships no working widget); canary imports the widget entry point (#12).
- **V7** Vault-check manifests are parsed from the phase-doc tables at runtime —
  single source of truth, no embedded copies to go stale (#11).
- **V8** CLAUDE.md carries **zero completion claims** — state lives in
  `make status` and this file; docs/README lists all four analyses with v4
  authoritative (#9).

## Finding status (Round 4)

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | `make setup`/`vault-init` false-green on total failure | CRITICAL | **Resolved** — see v4 Resolution Log |
| 2 | `make mcp` lobotomized; `serve` serves empty graph | HIGH | **Resolved** — see v4 Resolution Log |
| 3 | sync_forward ignores manifest; excluded dead; TUI ×4 unguarded | HIGH | **Resolved** — see v4 Resolution Log |
| 4 | Merged-skeleton state broken & never CI-verified | HIGH | **Resolved** — see v4 Resolution Log |
| 5 | Test-name enumerations drifted (phantom test) | HIGH | **Resolved** — see v4 Resolution Log |
| 6 | Dead AKANGA_SRC warning; peek unlocked by infra failures | SERIOUS | **Resolved** — see v4 Resolution Log |
| 7 | write_back dead at runtime; phase-0 validator nagging | SERIOUS | **Resolved** — see v4 Resolution Log |
| 8 | Time estimate expired; "optional" vault contradiction | SERIOUS | **Resolved** — see v4 Resolution Log |
| 9 | CLAUDE.md two rounds stale | SERIOUS | **Resolved** — see v4 Resolution Log |
| 10 | Lying flake message; time.time in solution; macOS fix unvalidated on CI | SERIOUS | **Resolved** — see v4 Resolution Log |
| 11 | Vault manifests stale at ship | SERIOUS | **Resolved** — see v4 Resolution Log |
| 12 | textual-kitty cannot deliver the promised renderer | MODERATE | **Resolved** — see v4 Resolution Log |
| 13 | Editorial repetition/voice debt (+13%, rules ×3–5) | MODERATE | **Resolved** — see v4 Resolution Log |
| 14 | No tag, identical commit messages, no inbound license, Mirin untranslated | MODERATE | **Resolved** — see v4 Resolution Log |

E10 (3.12 floor) is **CLOSED** — verified, not remediated: 177 tests green on 3.12.

---

# ROUND 5 — Adversarial-Analysis-V5 Remediation (2026-06-12, COMPLETE — 9/9 findings resolved)

> Source: `docs/adversarial-analysis-v5.md` (readability + DRY lens — first
> round on the cleanliness dimension). 9 findings: 1 STRUCTURAL, 5 SERIOUS,
> 3 MODERATE. Owner accepted the suggested tiers (fast path): Tier 1 fixed
> first, Tiers 2–3 accepted as Changed and scheduled.

## Adopted decisions (W1–W3 so far) — recorded, do not re-litigate

- **W1 (#8)** `extract_wikilinks` strips ``` fences before matching — same
  invariant as `parser.extract_inline_edges`. Canonical links.py (phase_02)
  fixed and propagated 3–8 via sync-forward; pinning test
  `test_extract_wikilinks_ignores_fenced_code` added; skeleton HOW updated
  (fence strip is now step 1).
- **W2 (#2)** Loader calls must never run at module top level in tests —
  sys.path setup happens in `pytest_configure` (collection time), diagnostics
  in the session guard (fixture time). The 9 per-phase `_setup_akanga_src`
  fixtures (false docstrings) are replaced by ONE root-conftest
  `_akanga_src_guard` autouse session fixture with a truthful docstring;
  phase number in the error message is derived from collected items. The 5
  files with module-level loads (phase_02 test_db/test_indexer/test_links,
  phase_03 test_graph, phase_04 test_watcher) now bind learner modules in an
  autouse module-scoped `_bind_learner_modules` fixture. Verified: missing
  AKANGA_SRC now yields the curated message + exit 1 in every phase.
- **W3 (#5)** Phase roster single-sourced: Makefile `MAX_PHASE := 8` +
  `PHASES := $(shell seq 0 $(MAX_PHASE))` feed all four all-phases loops,
  `TO`, and resume's bound. `verify-all`/`examples-all`/`test-phase-range`
  gained the `TESTED=0`-style floor-guards test-all already had (v4 #1
  pattern finished). `sync_forward.py --to` defaults to the manifest's
  `[manifest].phases` max. CI `checks` job cross-checks the verify matrix
  against `make -s print-max-phase`.

- **W4 (#7)** Edge SQL lives in db.py, behind the lock — the Phase 6 server's
  `/nodes/{id}/edges` and `DELETE /edges/{id}` routes now call
  `db.get_edges_touching` / `db.delete_edge` (whose docstrings are therefore
  true again); propagated 7–8. Skeleton phase_06 teaches the same two
  CANONICAL names (no more invented `*_for_node` variants, no inline-SQL
  option) and drops the redundant edge-cleanup step in delete_node
  (`db.delete_node` already removes all touching edges).
- **W5 (#4)** Marker convention single-sourced in `scripts/_common.py`
  (`MARKER_SNIPPETS` + `is_marker_file`, match anchored to the first 3 lines
  to kill the whole-file substring exemption); sync_forward + skeleton_merge
  import it; check_doc_contracts' AST-empty heuristic documented as
  deliberately different. `tests/test_scripts_markers.py` (3 tests, no
  AKANGA_SRC needed — the root guard now skips sessions with no phase tests)
  welds prose markers ⇔ snippets ⇔ AST-empty; runs in CI's checks job.
- **W6 (#1)** Dual-layout import policy single-sourced in
  `tests/_helpers.py::load_attr`; all 23 loaders are now one-line wrappers
  (names and call sites unchanged). Unified policy: catch ImportError
  (superset), report every candidate's REAL error (broken-but-present files
  no longer masquerade as missing), explicit guards with descriptions
  (phase_01's unguarded parser load now guards on Edge), deliberate
  divergences kept and documented in place (phase_05 returns the function;
  phase_08 MCP loader is package-first with the why). test_rag's gratuitous
  _load_db copy deleted (imports the conftest's).

- **W7 (#3)** Fixtures renamed by contract, kept phase-local: phase_02
  `tmp_db`→`db_path` + `tmp_vault`→`vault_dir` (docstring states akanga.yaml
  lives in the returned dir's PARENT), phase_05 `tmp_db`→`indexed_db` +
  `tmp_vault`→`vault_with_nodes`, phase_01 `tmp_db`→`sync_queue_conn`. Both
  false "upsert_edge is positional" comments replaced with the real
  keyword-friendly signature; `populated_db`'s docstring now states the
  Node-OR-dict upsert contract that phase 3 exercises. `_write_node`
  deduplicated into tests/_helpers.py (phase_06 conftest re-exports it).
- **W8 (#6)** scripts/_common.py capped at four conventions: marker files,
  `REPO_ROOT` (replaced 4 computations), `normalize_phase` with
  strip_split/expand_split covering the 1A/1B convention (replaced 2 Python
  parsers; shell sites carry keep-in-step pointer comments), and
  `iter_md_section` (replaced 4 walkers; parity-verified line-for-line on
  all 10 phase docs). check_doc_contracts gained a file-local
  `strip_self_cls` (3 inline copies → 1). `make help` is self-registering:
  `## @group description` tags + one HELP_GREP macro replace the 12
  hand-maintained name alternations — output byte-identical, new targets
  appear in help with no second list to edit. run_checks restructuring
  explicitly DEFERRED (risk > reward); AST harvesters left distinct by
  design.
- **W9 (#9)** `NodeRecord` (frozen, slots — grep-verified nothing mutates DB
  returns; parse-model Node mutations are a different type) is the DB's
  six-field read model in canonical db.py; all ten `Any` annotations
  replaced (`upsert_node(node: Node | NodeRecord | dict[str, Any])` typed
  honestly); graph.py `EgoGraph.root: NodeRecord` via TYPE_CHECKING (the
  misleading "avoid import cycle" comment deleted); sync_worker.drain
  annotated `GraphDatabase | sqlite3.Connection`. Skeleton phase_02 db.py
  now teaches NodeRecord (stubs still raise NotImplementedError); phase_06
  server skeleton's nine SimpleNamespace footnotes collapsed to one
  canonical record-object note (+ one-line pointers), `vars(n)` suggestions
  removed (slots-incompatible); phase_08 note fixed likewise; canonical
  server `_node_dict` typed `NodeRecord`. Propagated: db.py 2→8, graph.py
  3→8, sync_worker.py 4→8, server.py 6→8.

## Finding status (Round 5)

| # | Finding | Severity | Status |
|---|---|---|---|
| 1 | Dual-try loader family: 23 forked copies, 4 live divergences | STRUCTURAL | **Resolved (W6)** |
| 2 | False fixture docstring; phases 02–04 bypass AKANGA_SRC diagnostics | SERIOUS | **Resolved (W2)** |
| 3 | Fixture name collisions; contradictory upsert contracts; false "positional" comment | MODERATE | **Resolved (W7)** |
| 4 | Marker convention defined 4 ways; zero script tests | SERIOUS | **Resolved (W5)** |
| 5 | Phase roster hand-enumerated ×9; silent-green loop guards | SERIOUS | **Resolved (W3)** |
| 6 | No scripts/ shared core; 1A/1B convention in 5 parsers; help double-registration | MODERATE | **Resolved (W8)** |
| 7 | Dead delete_edge/get_edges_touching with false docstrings; server hand-writes their SQL | SERIOUS | **Resolved (W4)** |
| 8 | links.py missing parser.py's fence strip → phantom edges from fenced examples | SERIOUS | **Resolved (W1)** |
| 9 | Ten Any-typed DB APIs; phantom second Node type | MODERATE | **Resolved (W9)** |

## Verification gate for Tier 3 (all green 2026-06-12)

- `make lint` clean across the repo; `make test-all` → 9/9 phases;
  `make verify PHASE=8` → cumulative green; collect-only 185 tests, 0 errors
- `sync_forward.py --check-all` → converged after 6 propagations
  (db/graph/sync_worker/server × solutions, db/server × skeletons)
- `make help` output byte-identical pre/post refactor; doc-contract lint
  exit 0; skeleton_check 9/9 OK; marker pinning tests 3/3; mkdocs clean
- `make vault-init && make vault-check PHASE=0` smoke: refactored manifest
  parser extracts the phase-0 node table and reports the empty vault's
  missing titles correctly
- One deferred item logged: check_doc_contracts.run_checks extraction
  (check_signatures/check_deliverables) — revisit only if that file grows

## Verification gate for Tier 2 (all green 2026-06-12)

- `make test-all` → all 9 phases passed; `make verify PHASE=8` → cumulative green
- `sync_forward.py --check-all` → converged (post server.py propagation)
- `pytest tests/test_scripts_markers.py` → 3/3 (no AKANGA_SRC)
- `ruff check tests/ scripts/` → clean; doc-contract lint exit 0;
  `skeleton_check` phase_06 OK
- Smoke: broken db.py under AKANGA_SRC → failure message includes the real
  ImportError from inside the file, identically in every phase

## Verification gate for Tier 1 (all green 2026-06-12)

- `make test-solution PHASE=2` → 40/40 (incl. new fence test)
- `make test-all` → all 9 phases passed
- `make verify PHASE=8` → cumulative 00..08 green
- `sync_forward.py --check-all` → 56 pairs, 0 drifting
- `ruff check tests/ scripts/` → clean
- `check_doc_contracts.py` → warnings only (pre-existing), exit 0
- `skeleton_check.py skeletons/phase_02/src` → OK
- Smoke: `env -u AKANGA_SRC pytest tests/phase_02/` → curated message, exit 1

## Round 5 verification audit (2026-06-12, post-close)

Five parallel audit dimensions re-verified the round (V1 test-lane, V2
scripts/CI, V3 solutions/skeletons, V4 docs truthfulness, V5 fresh gate
battery + new-defect hunt). All W1–W9 mechanical claims verified TRUE; all
12 gates green. 11 residual findings surfaced and ALL FIXED same day:

- 3 surviving hand-rolled dual-try loaders (phase_07 conftest fixture,
  phase_08 conftest rag_context, test_mcp _bootstrap_db) → load_attr/conftest
- 2 surviving false "positional" comments (test_mcp, test_rag) → corrected
- 2 hand-enumerated rosters inside ci.yml (status table, transition job) →
  derived from `make -s print-max-phase`
- phase-06 doc taught SimpleNamespace + `vars(node)` (crashes on slots
  NodeRecord) → rewritten to NodeRecord/asdict
- phase-01b doc referenced renamed `tmp_db` fixture → `sync_queue_conn`
- this file's own header claimed Round 4 in progress → all rounds complete
- CLAUDE.md + tutor.md said "71 relation types" vs registry's 72 → 72
- load_attr silently discarded a broken-but-present earlier candidate when a
  later candidate succeeded → now emits a stderr warning naming the broken
  file (probe-verified)

Known-latent (logged, not fixed): NodeRecord(frozen) generates __hash__ but
`tags: list[str]` makes hashing raise at call time — no current call site
hashes records; if a `set[NodeRecord]` is ever needed, change tags to
`tuple[str, ...]` first.
