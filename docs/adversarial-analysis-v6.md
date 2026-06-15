# Adversarial Analysis V6 — `docs/plan-noteapp-alignment.md`

> Date: 2026-06-12 · Purpose: stress-test the noteapp-alignment implementation plan before execution
> Lens: **Round 2 — are the mechanisms sound?** (specs vs real code, gates that gate, sequencing that holds)
> Method: 4 parallel verification agents (code specs / build & CI mechanics / docs specs / completeness & pedagogy), every claim re-verified against the repo, the noteapp mirror, and executed code (SQL CTE runs, regex sweeps, recounts, mkdocs builds).

## Scope and prior rounds

This analyzes the **plan**, not the curriculum (v1–v5 analyzed the curriculum). Settled decisions
D/E/V/W and the plan's N1–N9 register are challenged only where verification produced new evidence.
Headline: the plan's mechanical layer is genuinely strong — 30+ line refs, the 52-of-72 recount, the
B2 code block, the recursive CTE, every Makefile target and CLI invocation all verified correct.
The 12 critiques below are semantic and process-level: keys that don't match, gates that can't fail,
contracts changed without telling the learner.

---

## 1. The closing gates can't fail: `mkdocs build` is a no-op gate and the "link check" doesn't exist [CRITICAL]

### The problem
`uv run mkdocs build` is the gate for B4, B5+B6, B7, C10, and the final repo-wide gate; C10 adds
"+ link check". Verified empirically: `mkdocs.yml` has **no `strict: true` and no `validation:`
block**, so a missing nav file, a broken `[link](file.md)` cross-link, or a doc absent from nav all
build with **exit 0** (the build today already emits the not-in-nav INFO for `noteapp-alignment-audit.md`
and `deployment.md` and exits clean). And no link checker exists anywhere in the repo — no
`verify_links.py`, no mkdocs plugin, zero grep hits — nor does CI run mkdocs at all.

### Why this matters
Stage 14 (C10) is the wiring stage — nav, doc-map, six files of cross-links — and it is certified by
a gate that cannot detect any of its failure modes. A plan whose riskiest stage has a gate that
always passes is worse than no gate.

### What this means
Add to C10 (or Step 0): `strict: true` + a `validation:` block (`omitted_files: warn`,
`not_found: warn`, links `not_found/anchors: warn`) in `mkdocs.yml` — after first adding
`noteapp-alignment-audit.md` and `deployment.md` to nav or `exclude_docs` so the flip isn't
immediately red. Wire C1/C2's nav entries in their own commits (stage 10), not deferred to C10.
Delete the words "link check" or name a real tool.

## 2. A1's `(relation, target_id)` edge key misses every folded typed edge — DELETE silently resurrects [SERIOUS]

### The problem
Fold-pipeline frontmatter entries persist with `target_id: ""` forever: `write_back` writes inline
edges with empty `target_id` (`solutions/phase_02/src/akanga_core/parser.py:196-199,247-255`),
resolution happens only in the DB, and `tests/phase_02/test_indexer.py:596-600` pins the entry by
`relation` + `target` title. A1 keys `_remove_fm_edge`/the 409 guard on `(relation, target_id)`.
Scenario: learner writes `[[Beta | supports]]` → folds with `target_id: ""` → DB row has the UUID →
`DELETE /api/v1/edges/{id}` looks for the UUID in the file, finds nothing, no-ops on the file,
deletes the row, returns 204 → the edge **resurrects on the next index** — and A2's rederive-all
makes "next index" mean "any file added or removed anywhere in the vault." The plan's own test list
can't catch it (its DELETE test deletes an API-created edge, which does carry a UUID). The 409 guard
leaks the same way (folded duplicate → 201 + near-duplicate entry).

### Why this matters
N1's recorded contract — "DELETE removes the entry" — is false for the dominant edge species actual
learners create. Executor ships green tests and a zombie-edge behavior contradicting the very
doctrine (file-first, no resurrection) the workstream exists to establish.

### What this means
`_remove_fm_edge` and the dup guard must match by `target_id` **or** resolved title: the route
already has the target node — treat `target_id == "" and target.lower() == target_node.title.lower()`
(same case rule as `resolve_wikilink`) as the same edge. Add a test: fold a typed inline edge via
scan, DELETE it through the API, rescan, assert it stays dead.

## 3. The hyphen/underscore frontmatter-key contradiction is cited by the plan — then left standing and re-propagated [SERIOUS]

### The problem
`docs/learning/phase-01a-…md:120-139` presents the "canonical" edge block with **hyphenated**
`relation-id:`/`target-id:` keys. The canonical phase 2–8 code reads **only underscores**
(`indexer.py:193-199`, `parser.py:230-240`); only the pre-intro phase_01 parser tolerates both. A
learner hand-authoring the doc-canonical block gets their keys silently ignored AND destroyed on
first fold (`write_back` rewrites the list with empty ids). The plan demonstrably saw this — A1
says "underscore keys … NOT phase-01a's hyphenated YAML example" — yet no workstream edits
phase-01a:120-139, and C6's drafted pitfall text re-asserts the hyphen spelling ("frontmatter edges
with `target-id` are immune").

### Why this matters
After the round, three authorities contradict each other: the doc's canonical block (hyphens), the
API writing underscores into the same files, and a new pitfall box using a spelling the indexer
cannot read. The round amplifies a defect it explicitly noticed.

### What this means
Add to the A1 (or A4) commit: phase-01a:120-139 → underscore keys (matching the `Edge` dataclass
listing at :167-175, which already uses underscores); fix C6's drafted line to `target_id`.
Separately decide: restore phase_01's dual-spelling read tolerance in the phase_02+ readers (one
`.get(k) or .get(k.replace("_","-"))` fallback in two readers) — cheap, kills the destructive case.

## 4. Four phases' taught contracts change with zero learner-facing signal — and the phase docs go stale against their own new tests [STRUCTURAL]

### The problem
The round changes what learners are graded on in Phases 0, 1A, 3, 6 (new `test_textutil.py`,
collision-behavior reversal, ~7 alias tests requiring a new public `split_pipe_segment`, edge-endpoint
tests). Verified gaps: **A6 has no docs item at all** — phase-00's doc says the suite is
`test_parser.py` (singular; now false) and its What You Build table gains no slugify/unique_path
rows; **phase-01a:200 says "15 tests"** and its function table gains no `split_pipe_segment` row
(A4's doc edits don't cover either). `check_doc_contracts` checks 4/5 are one-directional (doc →
tests/skeleton), so the gates never catch a doc that under-specs the suite. No migration path
exists for mid-path learners: `textutil.py` lands only in `skeletons/phase_00`, so a learner past
Phase 0 (the author's own `arthur/phase-work` branch sits at exactly Phase 0 `create()`) never
receives the stub while phase_01's HOW now instructs "use textutil.slugify"; `make resume` reports
recorded-green phases that now fail. House precedent exists and is violated: the prior NOTEAPP-SYNC
batch added a test AND its phase-doc Deliverable line in the same change — only A1 follows it.

### Why this matters
The curriculum's governance story is "the doc is the spec; the tests are the contract." Under the
anti-spoiler tutor rules, the doc table + skeleton stub are the learner's ONLY spec — and after this
round they're incomplete for exactly the new material.

### What this means
(1) Add docs items to A6 (What You Build rows + Deliverable test names for phase-00) and A4
(function-table row + test count for phase-01a) — same commits as the code. (2) Add a short
"Changed 2026-06" admonition per affected phase doc (or one notice in docs/index.md): what changed,
what a previously-green learner does (`make skeleton PHASE=0` re-merge or `make peek` textutil —
verify the merge path is non-destructive and document it). (3) One sentence in phase-06 explaining
the deliberate 409-vs-suffix collision-policy split (N6).

## 5. The stage table contradicts the collision table, "stage 10 parallel-safe" is false, and line-pinned edits have no content-verification rule [STRUCTURAL]

### The problem
(a) Collision table: phase-01a "order **B1 → A4**"; execution sequence: A4 = stage 3, B1 = stage 5.
Harmless content-wise (disjoint regions) but the two "resolved" tables disagree. (b) **C3 (stage 10,
marked "parallel-safe with 5–9") inserts a header line at the top of all 17 foundations docs — three
of which B3/B4/B5 are rewriting by line range in stages 7–8.** Run in parallel: merge conflicts;
run before: every B3/B4/B5 line ref shifts by one. The collision table has no C3 row. (c) The
systemic version: every B/C line number was measured pre-round, yet stages 1–4 edit two of the cited
docs first; the plan flags drift ad hoc (C5b "post-A4 text") but states no general rule, and a
"replace lines N–M" instruction fails silently where an old-string mismatch fails loudly. (d) A-stage
gates omit `check_doc_contracts.py` even though A1/A4/A5 edit phase docs and CI runs the lint on
every push — a typo'd backticked test name lands red on main mid-round. (e) No commit-message spec;
house style is tiered conventional commits.

### Why this matters
The plan's core promise is literal executability by a fresh session. As written, that session either
hits a same-file conflict at stage 10 or applies a range-replace one line off and silently corrupts
a doc.

### What this means
Move C3 after stage 8 (or fold the sqlite/yaml/asyncio headers into B3/B4/B5's commits); add the C3
collision row; fix the B1→A4 cell to "disjoint — order immaterial". Add an execution-rules preamble:
"line numbers are pre-round anchors — locate every edit by quoted text, re-grep before each stage,
never range-replace without matching quoted context." Add `check_doc_contracts.py` to every A-gate
that touches a phase doc. Add one line: commit style `fix: noteapp-alignment N1 — file-first manual
edges (A-1)`.

## 6. B8's check-6 regex false-positives on a correct line the moment it lands [SERIOUS]

### The problem
Verified by running the spec'd regexes over the corpus: the registry derivation is sound (exactly 72
unique ID-first rows), but the second pattern `of the (\d{2,3})` hits
`phase-08:106` — "…of the 170 consume the whole 12,000-char budget…" — a **node count**, not a
relation count. 170 ≠ 72 → stage 9's own gate exits 1 on a correct sentence. C1 §6 is specced to
quote the same 170 figure into a file check 6 scans — a second potential hit. The escape hatch
(`ALLOW relcount:phase-08…:170`) would permanently mask a future genuine "170-type" typo.

### Why this matters
The executor meets a red lint with no instruction except an allowlist improvised under gate pressure
— the exact silent-decay channel the check exists to close.

### What this means
Require relation context in the second pattern (`of the (\d{2,3})(?=\s+(?:relation|typed|directed|have no))`)
or apply it only to lines containing "relation"/"inverse". Add phase-08:106 to B8's spec as the known
negative test case; phrase C1's 170 sentence without "of the".

## 7. The B1 and B6 sweeps have verified holes — and their own gates can't see them [SERIOUS]

### The problem
**B1**: `docs/plan-kg-theory-and-integration.md:157` (`# ... existing 71 entries unchanged ...`) is
missed **in a file B1 edits two lines up** (:22 is in the table) → half-fixed file; and
`docs/implementation-plan.md:115` ("71 built-in") is neither fixed nor on the deliberately-untouched
list. Neither path is in B1's gate grep or the final gate (both enumerate specific dirs). Adjacent:
`phase-01a:181` says the registry lives "in `akanga.yaml` or `vocabulary.yaml`" — B4's rewritten
yaml tail will assert verbatim "Relation types do NOT live here"; nobody edits :181, so the round
*creates* a cross-doc contradiction. **B6**: `phase-06:191` documents `GET /api/v1/nodes/{id}/results
— active check results`, an endpoint of the cut active manager that the solution does not serve —
one line under the line C4 edits, and invisible to B6's gate pattern (no token matches "active check
results"). Also missed: `json-rpc-basics.md:297` (`type="active"` — node types are `note|reference`).
And B6's stated expected output ("only the two explicitly-deferred mentions") is wrong twice: the
post-edit deferred phrasings match zero pattern tokens, while `phase-05:488` legitimately contains
`AkangaApp` (**test-pinned** alternate TUI class name — must NOT be edited) and will surface as an
unexplained hit.

### Why this matters
A ghost **API endpoint** is the highest-stakes residual (a contract claim, lint-invisible), and a
gate whose expected output doesn't match reality teaches the executor to wave findings through.

### What this means
Add to the tables: kg-theory:157 (fix), implementation-plan:115 (fix or freeze explicitly),
phase-01a:181 (registry location → relation-vocabulary.md), phase-06:191 (delete — cleanest inside
C4's endpoint edit), json-rpc:297 (reword to `type="reference"`/tag query). Widen B1's gate to
`docs/*.md` minus named frozen files. Rewrite B6's gate: extend the pattern
(`active check|active_result|type="active"|active node`) and state expected residuals explicitly,
including the phase-05:488 AkangaApp exemption with a "do not edit — test-pinned" note.

## 8. Repo-governance misses: un-ignored mirror, a decision-log section left contradicted, stale CLAUDE.md, audit published to the learner site [SERIOUS]

### The problem
(a) `.tmp-noteapp-mirror/` has **no `.gitignore` entry** — "never commit it" is enforced by nothing
across ~20 commits, and CI's tracked-files guards fire only post-push; the mirror is another
project's code. (b) `status-remediation.md:354`'s NOTEAPP SYNC section claims "most core-integrity
fix classes were already absorbed" — the audit proved F1 (a P0) invisible to that section's
classification, and the plan appends N-entries below without amending the now-false summary — the
exact contradiction-by-omission pattern the round criticizes. (c) CLAUDE.md "Current focus" says
"No round is currently in progress"; maintaining that field is established practice (commit
c4bb30a) and the plan never updates it at kickoff or close. (d) `docs/noteapp-alignment-audit.md`
matches no `exclude_docs` pattern (`plan-*.md` covers only the plan) → MkDocs builds and Material
indexes a contributor audit full of solution internals on the learner-facing site whose tutor rules
forbid opening `solutions/`; it's also absent from docs/README's map.

### Why this matters
Each is one line; together they're a self-contradicting decision log, a lying contributor guide, a
spoiler leak, and a provenance accident waiting on one `git add -A`.

### What this means
Step 0 first command: append `/.tmp-noteapp-mirror/` to `.gitignore` (commit with the first round
commit) — or place the mirror outside the worktree. B8: one superseding line atop NOTEAPP SYNC
("second pass found four core-integrity gaps this section missed — see N-series"). Stage 1 + Stage 14
edits to CLAUDE.md "Current focus" (round open/closed). C10: `noteapp-alignment-audit.md` →
`exclude_docs` + docs/README map entry.

## 9. N2's register text overstates the trigger's reach — the watcher path is untouched [MODERATE]

### The problem
The rederive-all trigger lives in `full_scan_and_index` only. The live runtime path is per-event
`index_file` (`solutions/phase_08/src/akanga_core/app.py:69,116-120`), which re-derives only the
changed node — so with the app running, "A links to B; B created later" still waits for the next
full scan. N2's text ("adding/removing files re-derives edges for all nodes") is true for scans,
false at runtime; A2's spec'd docstring rewrite would delete the only documentation of a limit that
still holds on the `index_file` path; C6's drafted "resolves automatically on the next scan (N2)"
inherits the overstatement. (The bigger attacks failed: `_reindex_edges` is DB-only — no write_back,
no file churn, no watcher storms.)

### What this means
Narrow, don't delete: scope the :32-34 rewrite to `full_scan_and_index`; keep `index_file`'s
:220-221 line essentially as-is; amend N2's register text ("full scans re-derive …; the per-file
watcher path still defers to the next full scan"); align C6's line.

## 10. Two executable spec bugs: `index_file`'s vault-path convention, and `unique_path` returns `str` where a `Path` is needed [MODERATE]

### The problem
(a) A1 says only "`index_file(...)`". The natural reading mixes a `resolve()`d file path with the
unresolved configured vault root; `index_file` computes the stored path via lexical
`os.path.relpath` (`indexer.py:68-76`) — across any symlinked vault (macOS `/var → /private/var`),
that yields `../../../private/...` as `node.path`, permanently defeating the hash fast-path and
tripping the duplicate-id "sync-conflict copy suspected" warning on every scan. Tests stay green
(pytest resolves basetemp; Linux CI has no symlink) — it ships silently. (b) A6 switches the MCP
collision loop to `unique_path`, which returns `str` (mirror `textutil.py:25-35`), but the next
statement calls `.resolve()` on it (`akanga_mcp/server.py:217`) → `AttributeError` on every
`create_node`; caught by A6's own gate, but the spec promised no re-derivation.

### What this means
One-line spec fixes: A1 → `index_file(str(full_path), get_db(), str(_vault_root()))` (resolved on
both sides); A6 → `target = Path(unique_path(str(vault_root), slug))`, and note the suffix series
changes (`-2,-3…` → `-1,-2…`; nothing pins it — verified).

## 11. `verify PHASE=8` is not `verify-all` — and the per-stage gates never run suites against solutions 0–7, exactly where the hand-edits land [MODERATE]

### The problem
`make verify PHASE=8` runs suites 00..08 against **`solutions/phase_08/src` only** (Makefile:366-386);
`verify-all` is the full per-phase walk (:388-414). A4 and A6 hand-edit `solutions/phase_00/` and
`phase_01/` parsers (unmanifested by design), and the new phase-00/01 tests run against solutions
1–7 in **no plan gate** — only in CI's 9-leg matrix and the merged-skeleton transition job
(ci.yml:111-220), which the plan never mentions. The final gate's "`# or: make verify PHASE=8`"
invites the cheap path precisely where the expensive one is the point.

### What this means
Delete the "or" from the final gate. In A4/A6's gates, add `make verify PHASE=1 && make verify
PHASE=2` (or run `verify-all` for A6 given its fan-out). Note CI's transition job as the post-push
check for the new skeleton stubs.

## 12. Scope drift between audit and plan: a taught-but-unported one-liner that N2 amplifies, two silently dropped TEACH items, and one overstated perf claim [MODERATE]

### The problem
(a) C6 teaches the duplicate-title nondeterminism as "a one-line ORDER BY and a good self-set
exercise" — but A2's rederive-all means any file add/remove now re-rolls the nondeterministic winner
for every ambiguous link vault-wide; the round amplifies the symptom while declining the one-line
fix in a function A3 already touches, with no N-entry recording the divergence (N4 set the standard:
known noteapp deltas get recorded). (b) F5's TEACH half (stub-creation stretch) — N3 says "doc-only
mention at most" and no workstream item ever writes the mention. (c) The conformance-table teaching
sidebar (audit F9/F11) — A6 *uses* the technique, nothing teaches it. (d) C2's framing sentence
("everything … well under a second at 5k nodes, all but one a NetworkX one-liner") contradicts its
own mirror sources (all-pairs Adamic-Adar "milliseconds to low seconds", structural holes "seconds",
exact betweenness unbenchmarked in pure Python) — minting a fresh unsourced benchmark in the round
that exists to remove unsupported claims.

### What this means
Decide **N10**: port oldest-wins (`ORDER BY` + one pinning test; C6 line flips to "resolved (N10)")
— the cheaper end given A2 lands anyway — or record "kept unspecified deliberately" as a numbered
decision. Pick "at all or not at all" for the stub-stretch mention and the conformance sidebar
(a 3-line `!!! tip` next to A6's test file) and record both. Soften C2 to the mirror's actual
numbers ("current-note-scoped scoring is sub-millisecond; whole-vault passes run in seconds at 5k
nodes") and name which item "all but one" refers to.

---

## What this analysis does NOT challenge

- **The recount is correct** — reproduced by code: 72 unique registry rows (zero duplicates across
  the 11 category tables), 12 symmetric, 4 pairs/8 members → **52 of 72** have no defined inverse;
  the phase-08 runtime parse yields exactly 72 (no double-counting — pairs table is name-first,
  regex is ID-first). The SC-005/SC-006 flag fix is right and breaks no other stated count.
- **B2's replacement block is semantically identical** to `solutions/phase_03/graph.py` (same dedup
  key, same boundary semantics, exact field/enum names — the solution's helper is even named `_record`).
- **C1's recursive CTE verified live**: runs correctly on the real schema with a cycle; the no-cap
  variant verified non-terminating — "the depth cap IS the cycle guard" is exactly right. The 40–250×
  figure is sourced; the ~170-node figure is real at phase-08:102.
- **N8's limit semantics are sound**: a full budget stays full, so no edge between two *included*
  nodes can be dropped; the only missing-edge case (mutual edge between two depth-boundary nodes)
  predates the limit — worth one docstring sentence, not a redesign.
- **All gate commands exist as named** (`test-solution`, `verify`, `verify-all`, `examples-all`,
  `skeleton-check`, `sync-forward FROM/FILE/BASE/APPLY=1`); the raw `sync_forward.py` invocations are
  argparse-valid; `--check-all`'s completeness pass works as claimed (textutil's manifest entry IS
  same-commit-mandatory); skeleton_check accepts the planned stubs; B1's rename-atomicity claim is
  real (lint check 4 errors on either one-sided rename); B2→C4 ordering is safe **only** as one
  commit (doc-first split trips lint check 1 — the plan's "in one step" is load-bearing).
- **Decisions N1, N4–N6, N8 core reasoning** — all compatibility re-greps held (72 slugs classify;
  no fixture pins old slugs or double edges; no test asserts file byte-stability after POST /edges;
  `upsert_edge` conflict returns the existing row id, so A1's idempotency claim holds).
- **Audit→plan traceability**: 29 of 32 audit items COVERED; the 3 PARTIAL/DROPPED are critique 12.

## Risk matrix

| # | Risk | Severity | Requires |
|---|---|---|---|
| 1 | mkdocs gate is a no-op; link check doesn't exist | CRITICAL | mkdocs strict+validation; real link step or drop the claim |
| 2 | DELETE/409 miss folded edges (`target_id: ""`) → zombie edges | SERIOUS | title-fallback matching + 1 test |
| 3 | Hyphen/underscore key contradiction left standing, re-propagated by C6 | SERIOUS | phase-01a:120-139 edit + C6 fix (+ optional dual-read tolerance) |
| 4 | Taught contracts change, phase docs stale, no learner migration note | STRUCTURAL | A4/A6 doc items + "Changed" admonitions + resume/skeleton path |
| 5 | C3 collides with B3/B4/B5; table contradiction; no stale-line rule; doc-lint missing from A gates | STRUCTURAL | resequence C3; execution-rules preamble; gate additions |
| 6 | check-6 false positive on phase-08:106 | SERIOUS | context-anchored regex + known-negative test case |
| 7 | B1/B6 sweep holes (kg-theory:157, ghost `/results`, `type="active"`, wrong gate expectation) | SERIOUS | 5 table additions + widened gates + AkangaApp exemption note |
| 8 | Mirror un-ignored; NOTEAPP SYNC contradicted; CLAUDE.md stale; audit on learner site | SERIOUS | 4 one-line governance edits |
| 9 | N2 overstates reach; docstring rewrite erases a true limit | MODERATE | narrow the rewrite + amend N2/C6 text |
| 10 | index_file path-convention mixing; unique_path str/Path | MODERATE | two one-line spec fixes |
| 11 | verify-8 ≠ verify-all; solutions 0–7 ungated where hand-edits land | MODERATE | gate strengthening in A4/A6 + final gate |
| 12 | Scope drift: unported one-liner N2 amplifies; 2 dropped TEACH items; C2 perf claim | MODERATE | decide N10; record drops; soften C2 |

## Suggested priority for resolution

1. **#1, #8** — gate and governance integrity first; they protect everything else (30 min of plan edits).
2. **#2, #3, #10** — A1's spec must be corrected before Stage 1 executes (they're all in the same commit's blast radius).
3. **#4, #5** — structural: add the execution-rules preamble, resequence C3, add the doc items and learner notes to A4/A6.
4. **#6, #7, #9, #11** — sweep/gate amendments, cheap and mechanical.
5. **#12** — one real decision (N10 duplicate-title), two record-the-drop entries, one sentence softened.

All 12 are plan amendments — none invalidates the plan's architecture, decisions N1–N9's core
reasoning, or the stage structure beyond moving C3.

---

## Resolution log (2026-06-12 — all 12 resolved into Plan Rev 2)

All critiques resolved as **Changed** in `docs/plan-noteapp-alignment.md` (Rev 2), drafted by
three verification agents and integrated in one pass. Notable verification-driven upgrades
found while drafting the fixes:

| # | Resolution |
|---|---|
| 1 | **Changed.** New Step 0.5 (commit G-0): `strict: true` + full `validation:` block in mkdocs.yml, `noteapp-alignment-audit.md` → exclude_docs, `deployment.md` → nav (verified green pre-flight). "link check" claim deleted — strict build IS the link check. C1/C2 carry their own nav entries. |
| 2 | **Changed — and upgraded.** Title-fallback matching (`_fm_edge_matches`) alone was verified INSUFFICIENT: `write_back` re-folds the prose inside the DELETE handler itself (`indexer.py:139` + `merge_edges`). DELETE now also **de-types the originating `[[T \| rel]]` shorthand to `[[T]]`**. Two new tests (`test_delete_folded_typed_edge_stays_dead`, `test_post_duplicate_of_folded_edge_returns_409`). N1 amended. |
| 3 | **Changed.** phase-01a:120-139 + four prose mentions flip to underscore keys (commit A-3); C6's `target-id` spelling fixed; **new decision N11**: dual-spelling read tolerance ported from phase_01's `_edge_from_dict` into the two canonical readers — read both, write underscores — with `test_hyphenated_edge_keys_are_read`. |
| 4 | **Changed.** A6 gains a full docs item (What You Build rows, Deliverable rewrite, two contractual test names `test_slugify_conformance_table`/`test_split_pipe_segment_table`); A4's doc item extended (function-table row, de-counted "15 tests"); four "Changed 2026-06" admonitions (00→A-4, 01a→A-3, 03→C-4, 06→A-1) with VERIFIED migration mechanics (`skeleton_merge.py` is append-only — non-destructive claims true for 00/01a, honestly NOT claimed for 03/06); N6 asymmetry sentence added to phase-06 (which contains no "409" today — the sentence introduces it + the :58 roll-call). |
| 5 | **Changed.** Execution-rules preamble (locate-by-text, range-replace guard, doc-lint-before-commit, commit-message style); C3 moved to Stage 9.5 with a new collision-table row; phase-01a collision cell corrected (A4↔B1 disjoint); doc-lint added to A-1/A-3/A-4 gates. |
| 6 | **Changed.** check-6's second pattern context-anchored (`of the (\d{2,3})(?=\s+(?:relation\|typed\|directed\|have no))` — empirically tested: phase-08:106 no-match, "52 of the 72 relation types" matches 72); known-negative/known-positive cases pinned in the spec; C1 phrases the 170 figure without "of the". |
| 7 | **Changed — and extended.** B1 gains kg-theory:157 + implementation-plan:115 (both FIX); A4 gains phase-01a:181 (registry location); B6 gains phase-06:191 (ghost `/results` endpoint), json-rpc:296-298 (tag-query rewrite — the real tool has NO `type` param at all), and three design-patterns ghosts (:19, :39, :107-120) the original list missed; B6's gate rewritten with the extended pattern and ONE expected residual (phase-05:488 AkangaApp — test-pinned, do not edit). **Bonus finding:** B1's `\| grep -v relation-vocabulary` filter matched line CONTENT and was hiding four of B1's own edit targets — replaced with path-level `--exclude` (verified: 41 hits across 31 files, all mapping 1:1 to the edit table). |
| 8 | **Changed.** Step 0 starts with the `.gitignore` append (committed in G-0); NOTEAPP SYNC superseding line drafted into B8; CLAUDE.md "Current focus" flip at Step 0.7 + close at C10 item 7; audit doc excluded from the site (Step 0.5) + README map entries (C10 item 2). |
| 9 | **Changed.** A2's docstring rewrite scoped to `full_scan_and_index`; `index_file`'s still-true limit sentence preserved; N2 register text amended; C6's taxonomy line scoped ("next full scan… the live watcher re-derives only the file that changed"). |
| 10 | **Changed.** A1 specs the exact call `index_file(str(full_path), get_db(), str(_vault_root()))` (resolved on both sides — symlinked-vault path corruption closed); A6 specs `Path(unique_path(...))` + the `-2,-3…` → `-1,-2…` suffix-series note (nothing pins the old series — verified). |
| 11 | **Changed.** Final gate's "or verify PHASE=8" deleted; A-3 gate gains `verify PHASE=1 && verify PHASE=2`; A-4 gate upgraded to `verify-all`; CI's `transition` job (ci.yml:111) named as the post-push check. |
| 12 | **Changed.** (a) **New decision N10 + new item A7**: deterministic duplicate-title resolution ported — verified noteapp uses `ORDER BY created_at ASC, id ASC`, the curriculum schema has NO timestamp column (and a minted one wouldn't survive `rm *.db`), so **`ORDER BY path ASC`** is the rebuild-stable equivalent; lands in commit A-2 with a determinism-pinning test; C6's line updated. (b) Stub-creation stretch mention drafted and assigned to C6's commit; N3 amended. (c) Conformance-table tip drafted into A6's phase-00 doc item; N9 amended to cover all TEACH-tier doc adoptions. (d) C2's framing softened to the mirror's actual benchmarks (sub-ms current-note scoring, low-seconds whole-vault passes; "all but one" made precise — the orphan scan is the pure-SQL item). |

Register after resolution: **N1–N11** (N1/N2/N3/N9 amended; N10/N11 new). Plan Rev 2 is the
executable artifact; this analysis is closed.
