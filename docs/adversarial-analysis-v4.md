# Adversarial Analysis V4 — Verify the Verification

> **Date:** 2026-06-12 · **Audience:** contributors — internal analysis, excluded from the published site
> **Lens:** Round 4 — *"trust nothing machine-written under deadline: verify the verifiers, read the patched text whole, run the runtime, look where no round could."* Rounds 1–3 resolved 120+ findings; the remediation layer itself (tests, tooling, CI, doc patches — the largest body of deadline-shipped artifacts in the repo) had never been attacked.
> **Method:** 5 parallel agents — cold-start execution walkthrough, safety-net audit, editorial whole-text read, runtime truth (live REST/MCP/3.12), structural blind spots. Execution-first where the sandbox allowed; every load-bearing static claim re-verified by the orchestrator before acceptance (`make setup` false-green, AKANGA_SRC dead warning, phantom test name, manifest self-contradiction — all reproduced).

---

## Claims ledger (executed live this round)

| Claim | Result |
|---|---|
| **E10**: `requires-python>=3.12` | **CLOSED — CONFIRMED.** Cold 3.12.8 env, 121 packages, all 9 phases green (177 tests incl. stdio smoke) |
| SEC-02/04/06 + SEC-01 delimiters at the live transport layers | **CONFIRMED under fire** — traversal 400s with zero bytes planted; FTS operators defanged at HTTP; delimiters byte-intact through FastMCP stdio *with a live injection payload inside* |
| All 7 console examples post-Round-3 | CONFIRMED green |
| `vault-check PHASE=0` accepts `create()` output | CONFIRMED (but see #7b) |
| `make mcp` launches a working server | **REFUTED** (#2) |
| `make serve` serves an existing vault | **REFUTED** for cold start (#2) |
| Typed inline edges reach the DB typed | **REFUTED** at runtime (#7) |
| `[graph]` extra delivers the promised renderer | **REFUTED** (#12) |

---

## Consolidated Findings

### 1. The first command a learner ever runs false-greens on total failure [CRITICAL — reproduced]
*A1; orchestrator-verified.* `make setup` (and `setup-phase`, `setup-workshop`, `vault-init`) chain with `;`, so the recipe's exit status is the final `printf`'s. With `uv` absent: `command not found` → green **"Done."** → exit 0 (reproduced verbatim). `vault-init` goes further: it writes a **corrupt `akanga.yaml`** (blank workspace UUID) and prints "Vault ready." And `uv` installation instructions exist nowhere on the learner path — README has no Prerequisites section at all.
**Fix:** `.SHELLFLAGS := -ec` (or `&&`-chain); a `need-uv` preflight reused from study.sh's pattern; 3-line Prerequisites block in README (uv, Python ≥3.12, git).

### 2. The capstone runtime entry points don't work as documented [HIGH — executed]
*A4, live protocol evidence.* (a) `make mcp` passes `--vault/--db` argv that `akanga_mcp/server.py.__main__` **never parses** (it reads env vars only) → `db` stays None → every tool returns empty with `isError: false`: a healthy-looking MCP server that knows nothing, forever, with no startup warning. Tests never catch it because they call `init_server()` directly. (b) Neither `create_app()`'s lifespan nor `init_server()` ever indexes the vault — `make serve` over a 50-node vault returns `[]` from `/api/v1/nodes` unless the TUI happened to index the same `.db` first; that sequencing dependency is recorded nowhere, and POSTing an edge to a disk-only node 400s.
**Fix:** argparse in `__main__` (or Makefile exports the env vars) + loud exit if `db is None`; call the (hash-first idempotent) `full_scan_and_index` in both lifespans, or at minimum log "serving N indexed nodes"; mirror in the phase-8 skeleton docstrings.

### 3. The convergence tooling ignores its own manifest — and the gate's coverage decays [HIGH]
*A2; manifest contradiction orchestrator-verified.* `sync_forward` propagate mode never opens `sync_manifest.toml`: the documented fix command for `server.py` would clobber phase_08's intentionally-divergent copy, and `--check-all` (whose `applies_to` stops at 7) would report the broken tree **converged** — drift gate green on a broken phase 8. The `excluded` key is read by no code, and the manifest already self-contradicts (sync_worker: `applies_to` includes 8 *and* `excluded_reason` says "phase_08 does not ship sync_worker.py" — stale from the Round-3 integration pass itself). Unguarded surface: `akanga_tui/app.py` exists in **4 copies outside the gate**; no completeness check fails when a new multi-copy file appears.
**Fix:** propagate consults the manifest (refuse/warn on excluded or out-of-range targets); check_all validates manifest self-consistency; a completeness pass flags any ≥2-copy path absent from the manifest (with an explicit ignore list if TUI divergence is intended — that intent is currently recorded nowhere).

### 4. The state every real learner occupies — merged skeletons — is verified by nobody, and the merge breaks it [HIGH]
*A1 + A2 convergent.* `skeleton_merge` delivers function/class stubs but **not their imports**: the documented phase-0→1 path ends in `AttributeError: module 'akanga_core.parser' has no attribute 'Edge'` — actively misleading (Edge IS in their models.py); implementing the merged stubs then hits `NameError: Edge`/`NameError: Path`. It is also blind to signature evolution — the curriculum's *first real transition* (`create()` gaining url/external_type/description at 1B) is silently skipped with no report — and to module-level constants (`Assign`/`AnnAssign`); on a learner syntax error it prints a **false all-clear** ("your preserved files already have every symbol") and exits 0. Adjacent: `make skeleton PHASE=8` copies an `app.py` marker pointing at a phase-07 file that doesn't exist. CI tests pristine skeletons and pristine solutions — never the merged product.
**Fix:** merge `Import`/`ImportFrom` diffs; report signature collisions ("`create` exists but this phase changed its signature"); extend to Assign/AnnAssign; distinct exit + summary on syntax errors; fix the phase_08 marker; **add the missing CI job**: skeleton N−1 → `make skeleton PHASE=N` → run phase-N tests → assert every failure is NotImplementedError, never NameError/ImportError.

### 5. The Round-2 fix created a new contract surface (test-name enumerations) and it has already drifted in 4 of 5 docs [HIGH]
*A3; phantom test orchestrator-verified.* phase-02 names a test that doesn't exist (`test_read_only_database` — renamed in remediation, doc never updated) and omits 4 shipped tests; phase-04 hides two real deliverable tests (`re-touch postpone`, `delete grace`) inside the sync-services "background color" box — a learner building to the Rules + Deliverable list fails tests whose spec lives in ambience; phase-00's "by name" list is 17 of 18; phase-08's "complete suites" claim omits `test_mcp_stdio.py` + 4 tests. `check_doc_contracts.py` lints signatures/targets/paths — test names are its blind spot, and that's exactly where drift regrew.
**Fix:** fourth check class — harvest `test_*` tokens from Deliverable sections, verify existence, flag shipped-but-unlisted; editorial sync of the 4 docs; promote the grace-window contract into phase-04's Rules + Deliverable list.

### 6. The AKANGA_SRC warning is dead code; infra failures unlock `make peek` [SERIOUS — reproduced]
*A1; orchestrator-verified (warning did not fire with AKANGA_SRC unset).* `$(origin AKANGA_SRC)` returns `file` for a `?=` makefile assignment, never `default` — the warning block added in remediation is unreachable under every invocation, while CLAUDE.md documents it as existing. On the same path: a collection-error run still appends a `red` line to `.akanga-progress`, which both pollutes `make resume` and **unlocks `make peek`** without any honest attempt. The conftest's missing-src message says "Create your src/ directory" — the right action is `make skeleton PHASE=0`, and nothing says so.
**Fix:** condition → `[ "$(origin AKANGA_SRC)" = "file" ]` (one word); don't record red lines on pytest exit codes 2–4; conftest message names `make skeleton`.

### 7. Typed inline edges never become typed at runtime; the validator nags phase-0 learners for following the doc [SERIOUS — executed]
*A4, end-to-end protocol evidence.* (a) `write_back` — Phase 1A's flagship — is **dead code in the running system**: no indexer, watcher, REST, or MCP path ever calls it; a node containing `[[SQLite WAL Mode | supports]]` reaches MCP `get_context` as `--[wikilink]-->`, relation silently dropped; the architecture doc's "folds inline captures into frontmatter" describes a fold no component performs. (b) A vault built strictly per the phase-0 doc passes `vault-check PHASE=0` but emits **12 warnings** telling the learner to use the typed form the doc explicitly defers to 1A — first contact with the validator is a wall of contradictions. Bonus: phase-8 example prints `[END ...]` while rag.py emits `[/ ...]`.
**Fix:** invoke `write_back` from the watcher's on-modified path or `index_file` (it's atomic + idempotent by its own tests); suppress the untyped-wikilink warning for `--phase 0`; harmonize the closing delimiter.

### 8. The 35–55h estimate quietly expired while Rounds 2–3 enriched what it measures [SERIOUS]
*A5, arithmetic shown.* Real total ≈ **46–75h**: per-phase coding 34–51h + 30,401 words of phase-doc reading (2.5–3.5h) + **70 hard-required vault nodes** (vault-check fails without them; 5–9h) + diff ritual (2.5–5h) + break-it blocks (2.5–6h). README:28 calls vault work "**optional**" while phase docs list it as a deliverable and the Makefile's finish line is `make vault-check FULL=1` — the time budget and the deliverable definition disagree, as accumulated residue of three rounds adding enrichment in isolation.
**Fix:** split estimate in README ("34–51h implementation + 12–24h reading/vault/reflection — the vault is a deliverable, not an extra"); delete "optional"; per-phase header gains "~Xh code + ~1h vault/reflect".

### 9. CLAUDE.md is two rounds stale — the lens every future session is force-fed [SERIOUS]
*A5.* It still asserts solutions = "phase_08 only", "Current focus: Round 2", "solutions for 0–7 do not exist yet", a phase-8 solution "being brought up to its suite", and omits everything Round 3 built (run/serve/mcp/resume/peek/checkpoint/verify, drift gate, canary, E1–E10). Every round audited the repo *through* CLAUDE.md; none audited CLAUDE.md as the lens — a trusting future session would start re-creating solutions that exist. Line 37 states the correct rule ("trust `make status`") six lines after violating it. Related: `docs/README.md` (the Round-2 map fix) omits v3, status-remediation, and the facilitator guide, and still calls v2 "authoritative".
**Fix:** rewrite CLAUDE.md to carry **zero** completion claims (point at `make status` + status-remediation); update the security-section paths (noteapp → solutions); refresh docs/README; consider archiving v1/v2 analyses now that the convention exists.

### 10. The timing tests' margins are survivable but one failure message lies, and the macOS fix is dead code on CI [SERIOUS]
*A2, margins computed.* The re-touch test has a 250 ms margin on a loaded 2-core runner, and when it flakes the first assertion to trip **falsely accuses a correct implementation** of the early-fire bug with an authoritative remediation message. The reference watcher computes deadlines with `time.time()` while tests measure `monotonic()` (NTP-step hazard — the solution should use monotonic regardless). A duplicate flat-`sleep(0.2)` async test in test_watcher.py was never upgraded to the `_wait_until` pattern its twin got. And on Linux CI (inotify), an atomic replace emits `MOVED_TO`, never the coalesced delete — **the phantom-delete fix's designed scenario never executes in CI**; green CI does not validate the macOS behavior. Cumulative legs amplify any flake ×5 per push.
**Fix:** widen the margin (re-touch at 0.15 or debounce 800); split the assertion message so a flake can't impersonate the bug; monotonic in the solution; upgrade/delete the duplicate test; note the macOS-only branch in the test docstring (or a macOS CI leg if ever affordable).

### 11. The vault validator's embedded manifests were stale at the moment they shipped [SERIOUS]
*A2, diffed.* Phase 6 manifest lacks `CORS`, phase 7 lacks `Remote Trust` — both nodes added to the doc tables by W4 in the **same commit** that embedded the manifests (W6). `vault-check PHASE=6` silently under-enforces the exact contract it exists to enforce; the defense is a "keep in sync" comment — the mechanism whose failure motivated the contract lint, which doesn't cover vault tables. Also found: the lint silently ignores doc functions *absent* from skeletons (renames — the most common drift) and its coverage decays to ~zero for phases 7–8 (marker files skipped).
**Fix:** parse the doc tables at runtime (single source of truth, ~20 lines) or add manifest-vs-table to the lint; cover the absent-symbol case.

### 12. The phase-5 stretch promise cannot be delivered by any installable version of its dependency [MODERATE — executed]
*A4.* `textual-kitty` 0.4.0 (the latest ever published) exports nothing, ships no widget, and its own demo crashes on a missing module — the doc's "renders the graph as a PNG inside a Textual widget" is unachievable with the pinned package; the ecosystem moved to **`textual-image`**. The canary's import check can't distinguish an empty `__init__` from a working renderer.
**Fix:** swap dependency to textual-image; update phase-05 Layer-1 prose; canary imports the widget entry point, not the top-level package.

### 13. Editorial debt: measured repetition, voice drift, and pseudo-admonitions [MODERATE]
*A3, counted.* Docs grew +13% (phase-00 **+47%**); the direction rule appears 3–5× in phase-08, WAL-vs-Lock 4× in phase-02, the tmux trap 5× in phase-05; phase-00's 67-line YAML-injection insert is 15% of the doc wedged mid-concepts; phase-04's 153-line logging section sits *after* the phase ends and points at a site-excluded doc. Changelog-speak addressed to nobody ("earlier versions of this doc…"), unresolvable `BUG-*/CCR-*` ticket IDs in learner prose, two coexisting callout grammars, and three security inserts rendered as broken pseudo-admonitions while the `admonition` extension sits enabled and unused.
**Fix:** one canonical home per rule + one-line pointers; move the YAML-injection body to its foundations doc and the logging steps to a published home; delete "earlier versions" sentences; translate ticket IDs to plain English; convert the big inserts to `!!! warning` admonitions.

### 14. Consumable but not publishable [MODERATE]
*A5.* No git tag has ever existed — facilitators are told to schedule workshops on un-pinned `main` mid-remediation; the two newest commits share the identical message "feat: remaking after adversarial analysis" (~9,000 insertions untraceable to Resolution Log entries); CONTRIBUTING solicits PRs with **zero** inbound-licensing statement (one line closes it while it's still cheap); "**Mirin**" is translated nowhere in the repo (the exemplary, primary-source-cited Guaraní material is buried in a Phase 1B exercise); the Windows disclaimer lives only in the facilitator guide, after the point a native-Windows learner has already failed at `make`.
**Fix:** tag `v0.1.0` at green HEAD; commit-message convention line in CONTRIBUTING + inbound=outbound sentence; 3-sentence "About the name" block in README; one platform line in the Quickstart.

---

## What This Round Does NOT Challenge
The enforcement *core* held: the EventBus lock discipline survived deliberate interleaving attack; every SEC property held under live fire at the real transport layers (including a prompt-injection payload through FastMCP stdio); the 3.12 floor was honestly hedged and is now confirmed; escape hatches haven't inflated ("illustrative" ×3, ALLOW list still empty); the published-site quarantine has zero leaks; resume/peek's tone and the teaching-voice failure messages were singled out as exemplary by the cold-start stranger. Round 4's findings cluster at the **rim** — entry points, merge seams, claim freshness — not in the verified center.

## Risk Matrix

| # | Risk | Severity | Requires |
|---|---|---|---|
| 1 | `make setup`/`vault-init` false-green on total failure | CRITICAL | Makefile `-ec` + preflight + README prereqs |
| 2 | `make mcp` lobotomized; `serve` serves empty graph | HIGH | argv parse + lifespan indexing |
| 3 | sync_forward ignores manifest; excluded dead; TUI ×4 unguarded | HIGH | manifest-aware propagate + completeness check |
| 4 | Merged-skeleton state broken & never CI-verified | HIGH | import merge + collision report + CI transition job |
| 5 | Test-name enumerations drifted (phantom test) | HIGH | 4th lint check + doc sync |
| 6 | Dead AKANGA_SRC warning; peek unlocked by infra failures | SERIOUS | one-word origin fix + exit-code guard |
| 7 | write_back dead at runtime; D10 validator nagging | SERIOUS | wire write_back + phase-0 warning suppression |
| 8 | Time estimate expired; "optional" vault contradiction | SERIOUS | split estimate + delete "optional" |
| 9 | CLAUDE.md two rounds stale | SERIOUS | zero-claims rewrite + docs/README refresh |
| 10 | Lying flake message; time.time in solution; macOS fix unvalidated on CI | SERIOUS | margins + message split + monotonic |
| 11 | Vault manifests stale at ship | SERIOUS | parse doc tables at runtime |
| 12 | textual-kitty cannot deliver the promised renderer | MODERATE | swap to textual-image |
| 13 | Editorial repetition/voice debt (+13%, rules ×3–5) | MODERATE | canonical-home editorial pass |
| 14 | No tag, identical commit messages, no inbound license, Mirin untranslated | MODERATE | v0.1.0 tag + CONTRIBUTING lines + README blocks |

## Suggested Priority
**Tier 0 (hours, learner-facing trust):** #1, #6, #2, #7b (validator nag), #9 (CLAUDE.md).
**Tier 1 (the safety net's own bugs):** #3, #4, #5, #11, #10.
**Tier 2 (contract truth):** #7a (write_back wiring), #8, #12.
**Tier 3 (editorial + publishing):** #13, #14 (tag first — it's one command).

## Appendix — Agent Coverage
A1 cold-start → #1 #4 #6 (+ verbatim confirmation script) · A2 safety net → #3 #4 #5(blind spot) #10 #11 · A3 editorial → #5 #13 (+ docs/README staleness in #9) · A4 runtime → #2 #7 #12 + claims ledger (E10 closed, SEC confirmed live) · A5 blind spots → #8 #9 #14. Orchestrator reproductions: setup false-green, dead warning, phantom test, manifest contradiction. Notable: A1 and A2 found #4's two halves independently (imports vs signatures); A4's live MCP run and A1's static trace agree on the entry-point failure class.

---

## Resolution Log

*Status as of 2026-06-12 (F1–F5 batch + orchestrator integration). Verification: 9/9 cumulative legs green
(leg 08: 178), 8/8 merged-skeleton transitions sane (solutions-based simulation), stdio 3/3 (env + argv +
loud-fail), contract lint exit 0, drift gate 56+ pairs / 0 drifting / completeness-governed, mkdocs --strict,
ruff clean. Reproduced fixes confirmed live: setup false-green now exits 1 loudly; the AKANGA_SRC warning
fires for the first time since it was written; textual-image 0.13.2 widget imports.*

| # | Finding | Status | Resolution |
|---|---|---|---|
| 1 | setup/vault-init false-green | **Resolved** | `.SHELLFLAGS := -ec` + need-uv preflight + README Prerequisites (F1) |
| 2 | mcp argv ignored; serve empty graph | **Resolved** | argparse + exit-2 loud-fail; lifespan/init_server index at startup, "serving N nodes" log; tests pin both channels in isolation (F3/F4) |
| 3 | sync_forward ignored manifest; coverage decay | **Resolved** | manifest-aware propagate (+--force), self-consistency + completeness passes; manifest reality-checked (akanga_tui 5/6/7 mutually distinct → honest exclusions; stale server-exclusion dropped) (F2) |
| 4 | Merged-skeleton state broken & unverified | **Resolved** | import/constant merging + signature-collision reports + exit-3 on syntax errors (F2); CI `transition` job — base corrected to prior SOLUTION (a real learner's state) after the skeleton-base sim false-failed; 8/8 sane (F1 + orchestrator); lying phase_06/07/08 app.py markers removed/stubbed (F3 + orchestrator) |
| 5 | Test-name enumeration drift | **Resolved** | lint checks 4a/4b/5 added (F2); docs synced (F5); residual phase-01a + 6 sketch blocks resolved via real-name list + illustrative markers (orchestrator) |
| 6 | Dead AKANGA_SRC warning; peek unlock | **Resolved** | origin=file fix (warning now fires — verified); progress lines only on pytest exit 0/1 (F1) |
| 7 | write_back dead; phase-0 validator nag | **Resolved** | fold wired into the changed-file index path (canonical, propagated); --phase 0 suppression + how-to footer on hard failures; typed-edge fold test green (F3/F2/F4 + orchestrator) |
| 8 | Estimate expired; "optional" vault | **Resolved** | split estimate (34–51h + 12–24h); "optional" deleted; per-phase "+~1h vault/reflect" (F5) |
| 9 | CLAUDE.md two rounds stale | **Resolved** | zero-claims rewrite ("trust the tooling over any prose — including this file"); docs/README map refreshed (F5) |
| 10 | Flake-message lies; time.time; macOS branch unvalidated on CI | **Resolved** | margin 350ms + split truthful assertions; monotonic deadlines in the canonical watcher (propagated); macOS/inotify notes in tests and code (F4/F3) |
| 11 | Vault manifests stale at ship | **Resolved** | runtime-parsed from doc tables (single source); CORS-less phase-6 vault now hard-fails (F2) |
| 12 | textual-kitty cannot deliver | **Resolved** | textual-image>=0.6,<1 (0.13.2 locked; AutoImage widget verified); canary asserts the widget entry point; doc prose updated (F1/F5) |
| 13 | Editorial debt | **Resolved** | canonical rule homes + pointers; YAML-injection → foundations; logging → published observability doc (+nav); changelog-speak deleted; ticket IDs translated; admonitions converted (F5) |
| 14 | Not publishable | **Resolved** | Prerequisites + About-the-name + platform line (F5); commit-message + inbound-licensing sections (F1); **v0.1.0 tag after this commit's CI run** |

**Process note:** the transition job's first local run false-failed 2 of 4 transitions — the simulation used
pristine prior *skeletons* (marker files import nothing) where a real learner has implementations; corrected
to prior *solutions* before the job ever reached CI. Verifying the verifier, recursively, remains the theme.
