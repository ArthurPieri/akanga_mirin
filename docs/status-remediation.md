# STATUS — Adversarial-Analysis Remediation (V2 + V3)

> **Audience:** contributors / future Claude Code sessions. Updated 2026-06-11 (Rounds 2 AND 3 complete — 27/27 findings resolved across both).
> Handoff doc for the remediation of `docs/adversarial-analysis-v2.md` (complete) and `docs/adversarial-analysis-v3.md` (in progress) findings.
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
- **E10** `requires-python` pin drop to **>=3.12 — pending verification** that
  nothing in the path actually needs 3.13 (#10).

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
