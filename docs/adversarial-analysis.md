# Adversarial Analysis — Akanga Mirin Implementation Plan

> **Generated:** 2026-05-24  
> **Input:** `docs/implementation-plan.md` reviewed by 7 specialist agents  
> **Total findings:** 93 across Learner Experience (14), Software Architecture (14),
> Security & Threat Modeling (12), Open Source Sustainability (12), Project Management
> & Scope (13), QA & Test Engineering (15), Educational Theory & Pedagogy (13)

---

## 1. Executive Summary

Seven adversarial specialist agents reviewed the implementation plan from orthogonal
perspectives and produced 93 findings. Ten cross-cutting issues — each flagged by three
or more independent perspectives — represent the highest-leverage problems.

**Pre-implementation blockers (must resolve before Sprint 1 begins):**

| # | Issue | Est. Fix |
|---|---|---|
| 1 | Missing LICENSE file — corporate adoption blocked | 2 min |
| 2 | EventBus startup race crashes on first OS event | 30 min |
| 3 | `node.body` from DB is undefined; `_serialize_triples` reads stale data | 1–2 h |
| 4 | `max_triples=200` produces ~31 k chars but test asserts `<15 k` | 30 min |
| 5 | macOS `os.replace()` fires `on_moved`, watcher only handles `on_modified` | 1 h |
| 6 | CONTRIBUTING.md stub absent — first PR will be wrong | 30 min |
| 7 | Inverse edge direction bug in `_serialize_triples` | 30 min |

**Key cross-cutting themes:**

- The estimate is arithmetically wrong: subtotals sum to ~192.5 h, plan claims 270 h,
  realistic effort is 380–500 h.
- Every test is happy-path; zero error-path tests exist across all 9 phases.
- The `AKANGA_SRC` isolation mechanism has at least four silent failure modes.
- No CI/CD: `make verify-all` is an honor system.
- Phase 1 introduces 12+ concepts simultaneously, exceeding working memory limits.

---

## 2. Must Fix Before Implementation (Pre-Sprint 1)

> **MUST FIX BEFORE SPRINT 1**

These issues exist in content already written (phase docs, architecture notes). Leaving
them in place means Sprint 1 work is built on a broken foundation that will require
retroactive corrections through all downstream phases.

### BUG-01 — `node.body` from DB is undefined in Phase 8

**Problem:** `_serialize_triples` uses `node.body` which is not stored in the DB `nodes`
table. At runtime this produces empty descriptions or crashes. The partial fix described
in the plan (`parse(node.path).body`) is incomplete — the pattern
`desc = node.description or node.body[:120]` still appears in serialization code.

**Fix:**
```python
# Replace every occurrence of node.body in _serialize_triples with:
body = parse(node.path).body[:500] if node.path.exists() else ""
desc = node.description or body
```
Also add a total character cap independent of `max_triples`. A 10 MB node with 200
triples would otherwise produce gigabytes of LLM context.

### BUG-02 — `max_triples=200` incompatible with `<15,000` char assertion

**Problem:** 200 triples × average serialized length produces ~31,000 characters. The
test that asserts `len(result["context"]) < 15_000` will always fail. These two limits
are analytically incompatible and were specified in different places without
cross-checking.

**Fix:** Either reduce `max_triples` default to 80 (yields ~12,000 chars) or raise the
test threshold to 35,000. Decide which budget the LLM actually needs and make both
constants consistent.

### BUG-03 — Inverse edge direction in `_serialize_triples`

**Problem:** Incoming edges (where the current node is the *target*) are serialized
using the forward relation name. This produces `B --[contradicts]--> A` when `A` is the
source, silently inverting the knowledge graph semantics passed to the LLM.

**Fix:** For incoming edges, use the inverse relation name if defined, or prefix with
`<--` to indicate direction. Add a test that creates a directed edge and verifies the
serialized string contains the correct directionality for both the source and target
node's perspective.

### BUG-04 — EventBus startup race

**Problem:** `set_loop()` is not called on the EventBus before `watcher.start()`. The
first OS filesystem event arrives before the event loop is set, triggering
`AttributeError: 'NoneType' object has no attribute 'call_soon_threadsafe'`. This
happens in production on any fast filesystem (SSD). The existing test suite masks it
with `time.sleep()`.

**Fix:** Call `eventbus.set_loop(asyncio.get_event_loop())` in `AkangaApp.start_all()`
before `self.watcher.start()`. Add an integration test that starts the watcher and
publishes an event within 50ms (no sleep).

### BUG-05 — macOS `os.replace()` fires `on_moved`, watcher misses it

**Problem:** On macOS, `os.replace(src, dst)` generates a `FileMovedEvent` (`on_moved`),
not a `FileModifiedEvent` (`on_modified`). The watcher's `on_moved` handler checks
whether the destination is a `.md` file and re-indexes it, but only if both source and
destination are in the vault. Atomic writes use a temp path (often in `/tmp`) that is
outside the vault — so the `on_moved` guard fails and the re-index never fires.

**Fix:** In `on_moved`, check whether `dest_path` is within the vault regardless of
`src_path`. Add macOS-specific test using `tmp_path` outside vault as the temp file.

### BUG-06 — Missing LICENSE file

**Problem:** The README states "MIT license." No `LICENSE` file exists. GitHub shows
"No license detected." Corporate security scanners block repositories with missing
license files, preventing any enterprise workshop adoption.

**Fix:** Create `/Users/arthurpieri/code/akanga_mirin/LICENSE` with standard MIT text.
Cost: 2 minutes.

### BUG-07 — Missing CONTRIBUTING.md

**Problem:** CONTRIBUTING.md is listed as "coming soon." With no guidance, early
contributors will submit Docker integrations, style violations, skeleton pollution, and
wrong-format PRs — all of which the maintainer must reject manually from scratch. The
reputation cost of this is disproportionate to the 30-minute fix.

**Fix (Sprint 1):** Add a minimal CONTRIBUTING.md stub with five bullet points:
1. Run `make check` before opening a PR.
2. Do not modify `solutions/` — open an issue instead.
3. SENTINEL comments are load-bearing — do not remove.
4. Phase doc changes require a corresponding test change in the same PR.
5. All new phases must include at least one error-path test.

---

## 3. Cross-Cutting Issues (CCR-1 through CCR-10)

### CCR-1 — Solutions accumulation creates unmanageable propagation risk

**Perspectives flagged:** Architecture, Project Management, OSS Sustainability, QA

**Problem:** The 9-phase serial structure produces up to 9 copies of every file.
A bug found in Phase 2's `VaultIndexer` must be patched in Phases 3–9. No tooling
exists to propagate fixes forward. The `indexed_db` pytest fixture couples every
downstream phase test to Phase 2's implementation. At 1 bug per sprint, this creates
36 unplanned patch operations in Sprint 4 alone.

**Resolution:**
- Add `scripts/sync_forward.py`: given a file path and starting phase number, diffs and
  applies the change to all later phases.
- Add `make sync-forward FILE=X FROM=N` Makefile target.
- Add 5 h rework buffer to Sprint 4 (adjust total estimate accordingly).
- Document the propagation fix procedure in a new Appendix B in the implementation plan.

### CCR-2 — The estimate is arithmetically wrong and systematically low

**Perspectives flagged:** Project Management, Learner Experience, Architecture

**Problem:** The plan states "~270 hours total." Category subtotals sum to ~192.5 h —
a 77 h discrepancy before any assumption is challenged. Three specific line items are
under-estimated by 2–3×:

| Task | Plan estimate | Realistic estimate |
|---|---|---|
| ARCH-24: TUI tests | 4 h | 12–20 h |
| PED-10: 10 foundation docs | 8 h | 20–30 h |
| PED-06: Common Pitfalls | 4 h | 18–27 h |
| Phase 5 (learner time) | 5–7 h | 12–20 h |

Realistic total: **380 h ±30%** (conservative) to **500 h** (with rework and review).

**Resolution:**
- Fix arithmetic: recompute category subtotals and confirm they sum to the stated total.
- Audit the three under-estimated categories with a second reviewer.
- Update the README estimate table to 380 h with an honest ±30% range.
- Do not promise a completion date until estimates are reconciled.

### CCR-3 — `AKANGA_SRC` has multiple silent failure modes

**Perspectives flagged:** Learner Experience, Architecture, QA

**Problem:** Four independent failure modes, any of which produces wrong behavior without
an error message:

1. Learner forgets to set `AKANGA_SRC` → tests run against the reference solution.
2. Relative path resolves differently depending on CWD → wrong module loaded silently.
3. Variable is lost between terminal sessions → no warning, falls back to solution.
4. IDE runs pytest without the env var → learner sees solution pass, thinks their code works.

Additionally, `sys.modules` cache means `sys.path.insert` does nothing for modules
already imported in the same pytest session. `make test-all` runs Phase 0 code against
all phase tests because the cache is never invalidated.

**Resolution:**
- Add explicit `sys.modules` cache invalidation to `_activate_learner_src()`.
- `make test PHASE=N` without `AKANGA_SRC` set must print a loud warning (or fail).
- Add `make where-is-my-src` diagnostic target that prints the resolved import path.
- Add a conftest assertion: if `AKANGA_SRC` is unset and `solutions/` is on `sys.path`,
  print `ERROR: You are testing the reference solution, not your code.`

### CCR-4 — No CI/CD; `make verify-all` is an honor system

**Perspectives flagged:** OSS Sustainability, Project Management, QA

**Problem:** Any PR can break a reference solution without detection if the contributor
skips `make verify-all`. `make test-all` self-validates against reference solutions
(always green), giving false confidence. Sprint 4's 100 h estimate is the longest sprint
and the most likely to have contributors skipping validation.

**Resolution:**
- Add `.github/workflows/ci.yml` running `make check` on every PR. Estimated: 1 h.
- Separate `make verify-solutions` (runs tests against reference) from `make test` (runs
  tests against learner code, fails without `AKANGA_SRC`).
- Add `make status` target showing which phases have complete skeleton/test/solution
  triads.

### CCR-5 — Timing-sensitive tests use `time.sleep` instead of synchronization primitives

**Perspectives flagged:** Learner Experience, QA, Architecture

**Problem:** `time.sleep(0.2)` with a 50 ms debounce leaves 150 ms margin — enough on a
developer laptop, zero margin on a CI machine under load. Phase 4 debounce tests and
Phase 5 live-update tests will produce intermittent failures proportional to CI load.
Additionally, `test_watcher_fires_on_save` uses `.write_text()` (not the atomic write
path), so the test exercises a different OS event than production code.

**Resolution:**
- Replace all `time.sleep` in watcher tests with `threading.Event.wait(timeout=5)`.
- Replace all `time.sleep` in async TUI tests with Textual's
  `await app.wait_until(condition, timeout=10)`.
- Replace `.write_text()` in watcher tests with the actual atomic write path
  (`tmp.write_text(); os.replace(tmp, target)`).

### CCR-6 — The repo is vaporware at clone time but README presents it as functional

**Perspectives flagged:** Learner Experience, Project Management, OSS Sustainability

**Problem:** Tests, skeletons, solutions, and examples are all `[TODO]`. The Quickstart
section describes commands that fail on a fresh clone. The repo will be public during
Sprints 1–4 with a placeholder README. CONTRIBUTING.md is listed as "coming soon."
Early adopters who clone during Sprint 2 will see broken commands and no guidance.

**Resolution:**
- Add a `## Status` banner to the Sprint 1 README (not the final marketing README):
  > "Sprint N of 5 active. Tests/skeletons/solutions in progress — expected completion
  > [date]. Star/watch for updates."
- Move CONTRIBUTING.md stub (5 bullet points, per BUG-07) to Sprint 1 deliverables.
- Add `make status` target that prints a phase completion matrix.
- Do not publish the marketing README until Sprint 5.

### CCR-7 — `node.body` / DB invariant has security implications

**Perspectives flagged:** Architecture, Security, QA

**Problem:** The BUG-01 fix (read body from disk) introduces an unbounded disk read.
At `depth=2` with 200 triples, `context_for_query` may read up to 200 files from disk.
A 10 MB node causes the function to return potentially gigabytes of content. The test
`test_context_for_query` only checks `"contradicts" in result["context"]` and passes
even when all descriptions are empty.

**Resolution:**
- Fix `_serialize_triples` with a size cap: `parse(node.path).body[:500]`.
- Add a total character cap: stop adding triples once the running total exceeds 12,000
  chars, regardless of `max_triples`.
- Add test: `test_context_for_query_with_large_body` — creates a node with 1 MB body,
  verifies response is under 15,000 chars and completes in under 100 ms.
- Add test: `test_context_for_query_descriptions_are_not_empty`.

### CCR-8 — Phase 1 cognitive load is catastrophically high

**Perspectives flagged:** Educational Theory & Pedagogy, Learner Experience

**Problem:** Phase 1 introduces 12+ distinct concepts simultaneously: `Edge` dataclass,
four-field dual-key (`relation_id`/`target_id`), 71 relation types, two-pass parsing,
sync queue, workspace registry, inline extraction, merge deduplication, reference
integrity. This exceeds the 7±2 working memory limit by a factor of nearly 2. Learners
who stall here never return.

**Resolution (requires design decision — see Section 6):**
- Split Phase 1 into Phase 1A (edge schema: `Edge` dataclass, four-field dual-key,
  inline extraction, merge deduplication) and Phase 1B (workspace registry, sync queue,
  reference integrity). The 9-phase sequence becomes a 10-phase sequence.
- Alternatively, defer sync queue and workspace registry to Phase 3.
- Add a "what you're building today" advance organizer at the top of Phase 1 that
  explicitly names the two concepts being introduced (not twelve).

### CCR-9 — No error-path tests across all 9 phases

**Perspectives flagged:** QA, Learner Experience, Educational Theory & Pedagogy

**Problem:** Every test in the plan is happy-path. Zero tests verify: malformed YAML
frontmatter, read-only DB, circular symlinks, detached HEAD git state, Textual pilot
with no selected node, MCP tool with 0 results. The test suite is the only feedback loop
for learners. A suite that never exercises failure paths teaches learners that error
paths don't need to be written.

**Resolution:**
- Add at minimum one error-path test per phase. Required set:
  - Phase 0: `test_parse_malformed_frontmatter`
  - Phase 2: `test_delete_nonexistent_node`, `test_db_read_only_raises_nonfatal`
  - Phase 3: `test_bfs_with_circular_edge`
  - Phase 4: `test_watcher_ignores_hidden_files`, `test_eventbus_subscriber_error_is_nonfatal`
  - Phase 5: `test_tui_no_selected_node_no_crash`
  - Phase 7: `test_git_detached_head_is_nonfatal`
  - Phase 8: `test_mcp_search_returns_empty_list`, `test_mcp_tool_with_missing_node_id`
- Add acceptance criterion to ARCH-19 through ARCH-27: "Each test file must include at
  least one error-path test."

### CCR-10 — No LICENSE file

**Perspectives flagged:** OSS Sustainability, Security, Project Management

**Problem:** README says "MIT" but no LICENSE file exists. GitHub shows "No license
detected." Corporate security policies block cloning repositories without a machine-
readable license. Every enterprise workshop adopter is blocked.

**Resolution:** Create `LICENSE` with standard MIT text. Cost: 2 minutes.
This is also listed as BUG-06 above — it appears in both lists because of its severity
and its cross-cutting nature (legal, adoption, and policy dimensions).

---

## 4. Per-Perspective Findings Table

### 4.1 Learner Experience (14 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| LX-01 | 🔴 Critical | Phase 1 cognitive overload (12+ concepts) | Split Phase 1 → 1A + 1B (see CCR-8) |
| LX-02 | 🔴 Critical | `AKANGA_SRC` silent failure modes | Add `sys.modules` invalidation, loud warning (see CCR-3) |
| LX-03 | 🟠 Major | Quickstart commands fail on fresh clone | Add Status banner to Sprint 1 README (see CCR-6) |
| LX-04 | 🟠 Major | Phase 5 estimate off by 3–5× for Textual beginners | Update estimate to 12–20 h (see CCR-2) |
| LX-05 | 🟠 Major | Phase 4 debounce tests are flaky on loaded machines | Replace `time.sleep` with `threading.Event.wait` (see CCR-5) |
| LX-06 | 🟠 Major | Phase 5 live update test is flaky | Use `app.wait_until()` instead of sleep (see CCR-5) |
| LX-07 | 🟠 Major | Test suite never exercises failure paths | Add one error-path test per phase (see CCR-9) |
| LX-08 | 🟠 Major | No "expected difficulty" signal before hard phases | Add advance organizer to Phase 4 and Phase 5 intros |
| LX-09 | 🟠 Major | Vault node exercises are transcription tasks | Replace half with open-ended "find the connection" prompts |
| LX-10 | 🟡 Minor | `make test` without `AKANGA_SRC` silently passes | Print loud warning or hard fail |
| LX-11 | 🟡 Minor | `AKANGA_SRC` lost between terminal sessions | Add `make where-is-my-src` diagnostic |
| LX-12 | 🟡 Minor | IDE runs pytest without env var, learner misled | Document in Phase 0 quickstart |
| LX-13 | 🟡 Minor | Reflect sections designed for groups, audience is solo | Add Solo/Group track labels to Reflect sections |
| LX-14 | 🟡 Minor | No phase-level difficulty self-assessment | Add 2-min prerequisite quiz at top of each phase |

### 4.2 Software Architecture (14 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| ARCH-01 | 🔴 Critical | `node.body` from DB is undefined in Phase 8 | Fix `_serialize_triples` with disk read + size cap (BUG-01) |
| ARCH-02 | 🔴 Critical | `max_triples=200` incompatible with `<15k` char assertion | Reduce `max_triples` to 80 or raise threshold (BUG-02) |
| ARCH-03 | 🔴 Critical | EventBus startup race crashes on first OS event | Call `set_loop()` before `watcher.start()` (BUG-04) |
| ARCH-04 | 🔴 Critical | macOS `os.replace()` fires `on_moved`, watcher misses it | Fix `on_moved` guard to check `dest_path` only (BUG-05) |
| ARCH-05 | 🟠 Major | Inverse edge direction bug in `_serialize_triples` | Use inverse relation name for incoming edges (BUG-03) |
| ARCH-06 | 🟠 Major | `db` global state in MCP server breaks test isolation | Replace module singleton with dependency injection |
| ARCH-07 | 🟠 Major | Double debounce: git commits fire before indexer finishes | Trigger `stage_and_commit` on `node_updated`, not `file_changed` |
| ARCH-08 | 🟠 Major | `sys.modules` cache breaks `make test-all` isolation | Invalidate cache in `_activate_learner_src()` (see CCR-3) |
| ARCH-09 | 🟠 Major | Phase 5 reference solution estimated at author's speed | Update Phase 5 learner estimate to 12–20 h (see CCR-2) |
| ARCH-10 | 🟠 Major | No patch strategy for bugs found after Phase N is written | Add `sync_forward.py` + `make sync-forward` (see CCR-1) |
| ARCH-11 | 🟠 Major | `indexed_db` fixture couples all downstream phases to Phase 2 | Document coupling; add fixture reset between phase sessions |
| ARCH-12 | 🟡 Minor | Watcher test uses `.write_text()` not atomic write path | Use `tmp.write_text(); os.replace(tmp, target)` in tests |
| ARCH-13 | 🟡 Minor | Phase 5 and Phase 6 solutions conflict on same vault | Document dual-watcher conflict; add guard or test |
| ARCH-14 | 🟡 Minor | `pip install -e .` shadows learner code in some configs | Document in Phase 0 setup instructions |

### 4.3 Security & Threat Modeling (12 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| SEC-01 | 🔴 Critical | Prompt injection: named risk, no mitigation specified | Wrap KG context in delimiter; add sanitizer; add anti-pattern to `SERVER_INSTRUCTIONS` |
| SEC-02 | 🔴 Critical | Symlink escape bypasses path traversal protection | Use `(vault_root / user_path).resolve().is_relative_to(vault_root.resolve())` |
| SEC-03 | 🟠 Major | `akanga.yaml` not in safe loader audit scope | Audit `akanga.yaml` parsing; apply same safe loader fix |
| SEC-04 | 🟠 Major | MCP HTTP transport binds to `0.0.0.0` not `127.0.0.1` | Default MCP bind address to `127.0.0.1`; add `--mcp-host` flag |
| SEC-05 | 🟠 Major | WebSocket `/ws` has no auth; leaks node titles in real time | Add token auth to `/ws` or document as localhost-only |
| SEC-06 | 🟠 Major | FTS5 operator injection (distinct from SQL injection) | Wrap user query in double quotes before passing to `MATCH` |
| SEC-07 | 🟠 Major | Rate limiting absent: LLM agent can create thousands of nodes | Add per-IP rate limit to REST API and MCP tools |
| SEC-08 | 🟠 Major | `node.body` unbounded disk read creates DoS vector | Add 500-char body cap and total 12k char context cap (see CCR-7) |
| SEC-09 | 🟡 Minor | Git tests may interact with real remotes | Add boundary assertion in `git_vault` fixture: assert no remote configured |
| SEC-10 | 🟡 Minor | YAML injection in node frontmatter | Confirm `python-frontmatter` uses safe loader; add test with injected content |
| SEC-11 | 🟡 Minor | No LICENSE file creates legal ambiguity | Create `LICENSE` file (BUG-06) |
| SEC-12 | 🟡 Minor | No security policy (`SECURITY.md`) or disclosure process | Add `SECURITY.md` stub with private disclosure email |

### 4.4 Open Source Sustainability (12 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| OSS-01 | 🔴 Critical | No LICENSE file — corporate adoption blocked | Create `LICENSE` (BUG-06) |
| OSS-02 | 🔴 Critical | No CI/CD — `make verify-all` is honor system | Add `.github/workflows/ci.yml` (see CCR-4) |
| OSS-03 | 🟠 Major | CONTRIBUTING.md absent — early PRs will be wrong | Add CONTRIBUTING.md stub to Sprint 1 (BUG-07) |
| OSS-04 | 🟠 Major | 9× code duplication; any dep upgrade patches 4–9 files | Add `sync_forward.py` (see CCR-1) |
| OSS-05 | 🟠 Major | No test suite versioning; corrections break mid-phase learners | Add CHANGELOG.md; tag test suite versions |
| OSS-06 | 🟠 Major | Phase 8 (FastMCP) has shortest shelf life | Add version pins table to Phase 8 doc; pin FastMCP version |
| OSS-07 | 🟠 Major | Foundation docs have no "last-verified" timestamp | Add `<!-- last-verified: YYYY-MM -->` to each foundation doc |
| OSS-08 | 🟠 Major | No issue triage process or issue templates | Add 3 issue templates (bug, content-error, feature) in Sprint 1 |
| OSS-09 | 🟡 Minor | No GitHub Actions CI file in repo structure | Create `.github/workflows/ci.yml` (see CCR-4) |
| OSS-10 | 🟡 Minor | Repo will be public during construction with no status signal | Add Status banner (see CCR-6) |
| OSS-11 | 🟡 Minor | No roadmap for who maintains Phase 8 after MCP spec change | Assign Phase 8 a named maintainer in CONTRIBUTING.md |
| OSS-12 | 🟡 Minor | No `make status` target; contributor cannot see what is done | Add `make status` target (see CCR-4) |

### 4.5 Project Management & Scope (13 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| PM-01 | 🔴 Critical | Estimate arithmetic wrong: 192.5h subtotals ≠ 270h claimed | Recompute all subtotals; set official estimate to 380h ±30% |
| PM-02 | 🔴 Critical | ARCH-24 (TUI tests) under-estimated 3–5× | Update from 4h to 12–20h |
| PM-03 | 🟠 Major | ARCH-27 dependency table wrong (depends on ARCH-18) | Fix dependency: ARCH-27 → ARCH-18, not ARCH-01 |
| PM-04 | 🟠 Major | PED-10 (10 foundation docs) under-estimated 2–3× | Update from 8h to 20–30h |
| PM-05 | 🟠 Major | PED-06 (Common Pitfalls) under-estimated 4–6× | Update from 4h to 18–27h |
| PM-06 | 🟠 Major | Zero hours budgeted for bug propagation in serial chain | Add 5h rework buffer to Sprint 4 (see CCR-1) |
| PM-07 | 🟠 Major | Sprint 4 is 100h — longest sprint, most likely to slip | Split Sprint 4 into two 50h sub-sprints with a checkpoint |
| PM-08 | 🟠 Major | CONTRIBUTING.md listed as "coming soon" — blocks Sprint 1 | Move CONTRIBUTING.md to Sprint 1 (BUG-07) |
| PM-09 | 🟠 Major | Facilitator guide available last; facilitators need it first | Draft facilitator guide outline in Sprint 1 |
| PM-10 | 🟡 Minor | 38 user stories not validated by any actual target user | Identify 2–3 target users; validate top 10 stories before Sprint 3 |
| PM-11 | 🟡 Minor | "Working artifact every phase" promise fails for Phase 1 and 7 | Qualify the promise; add what "working" means per phase |
| PM-12 | 🟡 Minor | Phase 5 and Phase 6 solutions undocumented dual-watcher conflict | Add conflict documentation task to Sprint 4 |
| PM-13 | 🟡 Minor | Repo public during Sprints 1–4 with no status signal | Add Status banner to Sprint 1 README (see CCR-6) |

### 4.6 QA & Test Engineering (15 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| QA-01 | 🔴 Critical | Zero error-path tests across all 9 phases | Add one error-path test per phase (see CCR-9) |
| QA-02 | 🔴 Critical | `indexed_db` fixture chain couples all phases to Phase 2 | Document; add reset; add cross-phase contract tests |
| QA-03 | 🔴 Critical | SENTINEL is a comment, not a pytest marker — invisible to tooling | Add `pytest.ini` marker; add `make test-sentinels` target |
| QA-04 | 🟠 Major | `time.sleep` in timing-sensitive tests causes flakiness | Replace with synchronization primitives (see CCR-5) |
| QA-05 | 🟠 Major | Watcher tests use `.write_text()` not atomic write path | Use `os.replace()` in watcher test writes (see CCR-5) |
| QA-06 | 🟠 Major | `make test-all` always green against solutions — false confidence | Separate `make verify-solutions` from `make test` |
| QA-07 | 🟠 Major | Phase 2 under-tested: misses delete cascade, WAL, FTS5 desync | Add 4 missing test cases to Phase 2 test file |
| QA-08 | 🟠 Major | `test_db_is_expendable` checks only one FTS5 query on one tag | Extend to verify edges, relations table, workspaces, tagless nodes |
| QA-09 | 🟠 Major | `populated_vault` fixture (5 nodes, 2 edges) too sparse | Expand fixture to 30+ nodes for Phase 5 density test; 4-node chain for Phase 3 BFS |
| QA-10 | 🟠 Major | Phase 8 large vault fixture is `scope="function"` — 5–30s per test | Change to `scope="module"`; add 10s performance gate |
| QA-11 | 🟠 Major | Cross-phase contract tests absent | Add tests verifying Phase 2 → Phase 3 → Phase 4 → Phase 5 contracts |
| QA-12 | 🟠 Major | `test_context_for_query` only checks substring, not descriptions | Add assertion: `all(d for d in result["descriptions"])` |
| QA-13 | 🟡 Minor | `sys.modules` cache breaks `make test-all` isolation | Add cache invalidation (see CCR-3) |
| QA-14 | 🟡 Minor | No CI enforcement of `make verify-all` | Add GitHub Actions CI (see CCR-4) |
| QA-15 | 🟡 Minor | Git fixture may touch real remotes | Add no-remote assertion to `git_vault` fixture (SEC-09) |

### 4.7 Educational Theory & Pedagogy (13 findings)

| ID | Severity | Title | Resolution Summary |
|---|---|---|---|
| PED-01 | 🔴 Critical | Phase 1 cognitive overload (12+ concepts simultaneously) | Split Phase 1 → 1A + 1B (see CCR-8) |
| PED-02 | 🟠 Major | No behavioral learning objectives per phase | Replace "Core concept" one-liners with measurable objectives |
| PED-03 | 🟠 Major | Checkpoint exercises are pass/fail gates, not learning activities | Reformat as "explain-then-verify + deliberately break it" |
| PED-04 | 🟠 Major | Vault node exercises are transcription tasks | Replace half with open-ended "find the connection" prompts |
| PED-05 | 🟠 Major | Reflect sections designed for groups; audience is primarily solo | Add Solo/Group track labels; add solo-friendly prompts |
| PED-06 | 🟠 Major | No emotional arc design; Phase 4 and 5 are motivation cliffs | Add advance organizer to Phase 4 and 5 normalizing difficulty |
| PED-07 | 🟠 Major | "Project-based learning" claim is inconsistent with fully-specified path | Rename to "build-to-learn curriculum" or "structured build path" |
| PED-08 | 🟠 Major | No prerequisite validation before learner starts | Add 2-min self-assessment quiz at top of Phase 0 |
| PED-09 | 🟡 Minor | Foundation docs are reference material, not scaffolded learning | Add "Why this matters for Mirin" intro to each foundation doc |
| PED-10 | 🟡 Minor | 10 foundation docs under-estimated at 8h | Update to 20–30h (see CCR-2) |
| PED-11 | 🟡 Minor | Facilitator guide available last; facilitators need to evaluate first | Draft facilitator outline in Sprint 1 (see PM-09) |
| PED-12 | 🟡 Minor | Common Pitfalls under-estimated at 4h | Update to 18–27h (see CCR-2) |
| PED-13 | 🟡 Minor | No spaced repetition or review cycle across phases | Add "concepts revisited" cross-reference at end of each phase |

---

## 5. Implementation Plan Amendments

The following are specific, actionable changes to make to `docs/implementation-plan.md`
before Sprint 1 begins.

### 5.1 Fix the arithmetic

**Current:** "Total estimated effort: ~270 hours"  
**Action:** Recompute all category subtotals. Current sum is ~192.5h. Update the total
to **380 h ±30%** and update all per-category breakdowns to reflect realistic estimates
for the three known under-estimated line items.

### 5.2 Add to Sprint 1 deliverables

The following items must be added to Sprint 1 (they are not currently listed):

- `LICENSE` file (MIT) — 2 min
- `CONTRIBUTING.md` stub (5 bullet points) — 30 min
- `.github/workflows/ci.yml` — 1 h
- 3 GitHub issue templates (bug, content-error, feature) — 30 min
- `make status` target — 1 h
- Status banner in Sprint 1 README — 15 min
- Facilitator guide outline (not full doc) — 2 h

### 5.3 Fix ARCH-27 dependency

**Current:** ARCH-27 (Phase 8 tests) lists dependency as ARCH-01.  
**Fix:** Change dependency to ARCH-18 (Phase 8 solution). The test cannot be written
before the solution exists.

### 5.4 Add error-path acceptance criterion

Add to the acceptance criteria for ARCH-19 through ARCH-27:
> "Each test file must include at least one error-path test covering a failure mode
> specific to this phase."

### 5.5 Fix Phase 8 fixture scope

**Current:** Large vault fixture for Phase 8 tests is `scope="function"`.  
**Fix:** Change to `scope="module"`. Add a performance gate: fixture creation must
complete in under 10 s.

### 5.6 Add SENTINEL as proper pytest marker

**Current:** SENTINEL is a comment string.  
**Fix:** Register `sentinel` as a pytest marker in `pytest.ini`. Add
`make test-sentinels` target that runs only sentinel-marked tests. Document in
CONTRIBUTING.md.

### 5.7 Add Sprint 4 rework buffer

**Current:** Sprint 4 estimate is 100 h.  
**Fix:** Add 5 h rework buffer for bug propagation. Document as "propagation reserve —
used when a bug in Phase N requires patching Phases N+1 through 9." Update Sprint 4
total to 105 h.

### 5.8 Add dual-watcher conflict documentation

Add a task to Sprint 4: document the Phase 5 / Phase 6 dual-watcher conflict. Explain
that two `AkangaApp` instances cannot run on the same vault simultaneously. Add a
guard in `AkangaApp.start_all()` (PID lock file or port check).

### 5.9 Update per-phase learner estimates in README

The README's per-phase estimate table must reflect realistic learner time, not author
time. Phase 5 in particular should show 12–20 h, not 5–7 h.

### 5.10 Add `scripts/sync_forward.py` to Sprint 4

Add `sync_forward.py` as a deliverable in Sprint 4. It should:
- Accept a source file path and a starting phase number.
- Diff the source against the corresponding file in each later phase.
- Print a unified diff for review before applying.
- Apply with `--apply` flag after human confirmation.

---

## 6. Findings That Require Design Decisions

These issues cannot be resolved with a simple code or documentation fix. They require a
deliberate choice from the project owner before implementation proceeds.

### Decision 1: Split Phase 1 into 1A + 1B?

**Trade-off:** Reduces cognitive overload in the hardest phase at the cost of making a
9-phase path into a 10-phase path. All phase numbering in docs, Makefile, and directory
structure would shift.

> **Decision needed:** YES (add Phase 1B, renumber) / NO (add advance organizer and
> reduce scope within Phase 1 without splitting)

### Decision 2: Move solutions to a separate git branch?

**Trade-off:** Eliminates the 9× duplication propagation problem. Solutions can be
maintained in one place and diffed cleanly. Cost: learners cannot browse solutions on
`main`; the `make solution` target must check out a different branch.

> **Decision needed:** YES (separate branch) / NO (keep solutions in `solutions/` dir)

### Decision 3: Add Solo / Group tracks to Reflect sections?

**Trade-off:** Makes the curriculum usable for self-directed learners (primary audience)
without breaking workshop use. Cost: doubles the word count in Reflect sections.

> **Decision needed:** YES (add tracks) / NO (keep single version, optimize for one
> audience)

### Decision 4: Replace transcription vault node tables with open-ended prompts?

**Trade-off:** Significantly improves learning transfer (understanding vs. copying) at
the cost of requiring learners to produce their own vault structure, which cannot be
auto-validated by `make check`.

> **Decision needed:** YES (replace half with open-ended) / NO (keep tables, faster to
> complete)

### Decision 5: Add 2-minute prerequisite self-assessment quiz per phase?

**Trade-off:** Surfaces readiness gaps before the learner encounters them mid-phase.
Adds 2 minutes to the start of each phase. Requires someone to write and maintain 9
quizzes.

> **Decision needed:** YES (add quizzes) / NO (rely on Phase 0 prerequisites section)

---

## 7. Findings Already Addressed

The following issues raised by agents are already handled — at least partially — in the
existing plan or documents. They are listed here to acknowledge agent work and to note
where existing coverage is partial.

| Finding | Where Addressed | Gap |
|---|---|---|
| Path traversal protection | `plan-security-and-deployment.md` S1–S2 | Symlink escape not covered (SEC-02) |
| YAML safe loader | `plan-security-and-deployment.md` S1 | `akanga.yaml` not in scope (SEC-03) |
| FTS5 full-text search | `docs/learning/phase-02-*.md` | FTS5 operator injection not mentioned (SEC-06) |
| Atomic file writes | Architecture section in CLAUDE.md | macOS `on_moved` edge case not addressed (BUG-05) |
| Git auto-commit debounce | `docs/learning/phase-07-*.md` | Double debounce with indexer not addressed (ARCH-07) |
| EventBus thread safety | Architecture section in CLAUDE.md | Startup race before `set_loop()` not addressed (BUG-04) |
| Common Pitfalls sections | PED-06 in plan | Under-estimated 4–6× (PED-12) |
| Observability (`@timed`) | `docs/observability-module.md` | Not wired into any phase test |
| Virtual nodes | Phase docs cover virtual node type | No error-path test for missing `virtual.url` |
| TUI keyboard shortcuts | Phase 5 docs cover keybindings | No test for key with no selected node (QA-01) |

---

*This document was produced by synthesis of 7 adversarial specialist agent outputs.
All findings are traceable to at least one agent perspective. Cross-cutting issues
(CCR-1 through CCR-10) were independently raised by 3 or more agents.*
