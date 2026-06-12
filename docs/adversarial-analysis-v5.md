# Adversarial Analysis [V5] — Code Readability & DRY

> **Date:** 2026-06-12 · **Purpose:** first adversarial round focused on code
> cleanliness (readability + DRY) — prior rounds covered pedagogy, correctness,
> and security · **Lens:** Round 1 for this dimension — *is the code organized
> right, and where has duplication already caused (or primed) drift?*

---

## Scope and Prior Rounds

Analyzed: `scripts/` (5 Python tools + study.sh, ~2.2k lines), `Makefile`
(643 lines), `tests/` (~6.9k lines, 36 files, 10 conftests), the **canonical
sources** of every manifest-governed solution module, `skeletons/`, and
`examples/`. Three parallel analysis agents (test infra / scripts+Makefile /
solutions+skeletons), each with a verification mandate; quantitative claims
below were checked with diffs, greps, and caller censuses, and the two
highest-stakes claims (#7, #8) were independently re-verified.

All 41 findings from rounds 1–4 (D1–D11, E1–E10, V1–V8 plus per-round items)
are treated as resolved. Nothing here retreads them.

**Method note:** the most valuable findings came from asking not "is this
duplicated?" but "*did the copies already diverge?*" — three of the nine
findings are places where one copy got a fix or a policy the other didn't.

---

## 1. The dual-try loader family: 23 copies that look identical but have quietly forked [STRUCTURAL]

### The problem

Discovery undercounted. It's not "~10+ functions" — there are **23 named
dual-try loader functions plus 2 inline dual-try blocks**, ~290 lines total,
spread across 7 conftests and 6 test files:

| Loader | Copies | Locations |
|---|---|---|
| `_load_db` | **6** | `tests/phase_02/conftest.py:20`, `phase_03/conftest.py:20`, `phase_04/conftest.py:74`, `phase_05/conftest.py:23`, `phase_08/conftest.py:15`, `phase_08/test_rag.py:35` |
| `_load_parser` (incl. `_load_module`) | **3** | `phase_00/test_parser.py:37`, `phase_01/test_schema.py:23`, `phase_02/conftest.py:59` |
| `_load_indexer` | 2 | `phase_02/conftest.py:33`, `phase_05/conftest.py:36` |
| `_load_sync_queue` | 2 | `phase_01/conftest.py:26`, `phase_04/conftest.py:87` |
| one-offs (`_load_links`, `_load_graph`, `_load_eventbus`, `_load_watcher`, `_load_sync_worker`, `_load_create_app`, `_load_tui_class`, `_load_git_manager`, `_load_mcp_server`, `_load_rag`) | 10 | conftests + test files |
| inline dual-try | 2 | `phase_07/conftest.py:44-47`, `phase_08/conftest.py:209-212` |

**Diff results.** The 6 `_load_db` copies: 5 byte-identical; `phase_04`'s
differs only in docstring. That part is pure duplication. But the *family*
has already drifted in four behavioral ways:

1. **Exception policy forked.** `phase_02/conftest.py:25` catches
   `ModuleNotFoundError` only; `phase_05/conftest.py:41` catches
   `(ModuleNotFoundError, ImportError)`; `phase_00/test_parser.py:51`,
   `phase_07/test_git.py:36`, `phase_08/test_mcp.py:47` catch bare
   `ImportError`. A learner module that *exists but fails to import* produces
   a raw collection traceback in phase 2 but a swallowed-then-misleading
   "Could not import" `pytest.fail` in phases 0/7/8. Same mistake, different
   diagnosis per phase.
2. **Same name, different return type.** `phase_02._load_indexer` returns the
   *module*; `phase_05._load_indexer` returns the *function*
   `full_scan_and_index`. Naive deduplication breaks one suite.
3. **Guards forked 3 ways on the same module.** `phase_00._load_parser` guards
   `hasattr(parse|parse_node_file)`; `phase_02._load_parser` guards
   `hasattr(Node)`; `phase_01._load_module` loads `parser` with **no guard at
   all** — the only copy that can silently import a wrong top-level `parser`
   package from site-packages.
4. **Search order reversed.** `phase_08/test_mcp.py:38` tries package layout
   first, flat second — opposite of all 22 other sites. Possibly deliberate
   (Phase 8 recommends `akanga_mcp/`), but the rationale lives nowhere.

Also: `phase_08/test_rag.py:35` re-defines `_load_db` even though
`phase_08/conftest.py:15` already has it, *and* the repo already has the
import-from-conftest pattern (`tests/phase_02/test_db.py:7`). That copy is
gratuitous even by the repo's own conventions.

### Why this matters

The drift has **already happened** — this is not hypothetical. The
exception-policy fork means the curriculum's most important failure mode
("learner's file exists but is broken") behaves differently depending on the
phase, and the broad-`ImportError` copies actively mislead: they report "file
missing, check syntax errors" when the real cause is a failing import inside
an existing file (and a `SyntaxError` isn't caught by *any* copy, so that part
of the message is unreachable). When a maintainer next improves one loader's
error message they will fix 1 of 6 `_load_db` copies and the suites silently
diverge further. The cost isn't the ~290 lines, it's that 23 sites each
independently encode a *diagnostic policy* that should be a single deliberate
decision.

### What this means

Create **`tests/_helpers.py`** (the `tests/` tree is a real package — every
directory has `__init__.py`, and test files already import
`tests.phase_NN.conftest`, so `from tests._helpers import load_attr` works
identically in both execution modes; it contains no fixtures, so pytest
collection, conftest scoping, and the per-phase `make verify` subprocess loop
in `Makefile:348-368` are untouched):

```python
def load_attr(*candidates: tuple[str, str | None], guard=None, hint: str = ""):
    """Try (module, attr) candidates in order; pytest.fail with `hint` +
    the captured original exception if all fail."""
```

Each phase keeps thin named wrappers so test-file call sites don't change —
migration is mechanical, ~25 sites, one suite at a time, validated by
`make test-all`. The shared helper forces the three forked decisions
(exception breadth, guard, search order) to be made once; capture and
*include the original import error text* in the `pytest.fail` message so
broken-but-present modules stop being reported as missing.

**What NOT to do:** don't hoist loaders into the root `tests/conftest.py`
(it's the AKANGA_SRC bootstrap — keep it boring), and don't byte-unify
behavior blindly: the phase-05 return-a-function variant and the phase-08
package-first order may be deliberate; the fix is to make each divergence an
explicit `load_attr` argument with a comment, not to erase it.

---

## 2. The `_setup_akanga_src` fixture's docstring is false, and the module-level loader calls it fails to cover split learners into two different failure universes [SERIOUS]

### The problem

Nine byte-identical copies of this fixture (differing only in the phase int)
all claim:

> `"""Insert AKANGA_SRC into sys.path before any test module is imported."""`
> — e.g. `tests/phase_02/conftest.py:10-13`

That claim is wrong. Pytest imports test modules during **collection**, which
happens before any fixture — including session-scoped autouse ones — executes.
The thing that actually inserts `AKANGA_SRC` before module import is
`pytest_configure` in `tests/conftest.py:15-22`. The proof is in the repo
itself: `tests/phase_02/test_db.py:9` (`GraphDatabase = _load_db()`),
`test_indexer.py:10-11`, `test_links.py:6-8`, `tests/phase_03/test_graph.py:15`,
and `tests/phase_04/test_watcher.py:23-24` all call loaders at **module top
level** — collection time — and only work because of `pytest_configure`. The
fixture's real (undocumented) jobs are the fail-fast diagnostics and the
`sys.modules` purge in `_resolve_akanga_src` (`tests/conftest.py:25-43`).

This creates a verified behavioral split:

- **Phases 02/03/04** (module-level loads): run with `AKANGA_SRC` unset →
  `pytest_configure` no-ops → module-level `_load_db()` hits `pytest.fail`
  **during collection** → exit code 2. The carefully crafted
  `"AKANGA_SRC is not set! Run: AKANGA_SRC=./src make test PHASE=2"` message
  in `tests/conftest.py:28-32` **never displays**. The Makefile
  (`Makefile:282-287`) then calls this "an infrastructure problem, not a test
  failure" and records nothing in `.akanga-progress`.
- **Phases 00/01/05/06/07/08** (loads inside fixtures/tests): same mistake →
  fixture runs first → the good AKANGA_SRC message displays → exit 1 →
  recorded as a "red" attempt with the "work the ladder" hints.

Secondary hazard: in single-session runs (`make test-mine`,
`Makefile:324-326`, all 9 suites in one process), each phase's session fixture
purges every `"akanga"` entry from `sys.modules` (`tests/conftest.py:37-39`),
but module-level bindings captured at collection time survive the purge. After
the first purge, fixture-loaded classes and module-level classes are
*different class objects* for the same source file — a latent
`isinstance`/identity trap that only manifests in the one invocation mode
nobody CI-tests.

### Why this matters

The curriculum's core UX promise is "the failing test's message is a hint by
design" (`Makefile:277`). For the single most common beginner mistake —
running pytest without `AKANGA_SRC`, or with a broken module — three phases
bypass the entire curated-diagnostics machinery and get classified by the
Makefile as a non-attempt. And the 9 copied docstrings actively teach the
wrong mental model to the next contributor, who will reasonably assume
module-level imports are safe *because the fixture says it runs first*. That
false belief is plausibly how phases 02–04 got their module-level loads in
the first place — the drift is self-reinforcing.

### What this means

Two small, independent fixes:

1. **Eliminate the module-level loader calls** in
   `tests/phase_02/test_{db,indexer,links}.py`, `phase_03/test_graph.py`,
   `phase_04/test_watcher.py` — move each `X = _load_x()` into a
   module-scoped fixture. This routes every import failure through the
   post-fixture path: consistent exit code 1, the AKANGA_SRC message fires,
   progress is recorded. ~5 files, mechanical; verify with `make test-all`
   plus one deliberate `AKANGA_SRC=/nonexistent pytest tests/phase_02/`
   smoke check of the message.
2. **Replace the 9 fixture copies with one** root-conftest autouse session
   fixture; derive the phase from the failing test's path (or drop it —
   `make test PHASE=N` already echoes it). At minimum, fix the docstring to
   state what the fixture actually does: *fail fast with guidance when
   AKANGA_SRC is unset/missing, and purge cached akanga modules; sys.path
   insertion happens earlier, in pytest_configure*.

**What NOT to do:** don't delete the `sys.modules` purge "because
pytest_configure already handles paths" — the purge is what makes
back-to-back runs against different `AKANGA_SRC` values inside one
interpreter safe; and don't move the fail-fast into `pytest_configure` as a
hard error, because `make test-solution` and `verify` always set
`AKANGA_SRC`, and a configure-time crash would change exit-code semantics the
Makefile's triage messages depend on.

---

## 3. Same fixture name, contradictory contract: `tmp_vault` (4 semantics), `tmp_db` (3 types), and a fixture trio that teaches two incompatible `upsert_node` conventions [MODERATE]

### The problem

- **`tmp_vault` — 6 definitions, 4 distinct meanings.** `phase_00/conftest.py:17`
  and `phase_01/conftest.py:18` (byte-identical): `tmp_path` containing
  `akanga.yaml`. `phase_02/conftest.py:75`: writes `akanga.yaml` into
  `tmp_path` but returns the `tmp_path/"vault"` **subdirectory** — the config
  is *outside* the returned dir. `phase_04/conftest.py:107` and
  `phase_06/conftest.py:41`: bare `tmp_path`, no config.
  `phase_05/conftest.py:71`: `tmp_path` pre-populated with three `.md` nodes.
- **`tmp_db` — 3 definitions, 3 unrelated types.** `phase_01/conftest.py:43`:
  an open `sqlite3.Connection` with a `sync_queue` table.
  `phase_02/conftest.py:85`: a **string path to a file that doesn't exist
  yet**. `phase_05/conftest.py:91`: an open, fully-indexed `GraphDatabase`.
  Reading `def test_x(tmp_db):` tells you nothing without knowing the phase.
- **The populated-DB trio contradicts itself about the API it exercises.**
  `phase_02/conftest.py:107-138` (`populated_db`) upserts **`Node` objects**
  and calls `upsert_edge` positionally, annotated `# upsert_edge is
  positional: (source_id, target_id, relation, relation_id)` (line 136; same
  comment at `phase_08/conftest.py:176-177`). `phase_03/conftest.py:107-115`
  (`populated_graph_db`) upserts **plain dicts** and calls
  `db.upsert_edge(id_a, id_b, relation="links_to")` — keyword, no
  `relation_id`. The actual signature
  (`solutions/phase_02/src/akanga_core/db.py:306`) is
  `upsert_edge(self, source_id, target_id=None, relation=None,
  relation_id=None)` — so the "is positional" comment is simply false as a
  contract statement, and phase_03's own usage disproves it.

Plus one clean byte-identical duplicate: `_write_node` at
`phase_05/conftest.py:53` ≡ `phase_06/conftest.py:23`.

### Why this matters

In this repo, **tests are the spec** — learners are told to read failing
tests as hints. A learner who implements `upsert_node` to accept `Node`
objects (exactly what phase 2's fixture shows) passes Phase 2, then hits
Phase 3 failures whose tracebacks point into graph traversal code, when the
actual gap is that `upsert_node` must *also* accept dicts — a requirement
stated nowhere in a single file, only implied by the union of two fixtures in
two phases. The misleading "positional" comment compounds it: a learner who
makes the parameters positional-only per the comment passes phase 2 and
breaks on phase 3's keyword call. The fixture-name collisions are safe at
runtime (conftest scoping keeps them phase-local) but hostile to every human
reading tests across phases — the curriculum's primary intended reading
pattern.

### What this means

Three cheap, targeted edits — no shared-fixture infrastructure needed:

1. **Rename by contract**, keeping definitions phase-local:
   `phase_02.tmp_db` → `db_path`, `phase_05.tmp_db` → `indexed_db`,
   `phase_01.tmp_db` → `sync_queue_conn`; `phase_02.tmp_vault` → `vault_dir`
   (documenting that `akanga.yaml` sits in its *parent*),
   `phase_05.tmp_vault` → `vault_with_nodes`. Mechanical sed within each
   phase dir; zero cross-mode risk.
2. **Fix the false comment** at `phase_02/conftest.py:136` and
   `phase_08/conftest.py:176-177`, and add one sentence to `populated_db`'s
   docstring: *"upsert_node accepts a Node object or a plain dict — phase 3
   fixtures exercise the dict form."* That single line converts an implicit
   cross-phase contract into an explicit one at the exact place a stuck
   learner will look.
3. Move `_write_node` into the shared `tests/_helpers.py` from critique 1
   (it imports no learner code, so it's mode-safe).

**What NOT to do:** do not hoist `tmp_vault`/`tmp_db` into the root conftest
to "deduplicate" them — the divergence is *semantic*, phase conftest scoping
is the correct isolation mechanism, and a root-level fixture would be
silently shadowed by any remaining phase-local copy, which is exactly the
failure mode this critique is about.

---

## 4. The "marker file" convention is defined four different ways, and nothing pins them together [SERIOUS]

### The problem

The convention "this skeleton file is a placeholder, not code" is
load-bearing for three tools, and each carries its own private definition:

1. `scripts/sync_forward.py:67-78` — `MARKER_SNIPPETS = ("intentionally left
   as a reference marker", "Copy your Phase")` + `is_marker_file()`,
   consulted at 5 call sites to decide what the **drift gate** compares and
   what `--apply` may overwrite.
2. `scripts/skeleton_merge.py:42-59` — a byte-identical copy of both the
   tuple and the function, with only a comment (`# Same marker convention as
   sync_forward.py`) as the coupling mechanism.
3. `scripts/check_doc_contracts.py:459-460` — a *semantically different*
   third definition: `if not tree.body: continue  # comment-only
   reference-marker file`. Check 5 additionally encodes "phase is all
   markers" as `skel_map` emptiness.
4. The ~14 actual marker files themselves
   (`grep -rl "intentionally left as a reference marker" skeletons/` → 14
   hits) — the prose is the de-facto authority the snippet tuples
   substring-match against.

Verified: the two Python copies are currently identical, and
`git log --follow` shows both files were only touched together in remediation
commits — no divergence *yet*. Also verified: **zero tests cover anything in
scripts/**, so no test would fail if the copies drifted. The repo's own drift
gate (`sync_forward --check-all`, CI) governs `solutions/` modules only —
`scripts/`-internal duplication is the one multi-copy class the repo's
elaborate convergence machinery does not see.

Secondary fragility: `is_marker_file()` is a substring match against the
*whole file*. Any legitimate solution file containing the phrase "Copy your
Phase" in a comment or docstring is silently exempted from the byte-identity
drift gate (`sync_forward.py:302/319` `continue` with no output).

### Why this matters

The marker prose is learner-facing text — exactly the kind of thing a
tone/wording pass edits. Reword the marker files to "Bring forward your Phase
02 parser…" and both snippet tuples silently stop matching, while
check_doc_contracts' AST-empty heuristic keeps working: **the three gates now
disagree about what a marker is, and nothing reports it.** Consequences:
`make sync-forward BASE=skeletons … --apply` overwrites placeholder markers
with full prior-phase implementations (solution leakage into the learner's
starting tree — `skeleton_check.py` catches leaked *function bodies* in CI,
but leaked module constants and the destroyed pedagogical pointer text get
through); `--check-all --base skeletons` reports every marker as drift (false
positives that train maintainers to distrust the gate). Conversely, a
maintainer adding a third snippet for a new marker style will plausibly
update `sync_forward.py` and miss `skeleton_merge.py` — the comment is the
only breadcrumb, and no CI signal exists.

### What this means

Create `scripts/_common.py` holding `MARKER_SNIPPETS` + `is_marker_file()`
(see critique 6 for what else belongs there). Both scripts are invoked as
`python scripts/x.py`, so a plain `import _common` works with no packaging
changes — the "stdlib only, runnable standalone" property is preserved. Two
further moves:

- **Pin the convention with a test**: a 20-line `tests/test_scripts_markers.py`
  (or CI step) asserting every comment-only file under `skeletons/*/src/`
  that mentions "solution here" satisfies `is_marker_file()`, and that
  `is_marker_file` ⇒ `ast.parse(...).body == []`. That single test welds all
  four definitions together.
- In `check_doc_contracts.py:459`, either call `_common.is_marker_file()` or
  extend the comment to state *why* the AST-empty heuristic is deliberately
  different (it also skips empty `__init__.py`, which the snippet match does
  not). Right now the difference reads as accident, not intent.
- Cheap hardening: anchor the snippet match to the first ~3 lines of content,
  matching how markers are actually written, to kill the whole-file substring
  false positive.

Migration cost: ~1 hour. **What NOT to do:** don't try to make the
manifest/drift gate govern `scripts/` files — `sync_manifest.toml` models
*phase copies*, and bending it to internal duplication would muddy a clean
model. A shared module + one pinning test is the right size.

---

## 5. The phase roster (0–8) is hand-enumerated in ~9 places, and the loops' existence-guards turn a missed update into silently green verification [SERIOUS]

### The problem

The set of phases is data, but it is hard-coded as literals in at least nine
locations:

- `Makefile:303, 373, 407, 518` — four identical `for n in 0 1 2 3 4 5 6 7 8`
  loops (test-all, verify-all, examples-all, status)
- `Makefile:170` — docs-all's variant list `00 01a 01b 02 … 08`
- `Makefile:33` — `TO ?= 8`; `Makefile:575` — resume's
  `if [ "$$NEXT" -gt 8 ]`
- `scripts/sync_forward.py:535` — `--to … default=8`
- `.github/workflows/ci.yml:159` — `matrix: phase: [0, 1, 2, 3, 4, 5, 6, 7, 8]`

Inside each Makefile loop the body re-derives
`PHASE_PAD=$$(printf "%02d" $$n)` and the `solutions/phase_NN/src` +
`tests/phase_NN` paths — 7 copies of the padding idiom. Critically, three of
the four loops guard with `if [ -d … ]` and **silently skip** non-existent
directories (`test-phase-range:334`, `verify-all:376` `continue`,
`examples-all:410`). Only `test-all` grew a `TESTED=0` floor-guard (line 313)
in round 4 — the same defect class survives, unfixed, in its three siblings.
Related dual-maintenance: `ci.yml:75-77` and `176-197` *re-implement*
`make status` and `make verify` inline rather than calling them, so the
roster and the loop logic both exist in two languages.

### Why this matters

This repo's headline claim is the "9/9 solution matrix" and cumulative
verification. Add a phase 9: you must edit nine call sites in three files.
Miss any Makefile loop and the failure is **silent and green** — `verify-all`
never visits phase 9 and prints "full verification passed"; `make resume`
tells a learner who finished phase 8 "you have finished the build" even
though phase 9 exists; `sync-forward` stops propagating fixes at phase 8, so
phase 9's copies drift *outside* the manifest gate's reach (propagate mode
honors `--to 8` even when the manifest's `applies_to` lists 9). The repo
already paid for this exact defect class once — adversarial-analysis-v4 #1
was "loop printed green over a skipped body" — and the fix was applied to one
loop instance instead of the pattern.

### What this means

Single source of truth at the top of the Makefile:

```make
MAX_PHASE := 8
PHASES    := $(shell seq 0 $(MAX_PHASE))
```

Then `for n in $(PHASES)` in all four loops, `TO ?= $(MAX_PHASE)`,
`-gt $(MAX_PHASE)` in resume, and a one-line CI consistency check that fails
if `ci.yml`'s matrix disagrees — cheaper and more honest than generating the
matrix dynamically. Give `verify-all`/`examples-all`/`test-phase-range` the
same `TESTED=0` floor-guard `test-all` already has (this is the round-4 fix
finished). `sync_forward.py --to` can stay defaulted to `8` but should be
cross-checked by the same CI grep, or simply default to `max(applies_to)`
from the manifest it already loads.

Migration cost: ~30 minutes, zero behavior change today. **What NOT to do:**
don't macro-ize the loop *bodies* into a `define`/`call` template — the four
loops do genuinely different work (record progress, hint ladder, cumulative
inner loop) and Make macro syntax would make the learner-facing recipes
unreadable; the duplication worth killing is the roster and the guards, not
the prose. Likewise leave docs-all's `01a 01b` list alone — it is
roster-shaped but encodes the doc-file split, a real difference.

---

## 6. scripts/ has no shared core: phase normalization exists 5×, repo-root 4×, self/cls-stripping 3× in one file, and `make help` requires registering every target twice [MODERATE]

### The problem

- **Phase normalization / 1A-1B split handling**, five independent
  implementations: `Makefile:29-30` (sed strip + printf pad),
  `Makefile:155-162` (docs-phase re-does it in a shell `case`),
  `study.sh:53-63` (bash regex + `tr`), `validate_vault.py:130-136`
  (`normalize_phase`), `check_doc_contracts.py:215-218` (`doc_phase_dir`).
  The "Phase 1 is split into 1A and 1B — opening 1A" user notice itself is
  copy-pasted verbatim (`Makefile:161`, `study.sh:61`).
- **Repo root**, four computations under three names: `sync_forward.py:55`
  (`REPO_ROOT`), `check_doc_contracts.py:62` (`ROOT`),
  `validate_vault.py:49-51` and *again* at 141-144 (anonymous inline).
- **Within one file**: `check_doc_contracts.py` strips `self`/`cls` three
  times (lines 198, 264, 465) and walks "find a `## Heading` section, stop at
  next `##`" three times, with `validate_vault.py:94-104` being a fourth copy
  of the same section-walker pattern.
- **AST harvesting across 3 scripts** was diffed and is **not** duplication:
  body-only + constants (merge correctness), `ast.walk` + params/defaults
  (contract checking), NotImplementedError scan (leakage detection) hold
  different invariants on purpose. Do not unify.
- **Makefile help**: 12 near-identical `grep -E '^(…)' | awk -F'##'` chains
  (lines 95-141). Every new target must be added in two places — its `##`
  comment *and* one of the 12 hand-maintained name alternations — or it
  silently vanishes from `make help`. All 36 current targets are correctly
  registered today, but the mechanism only holds by vigilance, and
  check_doc_contracts' MISSING-MAKE-TARGET check validates existence, not
  help visibility.

On the flagged long functions, all four were read in full:
`validate_vault.validate_vault` (189L), `propagate` (136L), and `merge_file`
(98L) are **fine** — single linear passes whose `── N. ──` section banners
mirror their docstrings' numbered check lists. The one genuine strain is
`check_doc_contracts.run_checks` (522-697): check 5 lives inside check 1's
miss-branch four indent levels deep, and five parallel per-phase dicts thread
state to the post-loop 4b pass. Worth extracting `check_signatures(doc, …)`
and `check_deliverables(doc, …)`, nothing more.

### Why this matters

The split-phase convention is the live risk: it is the repo's most unusual
rule and it lives in five hand-rolled parsers in three languages. The
curriculum has already split one phase; split another (say 4A/4B) and each
parser needs a compatible update — `validate_vault` hard-codes
`["1a", "1b"] if key == "1"` (line 344), `doc_phase_dir` happens to
generalize, the Makefile `case` and study.sh regex generalize, the notice
strings don't. Miss one and `make docs-phase PHASE=4` opens 4A while
`make vault-check PHASE=4` errors "no usable node manifest" — the tooling
disagrees about what a phase identifier means, and the learner is the
integration test. The repo-root and self/cls copies are lower-stakes but the
same shape: a fix applied where the bug was noticed, not where the logic
lives.

### What this means

`scripts/_common.py` (~60 lines, stdlib-only, same directory so
`import _common` just works) with: `REPO_ROOT`, `normalize_phase()` (moved
from validate_vault, including the 1→[1a,1b] expansion table),
`MARKER_SNIPPETS`/`is_marker_file()` (critique 4), and
`iter_md_section(lines, heading_re)`. Import it from the four Python scripts.
Leave `study.sh` and the Makefile's shell fragments alone — crossing the
language boundary to deduplicate two ~8-line bash blocks isn't worth a
`python -c` subprocess per invocation; instead add a one-line pointer comment
in each ("convention also implemented in scripts/_common.py:normalize_phase —
keep in step"). For `make help`, move grouping into the annotation —
`target: ## @study Open tmux study session…` — and replace the 12 chains with
one awk program that buckets by `@group`; new targets then self-register.
Migration cost: ~2-3 hours total.

**What NOT to do:** don't unify the three AST harvesters (semantics differ by
design); don't extract `skeleton_check.py`'s logic into _common — at 84 lines
it is the one script that is already the right size; and don't turn
_common.py into a kitchen-sink "utils" — cap it at the four named
conventions, each of which provably has ≥3 call sites today.

---

## 7. The edge-API story contradicts itself across db.py, server.py, and the skeleton — two db methods are dead code whose docstrings claim live callers [SERIOUS]

### The problem

`solutions/phase_02/src/akanga_core/db.py` (canonical source for db.py
everywhere) ships two methods that exist, per their own docstrings,
specifically so the API layer never hand-writes SQL:

- `db.py:346-355` — `delete_edge`: *"Exists so the API layer never reaches
  into `db.conn` with hand-written SQL (exemplar honesty): a route handler
  calls this and maps False to a 404."*
- `db.py:371-384` — `get_edges_touching`: *"the consumer is the API layer's
  `/nodes/{id}/edges` route, which previously hand-wrote this exact SQL
  against `db.conn` — the query belongs here, behind the lock, not in a route
  handler."*

Both claims are false. The canonical Phase 6 server does exactly what these
docstrings say it doesn't:

- `solutions/phase_06/src/akanga_core/server.py:334-344` — the
  `/nodes/{node_id}/edges` route hand-writes
  `SELECT * FROM edges WHERE source_id = ? OR target_id = ?` under
  `with db._lock:` against `db.conn` — byte-for-byte the SQL inside
  `get_edges_touching` (re-verified: identical string at `server.py:341` and
  `db.py:381`).
- `server.py:392-402` — the `DELETE /edges/{edge_id}` route hand-writes a
  SELECT + DELETE under `with db._lock, db.conn:` instead of calling
  `db.delete_edge` — the precise workflow `delete_edge`'s docstring describes
  as its reason to exist.

Caller census (grep across `solutions/`, `tests/`, `skeletons/`): **zero call
sites** for either method. Both are dead code in every tree.

The skeleton then adds a third and fourth name for the same concepts.
`skeletons/phase_06/src/akanga_core/server.py:277-291` tells learners to
write `delete_edges_for_node` ("GraphDatabase does not have a
delete_edges_for_node method by default. Either add one to your db.py … Or
execute the SQL inline here directly: `with get_db()._lock, get_db().conn:`
…"), and `:311-321` tells them to write `get_edges_for_node` — whose
suggested body is identical to the already-existing `get_edges_touching`.
The skeleton for `resolve_wikilink` (`skeletons/phase_02/src/akanga_core/links.py:52`)
likewise instructs `Inside 'with db._lock:', execute: …`, and the solution
`links.py:44-47` does it. So the curriculum simultaneously (a) documents a
no-private-access rule, (b) ships unused methods enforcing it, (c) violates
it in the canonical server, and (d) explicitly teaches learners to reach into
`_lock` as the recommended pattern.

### Why this matters

This is a learning repo: the stated workflow is "go green, then diff your
code against the solution." A learner who diffs hits four competing answers
to "where does edge SQL live?" — `get_edges_touching` (solution db, unused),
`get_edges_for_node` (skeleton suggestion), inline `db._lock` SQL (solution
server), `delete_edges_for_node` (skeleton, nonexistent anywhere). The db.py
docstrings actively lie about the architecture ("a route handler calls
this"), which is worse than no docstring — learners trust prose in a
reference implementation. For maintainers, the drift is mechanical: the
canonical-source scheme freezes db.py in phase_02 and server.py in phase_06,
and the CI byte-identical gate only catches copy drift, not **cross-module
contract drift** — db.py was evidently refactored ("previously hand-wrote
this exact SQL") without the server ever being updated to call it. Any future
fix to edge deletion lands in `delete_edge` and silently misses the server's
hand-rolled copy — the exact one-copy-got-the-fix failure mode.

### What this means

Make the docstrings true. In `solutions/phase_06/src/akanga_core/server.py`,
replace the `get_node_edges` body with `return db.get_edges_touching(node_id)`
and the `delete_edge` route body with
`if not db.delete_edge(edge_id): raise HTTPException(404, ...)`. Update
`skeletons/phase_06/server.py` HOW steps to point at the two existing db
methods (one name each) instead of inventing `*_for_node` variants, and drop
the "execute the SQL inline" option. Cost: server.py is canonical in
phase_06 → `make sync-forward` to phases 7-8 plus the skeleton edit, then
`make verify PHASE=8` cumulative; the change is behavior-preserving so test
risk is low. **What NOT to do:** don't delete
`get_edges_touching`/`delete_edge` to "resolve" the dead code — the methods
embody the right boundary; the callers are what's wrong. Also don't try to
hide `db._lock` behind a public lock property as part of this —
`links.resolve_wikilink` is same-package internal use and a bigger refactor
than the finding warrants.

---

## 8. The fence-stripping fix exists in parser.py but not in its near-twin in links.py — fenced `[[Title]]` examples become real DB edges [SERIOUS]

### The problem

Two modules in the same canonical phase_02 tree each parse `[[...]]` syntax
with their own regex:

- `parser.py:37-40` — `_INLINE_EDGE_RE` plus `_CODE_FENCE_RE = r"```.*?```"`,
  with the comment: *"Fenced code blocks are stripped before edge extraction
  so that example syntax inside ``` fences is never mistaken for a real
  edge."* `extract_inline_edges` (`parser.py:173`) applies the strip.
- `links.py:22-32` — `_WIKILINK_RE = r"\[\[([^\]|]+)(?:\|[^\]]+)?\]\]"`,
  **no fence stripping at all** (re-verified: zero fence references in
  links.py).

The indexer feeds raw body text to the unfixed copy: `indexer.py:183` calls
`extract_wikilinks(parsed.content or "")` and turns every hit into a
persisted `relation="wikilink"` edge (`indexer.py:184-186`). Net behavior:
write a note containing a fenced code block with `[[Flow State | supports]]`
and the typed-edge path correctly ignores it (fence stripped), while the
wikilink path **matches the same characters** (its regex's optional
`(?:\|...)?` group accepts the piped form), resolves "Flow State", and writes
a real edge into the DB. The system's own stated invariant — parser.py's
"never mistaken for a real edge", links.py's "Every wikilink becomes a
directed edge in the graph" — is broken by the divergence between the twins.
Test coverage confirms the asymmetry: `tests/phase_01/test_schema.py:101`
pins fence-ignoring for inline edges; `tests/phase_02/test_links.py` has no
fence test at all, and the skeleton `extract_wikilinks` HOW
(`skeletons/phase_02/links.py:17-28`) never mentions fences, so learners
reproduce the gap faithfully.

### Why this matters

This is the textbook DRY failure the lens hunts for: two near-identical
parsing blocks, one received the fence fix, the other didn't, and the unfixed
one is the only one wired into the indexer's edge derivation. The damage is
silent wrong data in the artifact the whole curriculum revolves around —
phantom edges from code examples pollute the Phase 3 ego graph, Phase 5 TUI
graph views, and the Phase 8 RAG triples handed to an LLM. And the audience
guarantees the trigger: these are notes written by programmers learning
systems concepts; fenced code containing wikilink syntax is the *expected*
note content (the repo's own docs are full of fenced `[[...]]` examples). A
learner who reads parser.py's fence comment will reasonably — and wrongly —
believe the whole pipeline ignores fenced syntax.

### What this means

Hoist the shared concern, minimally. Either (a) move `_CODE_FENCE_RE` to
links.py (or a tiny shared spot) and have `extract_wikilinks` strip fences
before matching — one-line body change — or (b) have the indexer strip
fences once before calling both extractors. Option (a) is better pedagogy:
the function's contract becomes self-contained. Add one test to
`tests/phase_02/test_links.py` pinning fenced-wikilink exclusion, and one HOW
line to the skeleton. Cost: links.py is canonical in phase_02 → sync-forward
to phases 3-8, `make verify` cumulative. Risk: any existing test that feeds
fenced wikilinks and expects edges would break — grep says none exists.
**What NOT to do:** don't unify `_WIKILINK_RE` and `_INLINE_EDGE_RE` into one
shared regex module — the two functions deliberately live in different
modules with different jobs, and the explicit per-module regex with its
breakdown comment is good teaching; only the *fence-stripping behavior* must
converge, not the regexes.

---

## 9. Ten `Any`-typed public DB APIs create a phantom second "Node" type — the skeleton needs nine defensive footnotes to compensate [MODERATE]

### The problem

`models.py:20-36` defines the dataclass the module docstring calls "the ONE
Node dataclass … so the parser, indexer, DB layer, TUI, and MCP server all
share one contract." But the DB layer doesn't return it. `db.py:83-91`
hydrates rows into `types.SimpleNamespace`, and every public read API erases
the type — `db.py:140` (`upsert_node(self, node: Any)`), `:244`, `:252`
(`-> Any | None`), `:267`, `:275`, `:386`, `:397`, `:408`, `:427`
(`-> list[Any]`), `:446` (`-> tuple[Any, str, str]`): ten `Any`-typed public
signatures in one 457-line module that is otherwise rigorously modern-typed
(zero `Optional[`/`List[` anywhere in solutions — verified by grep).
Downstream, the erasure forces hedges: `graph.py:73-74` types
`EgoGraph.root: object # Node (typed loosely to avoid import cycle)` — a
doubly misleading comment, since the runtime object is a SimpleNamespace,
not `models.Node`, and the same file already uses the `TYPE_CHECKING` import
idiom (`graph.py:23-26`) that would solve a cycle. `sync_worker.py:35`
leaves its `db` parameter unannotated entirely, while `sync_queue.py:28` uses
the same name `db` for a raw `sqlite3.Connection` — the only place in the
package where `db` is not a `GraphDatabase`.

The measurable learner cost shows up in the skeletons:
`skeletons/phase_06/src/akanga_core/server.py` carries **nine** separate
warning notes (lines 156, 189, 212, 232, 241, 254, 272, 340, 363) of the
form "db.get_node() returns a SimpleNamespace (attribute access), NOT a
dict", plus `skeletons/phase_08/.../server.py:119`. Nine footnotes defending
against confusion is the type system's job being done by hand, per call site.

### Why this matters

The DB-node and `models.Node` differ in shape (`_NODE_FIELDS` has no
`content`/`frontmatter`; `Node` has both, defaulted) — so conflating them is
a real runtime hazard: `db_node.content` raises `AttributeError` while
`parsed_node.content` works, and the docs say "the ONE Node dataclass" while
learners watch two structurally different node objects flow through the same
variable names. For a reference implementation whose explicit value is
teaching contracts, `-> Any` on the ten most-called methods means no IDE
completion on `node.title`, no mypy safety in learner code built against the
solution, and the misleading `# Node` comment in graph.py teaches the wrong
mental model. The Phase 6 skeleton's nine footnotes are evidence the authors
already know readers trip here — they patched the symptom in prose instead of
the seam in types.

### What this means

Cheap, type-only fix: add a small frozen `@dataclass NodeRecord` (the six
`_NODE_FIELDS`) or a `Protocol` to db.py (or models.py), have
`_row_to_node`/`_row_to_edge_tuple` return it, and replace the ten `Any`
annotations; fix `graph.py:73-74` to `root: NodeRecord` via `TYPE_CHECKING`
(or at least correct the comment), and annotate
`SyncWorker.drain(db: GraphDatabase | sqlite3.Connection, ...)`. Runtime
behavior can stay attribute-compatible, so test risk is near zero — but cost
is real: db.py + models.py are phase_02 canonical and graph.py is phase_03
canonical, so the change re-propagates via `make sync-forward` to every later
phase and must pass the full cumulative `make verify` chain; the skeleton
footnotes should then be trimmed to one note at first use. **What NOT to
do:** don't return `models.Node` from the DB (a `Node` with silently empty
`content` is a worse lie than an honest six-field record). And don't
introduce an ORM or generic row-mapper layer — one named dataclass is the
entire fix this teaching codebase needs.

---

## What This Analysis Does NOT Challenge

- **Cross-phase byte-identical solution copies** — manifest-governed,
  CI-enforced, resolved in v3 #7 / v4 #3.
- **Skeleton per-phase stub duplication and SENTINEL/WHAT-WHY-HOW format** —
  pedagogical progression by design.
- **TUI divergence** (phases 5–8 app.py variants) and per-phase
  `__init__.py` rosters — explicitly excluded in the manifest with reasons.
- **Long-but-sectioned functions**: `propagate` (136L),
  `validate_vault` (189L), `merge_file` (98L), and `build_ego_graph` (83L)
  were each read in full and judged readable — section banners mirror
  docstring check-lists. Cleared.
- **The three AST harvesters** in scripts/ — diffed; they hold different
  invariants on purpose. Cleared.
- **Type-hint modernity** — uniformly `list[str]` / `X | None` style, zero
  legacy `Optional[`/`List[`. Cleared (except the `Any` seam in #9).
- **Examples** — all nine standalone (zero `akanga_core` imports),
  consistently named. Cleared.
- **Makefile verbosity in learner-facing recipes** (hint ladder, resume,
  peek) — deliberate UX, not bloat.

### Consolidated "what's right"

`tests/conftest.py` is exemplary (44 lines, single-purpose, best
learner-facing error text in the tree); `phase_04/conftest.py:16-28`
`_wait_until` is the helper pattern the loaders should copy; exit-code
discipline across scripts is consistent and documented; every script opens
with a WHAT/WHY/HOW docstring citing the adversarial finding it answers;
`study.sh` is exemplary shell; eventbus.py/watcher.py lock-discipline and
monotonic-clock narration is genuinely excellent systems teaching; `db.py`
factors row hydration once and justifies its twin FTS delete blocks with
real, different reasons.

---

## Risk Matrix

| # | Risk | Severity | Requires |
|---|---|---|---|
| 1 | Dual-try loader family: 23 forked copies, 4 behavioral divergences already live | STRUCTURAL | `tests/_helpers.py` + mechanical migration (~25 sites) |
| 2 | False fixture docstring; phases 02–04 bypass AKANGA_SRC diagnostics at collection time | SERIOUS | Move 5 module-level loads into fixtures; 1 shared root fixture |
| 3 | Fixture name collisions teach contradictory `upsert_node`/`upsert_edge` contracts | MODERATE | Renames + 2 comment/docstring fixes |
| 4 | Marker convention defined 4 ways; zero tests on scripts/; silent gate disagreement possible | SERIOUS | `scripts/_common.py` + 1 pinning test |
| 5 | Phase roster hand-enumerated ×9; 3 of 4 loops still silently green on missing dirs (v4 #1 pattern unfinished) | SERIOUS | `MAX_PHASE`/`PHASES` vars + floor-guards + CI consistency grep |
| 6 | No scripts/ shared core: phase-split convention in 5 parsers / 3 languages; `make help` double-registration | MODERATE | Extend `scripts/_common.py`; `@group` help annotation |
| 7 | Dead `delete_edge`/`get_edges_touching` with false docstrings; server hand-writes their SQL; skeleton invents 2 more names | SERIOUS | 2 route-body swaps in canonical server + skeleton HOW edits + sync-forward |
| 8 | links.py missing the fence-strip parser.py has → fenced `[[...]]` examples become persisted edges, polluting graph/TUI/RAG | SERIOUS | 1-line links.py fix + 1 test + skeleton HOW line + sync-forward |
| 9 | Ten `Any`-typed DB APIs; phantom second Node type; 9 skeleton footnotes patch the symptom | MODERATE | `NodeRecord` dataclass + annotation pass + sync-forward + verify |

## Suggested Priority for Resolution

**Tier 1 — latent defects wearing a DRY costume (fix first):**
- **#8** — the only finding producing wrong *data* today; smallest fix.
- **#2** — the most common beginner mistake gets the worst diagnostics in
  exactly the early phases where it happens most.
- **#5** — finishes the v4 #1 fix across its three unfixed siblings; 30
  minutes.

**Tier 2 — drift traps with evidence the pattern already fired once:**
- **#7** — cross-module contract drift the byte-identity gate cannot see.
- **#4** — same gate blind spot, scripts/ edition; cheapest insurance.
- **#1** — largest surface; do after #2 so the helper lands in a cleaned tree.

**Tier 3 — clarity debt, schedule as a batch:**
- **#3**, **#6**, **#9** — each independent, each mechanical, none urgent.

---

*Next step per process: collaborative discussion — each finding ends as
Changed / Deferred (with trigger) / Accepted (eyes open) / Withdrawn / Needs
investigation, logged in `docs/status-remediation.md` as Round 5.*
