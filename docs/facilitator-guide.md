# Facilitator Guide

This guide is for tech leads, bootcamp instructors, and senior devs running Akanga
Mirin as a 2–4 day workshop. It assumes you have read the README and skimmed the
phase docs in `docs/learning/`. It tells you how to schedule the phases, what
participants will get stuck on, how to assess their work, and what to do before
anyone walks into the room.

**Do the phases yourself first.** At minimum, complete every phase you plan to run.
The traps listed below are real — you will field them with much more confidence
having hit them yourself.

---

## Honest limitations — read this before promising anything

> - **Reference solutions exist for all 9 phases** (`make status` shows the live
>   matrix; `make test-solution PHASE=N` proves any of them on your machine). That
>   means "look at the solution" is now *possible* at any moment — which is why the
>   stuck protocol below treats it as the **last** layer, governed by the peek
>   policy in `solutions/README.md`: peek one function after 30+ minutes stuck,
>   and record what you learned (`make peek` does both).
> - **Phase 5 (Textual TUI) is not workshop material.** It is 12–20 hours of solo
>   work. Assign it as post-workshop homework using its internal checkpoints
>   (5.1 / 5.2 / 5.3) — never schedule it into a workshop day.
> - **WebSocket push and the ego-graph REST endpoint are untested stretch goals**
>   in Phase 6. The tested contract is the CRUD + edges + templates endpoints.
> - **The API has no authentication** — it binds to `127.0.0.1` by design. Do not
>   demo it on `0.0.0.0` on shared workshop Wi-Fi.

---

## 1. Workshop formats

All formats follow the roadmap's MVP cut as their spine: **0 → 1A → 1B → 2 → 6**
(Phase 6 depends only on phases 0–2; nothing in 3–5 blocks a working REST API).
That cut is roughly 10–14 hours of hands-on coding — feasible in two full days
with buffer, but only if setup happened *before* day 1.

| Format | Phases | Hands-on hours | Outcome artifact |
|---|---|---|---|
| 2-day | 0, 1A, 1B, 2, 6 | ~10–14h | REST API over a personal knowledge graph |
| 3-day | + 3, 4 | ~16–21h | Same, plus live re-indexing on file save |
| 4-day | + 7, MCP demo (8) | ~19–25h | Same, plus git auto-history and a Claude integration demo |

Phase 5 is excluded from all formats. Point participants at checkpoints 5.1–5.3
in `docs/learning/phase-05-terminal-ui.md` as structured homework: 5.1 alone
(~4–6h) yields a working three-panel browser.

### 2-day schedule

**Day 1 — files, edges, sync queue**

| Time | Block |
|---|---|
| 09:00–09:30 | Setup verification (everyone runs `make test PHASE=0` and sees failures, not errors), framing: "the file is the database" |
| 09:30–12:00 | Phase 0 — parser, atomic write, UUID identity |
| 12:00–13:00 | Lunch |
| 13:00–13:20 | Phase 0 group reflect (see per-phase notes) |
| 13:20–15:50 | Phase 1A — edge schema, inline shorthand, write-back |
| 15:50–16:10 | Phase 1A group reflect |
| 16:10–17:30 | Phase 1B — sync queue (concepts + start; finishes Day 2) |

**Day 2 — index, then API**

| Time | Block |
|---|---|
| 09:00–10:15 | Phase 1B finish + group reflect |
| 10:15–13:00 | Phase 2 — SQLite, WAL, FTS5, two-pass indexer |
| 13:00–14:00 | Lunch |
| 14:00–14:30 | Phase 2 buffer + group reflect |
| 14:30–16:45 | Phase 6 — FastAPI CRUD, path traversal protection |
| 16:45–17:30 | Demo round: each participant `curl`s another participant's running API; wrap-up |

The Day 2 afternoon is the tightest block of the whole workshop. If Phase 2 runs
long, cut the Phase 6 stretch endpoints ruthlessly — the tested core contract
(nodes CRUD, edges, neighbors/backlinks, templates) is the deliverable.

### 3-day schedule

Day 1 unchanged (0, 1A, 1B — 1B fully fits with the extra slack). Then:

| Day 2 | Day 3 |
|---|---|
| 09:00–12:30 Phase 2 | 09:00–12:00 Phase 4 — watcher, EventBus, drain |
| 13:30–14:00 Phase 2 reflect | 12:00–12:30 Phase 4 group reflect |
| 14:00–16:30 Phase 3 — BFS ego-graph | 13:30–16:00 Phase 6 |
| 16:30–17:00 Phase 3 reflect + "See It Work" demo (render your own vault's ego-graph) | 16:00–17:00 Demo round + close |

Phase 3's "See It Work" section (rendering the ego-graph of the participant's own
vault) is the best morale moment of the workshop — do not skip it.

### 4-day schedule

Days 1–3 as above, with more generous buffers. Day 4:

| Time | Block |
|---|---|
| 09:00–11:30 | Phase 7 — GitManager, non-fatal wrappers, debounced auto-commit |
| 11:30–12:00 | Phase 7 group reflect |
| 13:00–14:30 | **MCP demo (facilitator-led, from Phase 8)** — run the Phase 8 reference solution (`make test-solution PHASE=8` proves it works on your machine), wire it into Claude Desktop or Claude Code, and ask Claude a multi-hop question against a vault built during the workshop. Show the typed triples in the response. |
| 14:30–16:00 | Participants who want to attempt Phase 8 themselves start it; others do vault pair-review (below) |
| 16:00–17:00 | Retro: what each person ships home with; Phase 5 homework briefing (checkpoints 5.1–5.3) |

The MCP demo lands hardest when the vault Claude queries is one a *participant*
built — ask for a volunteer's vault on day 3.

---

## 2. Per-phase facilitation notes

For every phase the checkpoint is the same command:

```bash
AKANGA_SRC=./src make test PHASE=N
```

Insist on the explicit `AKANGA_SRC` — without it the Makefile warns but defaults
to `./src`, and a participant in the wrong directory will "pass" against nothing.
`make where-is-my-src` settles any confusion in five seconds.

Run the **Group reflect** prompt (quoted from each phase doc) as the wrap-up
discussion — 15–20 minutes, whole room or groups of 3–4.

### Phase 0 — File System as Database (2–3h)

- **Trap: the atomic write.** Participants stream directly to the target file with
  `open(path, "w")` and pass every test except `test_write_is_atomic`. The fix is
  temp file + `os.replace`. Don't pre-empt it — let the test fail, then ask "what
  does a reader see if your process dies mid-write?"
- **Trap: UUID preservation.** Parsing a file that already has a valid `id` must
  keep it; only missing/invalid ids get a fresh `uuid4()`. Watch for code that
  regenerates unconditionally — it passes the happy-path tests and corrupts identity.
- **Group reflect:** *Is the `content_hash` in the DB part of the source of truth,
  or part of the derived index? Where exactly is the boundary, and does the
  distinction matter for how you reason about correctness?*

### Phase 1A — Edge Schema (2–3h)

- **Trap: write-back idempotence.** `test_writeback_is_idempotent` calls
  `write_back` twice; naive implementations duplicate the edge on the second call.
  The dedup key is `(relation, target)` — *not* the UUID pair, because inline edges
  carry an empty `target_id`. This is the single most common failure of the phase.
- **Trap: the code-block regex.** `[[Some Node | supports]]` inside a fenced code
  block must be ignored. Participants who reach for one giant regex struggle;
  steer them to "strip fenced blocks first, then scan."
- **Group reflect:** *`write_back` is described as "write atomically if changed."
  What is the check that determines "changed"? Who should own that check —
  `write_back` itself, or the caller? Which leads to more correct behavior at scale?*

### Phase 1B — Workspace and Sync (2–3h)

- **Trap: forgetting to commit.** `test_sync_queue_survives_restart` closes and
  reopens the DB; an enqueue without `conn.commit()` vanishes. Quick fix, but a
  good teaching moment about transaction boundaries.
- **Trap: enqueue idempotence.** Re-enqueueing the same pending `node_id` must not
  create a second row — the check is against *pending* rows only.
- **Group reflect:** *Workspace rename and node title rename both enqueue the same
  kind of job. One table with a `job_type` field, or separate tables? What does
  unifying make easier, what does it obscure, and does the distinction matter at
  drain time?*

### Phase 2 — Storage and Indexing (3–4h)

- **Trap: FTS5 operator injection.** Parameterized queries alone are not enough —
  `* OR title:*` passed as the bound parameter still reaches the FTS5 engine as an
  operator expression and raises. The term must *also* be wrapped in FTS5
  double-quote literals (`'"term"'`). `test_search_fts_no_operator_injection`
  enforces this (it's SEC-06 in the reference implementation).
- **Trap: single-pass edge resolution.** `test_two_pass_edge_resolution` indexes a
  file whose edge target doesn't exist in the DB yet. Pass 1 must complete (all
  nodes) before pass 2 (all edges) begins. Participants who resolve edges per-file
  get unresolved `target_id`s and don't understand why.
- Watch also for the classic `(node_id)` vs `(node_id,)` tuple typo — it produces
  baffling driver errors.
- **Group reflect:** *WAL and `threading.Lock` address concurrency at different
  layers. What does WAL prevent, and what does Lock prevent that WAL does not?
  Construct a concrete two-thread scenario where WAL alone is insufficient.*

### Phase 3 — Graph Algorithms (2–3h)

- **Trap: no visited set.** Any bidirectional pair (A⇄B) loops BFS forever.
  `test_build_ego_graph_cycle_handling` will hang, not fail — warn participants
  that a hanging test means this, and set a habit of `pytest --timeout` or Ctrl-C.
- **Trap: edge deduplication.** BFS reaches both endpoints of an edge, so each
  logical edge is encountered twice; dedup by `(source_id, target_id, relation)`.
- **Group reflect:** *BFS groups nodes by distance from the root, but the result
  dict doesn't store distance. Should it? What would the renderer do differently
  with distance information, and is that worth the complexity now?*

### Phase 4 — Concurrency and Events (3–4h) — the hardest workshop phase

- **Trap: `set_loop` ordering.** `eventbus.set_loop(loop)` must run *before*
  `watcher.start()` — the moment the watcher starts, its daemon thread can publish,
  and async subscribers need the registered loop. The startup buffer catches the
  race, but participants who rely on it as the normal path have not understood it.
- **Trap: a `threading.Timer` per path.** The tempting debounce design spawns one
  OS thread per file event. The correct design is one lock-protected
  `dict[path → deadline]` polled by a single worker thread. The phase doc's
  pitfalls section spells this out — make participants read it before coding.
- On macOS, atomic writes arrive as `on_moved` events, not `on_modified` —
  Mac-only "the watcher never fires" reports are almost always this.
- **Group reflect:** *What happens when two files change during the same debounce
  window? Walk through the single-worker design — the deadline dict, the ~25ms
  poll, the stop Event — then argue the other side: what would Timer-per-path cost
  during a 200-file git checkout?*

### Phase 6 — REST API (3–4h)

- **Trap: path traversal (SEC-02).** The only safe pattern is
  `vault_root.joinpath(body.path).resolve().is_relative_to(vault_root.resolve())`.
  The test suite covers three escape shapes — relative `../`, absolute path, and
  symlink — and `normpath`/`startswith`/`".." in path` each fail at least one.
  Expect participants to "fix" the first failing test with a substring check and
  then be surprised twice more.
- **Trap: 200 vs 201.** Creates must return 201. Small, but it fails the test and
  teaches contract precision.
- **Group reflect:** *The DB is a derived index that can be rebuilt. Should the
  API update the DB directly, or write the file and re-index? Which is right,
  and why?*

### Phase 7 — Version Control (2–3h)

- **Trap: `is_dirty()` without `untracked_files=True`.** New files are untracked,
  so a fresh vault appears clean and the first commit is silently skipped.
- **Trap: letting git exceptions escape.** Every GitManager method is non-fatal by
  contract — catch, log at WARNING, return the safe default. In tests, commits also
  fail without `user.email`/`user.name` configured.
- **Group reflect:** *`GitManager` stages ALL changes (`git add -A`) before every
  commit. Is that right for a personal vault? What would you never want staged,
  and how does `.gitignore` help? Walk through two edge cases.*

---

## 3. Assessment rubric

Two gates per phase, in order:

**Gate 1 — tests (objective).** `AKANGA_SRC=./src make test PHASE=N` green. This is
binary and self-serve; do not spend facilitator time re-reviewing code that passes.
Since the reference solutions are published, a green run no longer proves the code
was *earned* — Gate 2 and the pair-review are what distinguish earned green from
copied green. After Gate 1, have each participant run the post-green ritual from
`solutions/README.md`: **diff your implementation against the reference, write one
vault node about a difference and why.** That node cannot be faked with a copied
solution — there is no diff.

**Gate 2 — vault (conceptual).** Every phase ends with a "Vault Nodes to Create"
table — the vault is the proof of understanding, not the tests. It is a deliverable,
not an extra: budget **~1 hour per phase** for vault nodes and the Reflect prompts
(the phase docs' "Estimated time" lines now state this separately from coding time) —
either inside the schedule blocks above or as explicit same-day homework. Check it with:

```bash
make vault-check PHASE=N
```

This validates that the phase's expected nodes exist, that edges are well-formed,
and that relation names match the 71-type vocabulary (custom relations warn, not
fail). `make vault-check FULL=1` adds the ≥50-node end-of-path check.

**What a good vault node looks like.** Titles matching the manifest is the floor.
A *good* node has typed edges and a body in the participant's own words:

```markdown
---
id: 7c1b9e2a-…
title: WAL Mode
type: note
tags: [sqlite, concurrency]
edges:
  - relation: is_part_of
    relation-id: PA-001
    target: SQLite
    target-id: 3f2a…
  - relation: solves
    relation-id: EP-004
    target: Reader-Writer Blocking
    target-id: ""
---
Writers append to a side log instead of locking the main DB file, so readers
keep reading the last committed snapshot. The payoff is cross-process: the CLI
can read while the watcher writes. It does NOT make compound read-check-write
sequences safe — that's the threading.Lock's job, one layer up.
```

The signals: typed edges with relation IDs, a dangling `target-id` left honestly
empty, and a body that states a *limit* of the concept, not just a definition.
A node that copies the phase doc's prose verbatim fails the conceptual gate.

**Pair-review protocol (15 min, end of each day).** Pairs swap vaults. Each
reviewer picks one node and asks the author two questions: *"Why this relation
type and not a neighbor of it?"* (e.g. `solves` vs `enables`) and *"What would
break if this node disappeared?"* Then both run `make vault-check` on each
other's vault. Rotate pairs daily. This is the cheapest conceptual assessment
you can run, and it surfaces copy-paste vaults immediately.

---

## 4. Environment prep checklist

Setup failures are the number-one schedule killer. Do all of this **before day 1**.

**Prerequisites email (send 1 week out):**

- Python managed by **uv** ([install instructions](https://docs.astral.sh/uv/)) — the
  Makefile drives everything through `uv run`
- **git** installed and configured (`git config user.name` / `user.email` set —
  Phase 7 commits fail without them)
- A code editor of their choice. `tmux` + `nvim` + `glow` are needed only for the
  optional `make study` three-pane layout — **a plain editor is completely fine**,
  and the study script tells them what's missing if they try it
- Optional: `direnv` (auto-activates the environment), Claude Code CLI (for the
  study layout's third pane)
- Ask everyone to run the smoke test below and reply with the output

**Smoke test (must pass on every machine before day 1):**

```bash
git clone https://github.com/ArthurPieri/akanga_mirin
cd akanga_mirin
make setup               # uv sync --all-extras
make skeleton PHASE=0    # copies the Phase 0 skeleton into ./src/
AKANGA_SRC=./src make test PHASE=0   # tests run and FAIL with NotImplementedError — that is success
make vault-init          # scaffolds ./vault + akanga.yaml
```

The expected state is *failing tests*, not passing ones — say so explicitly or
you will get "it's broken" replies.

**Common setup failures:**

| Symptom | Cause / fix |
|---|---|
| `uv: command not found` | Installed but not on PATH — re-open the shell, or `source $HOME/.local/bin/env` |
| `make setup` hangs or fails resolving packages | Corporate proxy / offline room. Have everyone run `make setup` at home; uv's cache makes day-1 re-syncs offline-safe |
| `make setup` fails *downloading a Python interpreter* (not packages) | uv fetches interpreters from GitHub releases, which corporate proxies block even when PyPI works. Fix: point uv at a system Python that satisfies the pin (`uv python pin $(which python3)`), or pre-run `uv python install` on an unrestricted network before day 1 |
| Tests error (not fail) with import errors | They skipped `make skeleton PHASE=0`, or `AKANGA_SRC` points at the wrong directory — `make where-is-my-src` |
| ImportError at a **phase transition** (phase N was green, phase N+1 errors on import) | Later phases add new stubs *inside files the participant already owns* (e.g. phase 1 adds symbols to `parser.py`), and skip-existing preserved the old file without them. Fix: re-run `make skeleton PHASE=N+1` — it now reports the missing symbols in preserved files and merges the new stubs in |
| `direnv: error … is blocked` | Run `direnv allow` once in the repo — or skip direnv entirely, it's optional |
| `make study` exits with a missing-dependency error | tmux/nvim/glow not installed — fine; use a plain editor and `make docs-phase PHASE=N` is replaced by reading the doc in the editor |
| Windows machine | The Makefile and study script assume a POSIX shell. WSL2 works; native Windows does not. Flag this in the email |

---

## 5. When participants get stuck

Reference solutions exist for **every phase**, so "compare with the solution" is
always available — which makes the discipline of the remediation ladder more
important, not less. Use the layers in order; the solution is the last layer,
never the first:

1. **The test failure message.** The suites are written so failure messages are
   hints by design — the test names and assertions describe the missing behavior
   (`test_enqueue_is_idempotent` tells you exactly what's wrong). First response
   to "I'm stuck" is always "read the failing test, out loud."
2. **The skeleton docstrings.** Every stub has WHAT/WHY/HOW docstrings and raises
   `NotImplementedError` with a specific hint. Stuck participants have usually
   read the WHAT and skipped the HOW.
3. **The phase doc's Pitfalls section.** Most blockages are a documented pitfall.
   Ask "which pitfall is this?" before giving the answer.
4. **Pairing.** Pair the stuck participant with someone who just passed that test —
   the explainer consolidates their own learning. Cap solo struggle at ~30 minutes
   per test; cap pair struggle at ~20 more.
5. **The foundation docs.** Gaps in prerequisites (asyncio, SQLite, threading) are
   self-remediation material: `make foundations TOPIC=sqlite-basics` etc. Send the
   participant there during a break, not mid-exercise.
6. **The reference solution — one function, logged.** After 30+ minutes stuck on
   a single test and layers 1–5 exhausted, have the participant run `make peek`
   (or open `solutions/phase_NN/` themselves) for the **one** function blocking
   them — on the condition that they record what they learned (`make peek`
   appends the note to a learner-local `PEEKS.md`). Never project a whole
   solution file to the room; wholesale copying is the one not-reasonable move
   (`solutions/README.md` has the full norms list).
7. **You.** If layers 1–6 failed on a phase-critical item, give the answer
   directly and move on — protect the schedule. Note what stalled them; if two
   or more people hit the same wall, stop the room and whiteboard it.

A useful timebox heuristic per phase: when a participant is more than ~45 minutes
behind the room, have them stub the remaining tests' behavior with your dictated
fix and catch up conceptually in the group reflect. Working-but-not-fully-earned
code in phase N beats being locked out of phase N+1.

---

## 6. Quick reference — facilitator commands

```bash
make status                          # phase completion matrix (skeleton/tests/solution)
AKANGA_SRC=./src make test PHASE=N   # the per-phase checkpoint
make where-is-my-src                 # what AKANGA_SRC resolves to
make vault-init                      # scaffold ./vault + akanga.yaml
make vault-check PHASE=N             # conceptual gate per phase
make vault-check FULL=1              # end-of-path ≥50-node check
make test-solution PHASE=N           # reference solution (all 9 phases)
make verify PHASE=N                  # cumulative check of a solution (suites 0..N)
make docs-phase PHASE=N              # phase doc in glow (PHASE=1a / 1b for the split phase)
make example PHASE=N                 # run the phase's standalone ~30-line concept demo
```

The `make example` scripts are useful as 5-minute live demos at the start of a
phase block — one concept, immediately runnable, before participants build it
themselves.
