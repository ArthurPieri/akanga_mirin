# Implementation Plan — Noteapp Alignment Remediation (Rev 2)

> Source findings: `docs/noteapp-alignment-audit.md` (2026-06-12).
> Rev 2 (2026-06-12): amended per `docs/adversarial-analysis-v6.md` — all 12 critiques
> resolved (gate hardening, folded-edge matching + de-typing, hyphen-key tolerance N11,
> deterministic title resolution N10, learner migration admonitions, sequencing repairs,
> sweep-hole patches, governance one-liners). A fresh session should be able to execute
> this plan top-to-bottom without re-deriving anything.

---

## Execution rules (v6 #5)

1. Every line number in this plan is a **pre-round anchor** — locate edits by the quoted
   text, never by line number alone; re-grep all anchors for a stage before starting it.
2. A range-replace ("replace `:N–M`") executes only after the quoted context at both
   boundaries matches; on any mismatch, stop and re-locate — never apply blind.
3. Every commit touching `docs/learning/` runs `uv run python scripts/check_doc_contracts.py`
   **before** commit (CI runs it on every push — don't land red on main mid-round).
4. Commit messages: `<type>: noteapp-alignment <N-ids> — <summary> (<commit-id>)`, house
   types feat/fix/docs — e.g. `feat: noteapp-alignment N1 — file-first manual edges (A-1)`.
5. The four "Changed 2026-06" admonitions (Step 0.7 below) each add a block near line 4 of
   their phase doc — every later line-pinned edit in those docs shifts; rule 1 applies
   doubly there.

---

## Step 0 — Re-stage the noteapp reference mirror

Sub-agents cannot read `../noteapp`. Before executing, re-create the read-only mirror:

```bash
grep -qxF '/.tmp-noteapp-mirror/' .gitignore || echo '/.tmp-noteapp-mirror/' >> .gitignore
M=.tmp-noteapp-mirror; rm -rf "$M" && mkdir -p "$M/docs" "$M/tests"
rsync -a --exclude '__pycache__' ../noteapp/src "$M/"
cp ../noteapp/tests/test_links.py ../noteapp/tests/test_conformance.py \
   ../noteapp/tests/test_frontmatter_edges.py ../noteapp/tests/test_idempotency.py "$M/tests/"
cp -r ../noteapp/tests/data "$M/tests/"
rsync -a ../noteapp/docs/research ../noteapp/docs/guide ../noteapp/docs/analysis/round-2/SYNTHESIS.md "$M/docs/"
```

The `.gitignore` line is committed in **G-0** (the round-kickoff commit, with Step 0.5 and
the CLAUDE.md focus flip) — "never commit the mirror" is then enforced by git, not by
vigilance (v6 #8). Delete the mirror when the round is done.

## Step 0.5 — Harden the docs gate (commit G-0) (v6 #1)

`mkdocs.yml` today has no `strict:` and no `validation:` block — a missing nav file, a
broken cross-link, or an unexcluded doc all build with exit 0, so every `mkdocs build`
gate below would otherwise be a no-op. Three edits, one commit, BEFORE Stage 1:

1. **`exclude_docs`**: add `noteapp-alignment-audit.md` (a contributor doc full of solution
   internals; today it builds onto the learner site). `adversarial-analysis*.md` already
   covers v6; `plan-*.md` already covers this plan — no other additions needed.
2. **nav**: add `deployment.md` (deliberately public per the mkdocs.yml comment and
   docs/README.md) — new top-level section after Architecture:
   ```yaml
     - Operations:
       - "Deployment": deployment.md
   ```
3. **Strict mode** — top level, after `site_description`:
   ```yaml
   strict: true
   validation:
     nav:
       omitted_files: warn
       not_found: warn
       absolute_links: warn
     links:
       not_found: warn
       anchors: warn
       unrecognized_links: warn
   ```
   (MkDocs ≥1.6. With `strict: true`, every `warn` fails the build with exit 1.)

Gate for G-0: `uv run mkdocs build` exits 0 with **zero** not-in-nav/broken-link lines
(verified green against today's tree with exactly these edits). From this commit on, every
`mkdocs build` in this plan is a strict build. **Consequence:** strict mode fails on any new
doc that is neither in nav nor excluded — C1 and C2 MUST add their own nav entries in their
own commits.

## Step 0.7 — CLAUDE.md round flag (commit G-0) (v6 #8)

Replace CLAUDE.md's "No round is currently in progress…" paragraph (keep the deferred-item
sentence) with:

> **Noteapp-alignment round IN PROGRESS** — plan: `docs/plan-noteapp-alignment.md`;
> findings: `docs/noteapp-alignment-audit.md` + `docs/adversarial-analysis-v6.md`;
> running log: the N-series section of `docs/status-remediation.md`. One deferred item
> with a trigger: `check_doc_contracts.run_checks` extraction, revisit only if that
> file grows.

C10 item 7 restores the closed-state text at round end.

---

## Unified decision register (append to `docs/status-remediation.md` as the round executes)

New **N-series** ("Noteapp alignment"). Full entry text is drafted inside each workstream
item; amended rows reflect adversarial-analysis-v6 resolutions.

| # | Decision (resolved — do not re-litigate during execution) |
|---|---|
| N1 | Manual edges are **file-first**: `POST /api/v1/edges` appends to the source node's frontmatter `edges:` block (underscore keys) and reindexes; DELETE matches the entry by `target_id` OR — because folded entries persist with `target_id: ""` — by case-insensitive target title (the `resolve_wikilink` case rule), removes it, and **de-types the originating `[[T \| rel]]` shorthand to `[[T]]`** so the fold cannot resurrect it. The 409 duplicate guard uses the same matching rule, so folded duplicates 409 too. Guards: 400 self-edge / reserved `wikilink` / missing endpoint; 409 duplicate. noteapp's uuid5 ids + `auto` column NOT ported (delete-then-rederive + UNIQUE constraint make them unnecessary). |
| N2 | Indexer pass-2 trigger adopted: `rederive_all = new_files or removed > 0` — **full scans** re-derive edges for all nodes whenever a file was added or removed; the per-file watcher path (`index_file`) still re-derives only the changed node and defers cross-file resolution to the next full scan. |
| N3 | Unresolved wikilinks and unresolvable fm edges **log a warning** ("never silently evaporate a link the user wrote"); stub auto-creation NOT ported as code; ADOPTED as a doc-only Phase 2 "Stretch (untested)" mention (lands with C6; counted in N9's TEACH-tier doc-only batch). |
| N4 | **Alias rule adopted** into the curriculum spec: pipe segment matching `^[a-z][a-z0-9_-]*$` (after strip) = relation; anything else (spaces/uppercase/digit-first/escaped `\|`/multi-pipe) = Obsidian display alias → plain wikilink. `parser.RELATION_SLUG_RE` + `parser.split_pipe_segment` are THE grammar; `links.py` defers. Verified: all 72 vocabulary slugs + every relation in docs/tests still classify as relations. Inline code stripped in both extractors. Prior any-pipe-is-a-relation behavior retroactively recorded as the divergence it was. |
| N5 | The double edge from `[[A\|relation]]` (untyped wikilink + typed fm edge) was **accidental** (no doc/test pinned it); single-edge semantics ported — a typed link yields exactly one (typed) edge. |
| N6 | `textutil.slugify` (noteapp-identical collapse-runs rule) is the single title→filename rule, introduced at **Phase 0**, conformance table pinned in `tests/phase_00/test_textutil.py`. `create()` collisions → `unique_path` numeric suffixes (fixes silent overwrite). REST API keeps 409-on-existing-path by design (explicit intent, client can retry); `create()`/MCP auto-suffix (capture must never lose a note) — the asymmetry is taught in phase-06. MCP `create_node` uses the shared rule. |
| N7 | Foundations docs carry a one-line audience/effort header (`**Audience:** … · **Read time:** ~N min`); relation-vocabulary uses the reference-doc variant; estimates word-count-calibrated. |
| N8 | `build_ego_graph` gains `limit` (node budget incl. root, default `None` = unbounded) + `EgoGraph.truncated` flag; budget-excluded neighbors contribute no nodes and no edges; 2 shipped tests assert count+flag, never membership. Phase 6 ego stretch endpoint documents `?limit=`. (noteapp R2 #26, taught at build time.) |
| N9 | TEACH-tier items adopted **doc-only**: Phase 8 relation soft-validation (difflib, warn-never-reject); Phase 3 `to_mermaid` / Phase 6 `/export?format=` (json\|mermaid; graphml named only); Phase 2 stub-auto-creation stretch mention (noteapp `create_stub_node` — `type: note`, tag `stub`; lands with C6, see N3); and the phase-00 conformance-table testing tip (the pattern A6's `test_textutil.py` itself uses; lands with A6). No shipped tests, no skeleton stubs for any of them. |
| N10 | Duplicate wikilink titles resolve **deterministically**: `resolve_wikilink` orders matches by vault path (`ORDER BY path ASC` — `path` is NOT NULL UNIQUE) and takes the first, logging a warning that names every shadowed duplicate. noteapp's flavor is oldest-wins (`ORDER BY created_at ASC, id ASC` in `get_node_by_title`); the curriculum's `nodes` schema has no timestamp column, and minting one wouldn't survive `rm *.db` rebuilds — path order is the rebuild-stable, human-explainable equivalent. |
| N11 | Frontmatter edge-key spelling: **underscore keys are canonical everywhere** (docs, API writes, `write_back` serialization); the phase 2–8 readers (`write_back`'s existing-edge reader, `_reindex_edges`'s fm loop) gain phase_01's dual-spelling read fallback (`raw.get(k, raw.get(k.replace("_","-")))`) so hand-authored hyphenated entries (`relation-id:`/`target-id:`) are read correctly and normalized — never silently ignored, never destroyed on fold. phase-01a's canonical block flips to underscores. Read both, write underscores. |

Workstream B's correctness sweep is recorded as a prose log entry (see B8), not a numbered decision.

---

## Cross-workstream collisions — resolved sequencing

| File | Touched by | Resolution |
|---|---|---|
| `docs/learning/phase-03-graph-algorithms.md` traversal block + `graph.py` | B2 (rewrite to tuple contract) then C4 (add `limit`/`truncated` + admonition) | Execute **B2 first** (signature unchanged → lint check 1 stays green), then C4 amends signature + budget in code, skeleton, AND the just-rewritten doc block **in one commit** (doc-first split trips lint check 1 — load-bearing). B1 separately fixes `graph.py:16` docstring (71→72) — runs before both. |
| `docs/foundations/yaml-and-markdown-frontmatter.md` | B4 (tail rewrite `:471-559`) then C5c (new section in same region) | C5c lands **after** B4, placed after B4's rewritten "Akanga's Node Frontmatter Format". |
| `docs/learning/phase-01a-…` | B1 (`:73,:79` counts), A4 (grammar lines + hyphen→underscore block + `:181` registry fix + admonition), C5b (sidebar), C8 (fence tip), C1/C5a pointers | Different regions — **A4 ↔ B1 disjoint, order immaterial** (execution runs A4 at stage 3, B1 at stage 5 — consistent with the stage table); then C5b/C8/pointers. C5b uses the **"alias rule adopted"** variant (N4). |
| `docs/learning/phase-06-rest-api.md` | A1 (POST /edges contract + pitfall + admonition), B6 (ghost lines incl. `:191`), B7 (Tauri/slugify glosses), C4 (`?limit=` line), C7c (Pydantic pointer), C9b (export line), A6 (N6 collision sentence) | Different lines; any order after A1. |
| `docs/learning/phase-02-…` | B3 (DB_SCHEMA block), B6/B7 (ghosts, ripgrep), C6 (edge-lifecycle box + stub-stretch mention), C1 pointer | Different regions. C6 uses the **resolved** taxonomy lines (N1/N2/N3/N10/N11 — drafted in C6). |
| `docs/learning/phase-08-…` | B1 (counts + test rename), C7a/b (concepts), C9a (stretch) | Different regions; B1 first. |
| all 17 `docs/foundations/*.md` (H1 header line) | C3 (inserts the audience/read-time line under every H1) vs B3 (sqlite-basics `:170-220` rewrite), B4 (yaml `:471-559` rewrite), B5 (asyncio-primer multi-range rewrite) | **C3 runs after Stage 8** (Stage 9.5). Run earlier it shifts every B3/B4/B5 line anchor by one; run in parallel it merge-conflicts in three files. C3 locates by H1 text, never by line number. |
| `docs/status-remediation.md` | all workstreams | One new round section; N-entries appended in execution order; NOTEAPP SYNC superseding line (B8). |
| `docs/index.md` | B1 (`:65` count), C10 (two new foundation bullets) | B1 first. |

---

## Execution sequence

| Stage | Commits | Content | Gated on |
|---|---|---|---|
| 0 | G-0 | round kickoff: `.gitignore` mirror entry (Step 0) + mkdocs strict hardening (Step 0.5) + CLAUDE.md "Current focus" flip (Step 0.7) | — |
| 1 | A-1 | **F1** file-first manual edges (P0) + phase-06 admonition | G-0 |
| 2 | A-2 | **F4+F5+N10** indexer trigger + warnings + deterministic title resolution (A7) | — |
| 3 | A-3 | **F2+F10+N11** alias rule + single-edge typed links + hyphen-key tolerance + phase-01a doc pass + admonition | — |
| 4 | A-4 | **F3** textutil + collision-safe create + phase-00 doc pass + admonition + conformance tip | after A-3 (avoids interleaved parser.py propagation) |
| 5 | B-1 | 71→72 sweep (incl. `docs/index.md:65`, kg-theory:157, implementation-plan:115) + inverse recount + test rename | after Stage 4 (db.py/graph.py docstring propagation runs once, post-A) |
| 6 | B-2 | phase-03 traversal rewrite (tuple contract) | B-1 |
| 7 | B-3, B-4 | sqlite-basics FTS5 + DB_SCHEMA block; yaml tail rewrite | — |
| 8 | B-5+6, B-7 | asyncio-primer contract + active-manager ghost sweep (extended); small fixes + glossary | — |
| 9 | B-8 | lint check 6 (context-anchored) + NOTEAPP SYNC superseding line + status log | B-1 |
| 9.5 | C-3 | header rollout (17 docs) | **after Stage 8** — B3/B4/B5 rewrite three of the same files by line range |
| 10 | C-1, C-2 | graph-theory-basics.md; graph-algorithms-beyond-bfs.md (**each commit carries its own mkdocs nav entry** — strict mode, Step 0.5) | — (parallel-safe with 5–9) |
| 11 | C-4 | ego budgeting (code+tests+docs) + phase-03 admonition | Stage 6 (B2's block) + A propagation discipline |
| 12 | C-5a, C-5c, C-7, C-8 | OOP sidebar; schema-vs-dict sidebar (after B-4); RAG/injection primers + Pydantic pointer; fence-regex tip | C-5c after Stage 7 |
| 13 | C-6, C-5b, C-9 | edge-lifecycle box + stub-stretch mention; alias sidebar (N4 variant); stretch items | Stages 1–3 |
| 14 | C-10 | nav verification/doc-map/cross-links/decision-log wiring + CLAUDE.md round close | everything |

**Final repo-wide gate** (after Stage 14):
```bash
make verify-all          # NOT "verify PHASE=8" — that runs suites against solutions/phase_08 only
uv run python scripts/sync_forward.py --check-all
uv run python scripts/check_doc_contracts.py
uv run ruff check tests/ skeletons/ scripts/ solutions/ examples/
make examples-all
uv run mkdocs build      # strict per Step 0.5 — this IS the link check
grep -rn '\b71\b' docs tests skeletons solutions scripts \
  --include='*.md' --include='*.py' \
  --exclude='relation-vocabulary.md' \
  --exclude='adversarial-analysis*.md' \
  --exclude='status-remediation.md' \
  --exclude='analysis-and-enhancements.md' \
  --exclude='noteapp-alignment-audit.md' \
  --exclude='plan-noteapp-alignment.md' \
  --exclude-dir=archive
# → zero hits (NEVER pipe to `grep -v relation-vocabulary` — that filters on line CONTENT
# and hides index.md:65, phase-01a:79, phase-08:445, implementation-plan:115)
```

---

## Verified repo mechanics (re-checked against the actual files)

- `scripts/sync_manifest.toml`: `parser.py`, `links.py`, `indexer.py`, `db.py` canonical in phase 2 (`applies_to=[2..8]`); `server.py` canonical in phase 6 (`[6,7,8]`); `src/akanga_mcp/server.py` single-copy (phase 8). `parser.py` also exists in `solutions/phase_00` and `phase_01` as smaller pre-introduction forms **outside** manifest scope — hand-edit those, never sync-forward.
- Manifest completeness pass **fails** on any new file in ≥2 solution trees without a `[[modules]]`/`[[ignore]]` entry → F3's `textutil.py` needs its manifest entry in the same commit.
- Only introduction-phase skeletons carry real WHAT/WHY/HOW stubs; later-phase skeleton copies are markers that sync_forward never touches. Stubs must keep raising `NotImplementedError` (`make skeleton-check PHASE=N`).
- Propagation ritual: edit canonical → `make test-solution PHASE=N` → `make sync-forward FROM=N FILE=src/... BASE=solutions APPLY=1` per file → `uv run python scripts/sync_forward.py --check-all` → cumulative verify.
- `scripts/check_doc_contracts.py` lints ONLY `docs/learning/phase-*.md`: (1) `def` signatures in non-"illustrative" python blocks vs skeleton ASTs (trailing defaulted params may be omitted in the doc), (2) `make` targets, (3) foundation-doc existence, (4) backticked `test_*` tokens in `## Deliverable` sections must exist in `tests/phase_NN/`, (5) doc What-You-Build functions must exist in the skeleton — so new doc table rows require their skeleton stub in the SAME commit.
- Tests load via `AKANGA_SRC` + `tests/_helpers.py::load_attr` + per-phase autouse fixtures; new test files follow that loader and the rich-failure-message convention.
- **Learner migration signal (v6 #4)**: each of the 4 phases whose graded contract changes (00, 01a, 03, 06) gets a `!!! warning "Changed 2026-06 (noteapp-alignment round)"` admonition inserted directly after the `**Estimated time**` line (line 3 in all four docs), in the SAME commit as that phase's contract change (00 → A-4, 01a → A-3, 03 → C-4, 06 → A-1). Migration mechanics verified: `make skeleton PHASE=N` copies only files absent from src/ (textutil.py arrives as a new file), preserves every existing file, and `skeleton_merge.py` APPENDS missing top-level symbols into preserved files with a signature-collision notice — it never modifies learner code.

---

# Workstream A — Code alignment

Execution order: **F1 → F4+F5+N10 → F2+F10+N11 → F3.**

## A1 (F1, P0) — Manual edges become file-first

**Decision (N1): port file-first persistence AND keep the taught lesson.** The
curriculum's `_reindex_edges` already derives fm `edges:` entries into the DB on
every scan — so no `auto` flag, no uuid5, no standalone `edges.py` module is needed.
**v6 #2 upgrade:** folded entries persist with `target_id: ""` and `write_back` re-folds
prose on every hash change — so matching needs a title fallback AND DELETE must de-type
the originating inline shorthand, or the edge resurrects inside the DELETE handler itself
(traced through `indexer.py:139` + `merge_edges`, `parser.py:204-217`).

### Change spec

1. **`db.py` — new accessor** (canonical `solutions/phase_02/src/akanga_core/db.py`, propagate 3–8):
   `get_edge(self, edge_id: str) -> dict[str, Any] | None` — `SELECT * FROM edges WHERE id = ?`
   under `self._lock`; place next to `delete_edge` (~line 377). Phase_02 *skeleton* db.py
   NOT touched (taught inline in the phase_06 skeleton docstring, like `get_edges_touching`).

2. **`server.py`** (canonical `solutions/phase_06/src/akanga_core/server.py`, propagate 7–8):
   - `RESERVED_RELATIONS = {"wikilink"}` (curriculum has no `markdown-link`; comment why).
   - Add `index_file` to the `.indexer` import (line 35).
   - Helpers (full-file rewrite style via `parse_node_file`/`write_node_file`, NOT textual splicing):
     - `_fm_edge_matches(entry: dict, relation: str, target_id: str, target_title: str) -> bool` —
       THE matching rule, shared by the dup guard and DELETE. Folded entries persist with
       `target_id: ""` forever (`write_back` writes inline edges with empty ids,
       `parser.py:196-199,247-255`; resolution happens only in the DB). Rule: relations
       equal (both `None`-normalized to `""`) AND (`entry["target_id"] == target_id` OR
       (`entry["target_id"]` empty AND `entry["target"].strip().lower() ==
       target_title.strip().lower()` — the same case rule as `resolve_wikilink`)). An empty
       `target_title` never matches the fallback branch. (After A-3 lands, the
       `entry.get(...)` reads here use N11's dual-spelling helper.)
     - `_append_fm_edge(full_path, relation, relation_id, target_title, target_id) -> bool` —
       any existing entry where `_fm_edge_matches` → `False` (the route 409s — this catches
       folded duplicates, not just API-created ones); else append entry with **underscore
       keys** (the `write_back`/`_reindex_edges` convention) → `True`.
     - `_remove_fm_edge(full_path, relation, target_id, target_title) -> bool` — remove the
       first entry where `_fm_edge_matches`; **additionally de-type the entry's originating
       inline shorthand in the body**: substitute
       `re.compile(r"\[\[\s*" + re.escape(entry_target) + r"\s*\|\s*" + re.escape(entry_relation) + r"\s*\]\]")`
       with `[[<entry_target>]]` (the fold stored the prose capture verbatim, so the
       escape-match is exact). Without this, the next `write_back` re-folds the entry from
       the prose and the edge resurrects inside the DELETE handler; with it, the user's
       prose reference survives as a plain wikilink (which legitimately yields an untyped
       `wikilink` edge on rescan). No-op for API-created edges. One atomic
       `write_node_file` carries both changes. Returns `True` if an entry was removed.
   - `create_edge` guard order: source 400 → target 400 → self-edge 400 → reserved relation
     400 → `full_path = _safe_disk_path(str(source.path))` (SEC-02; already `.resolve()`d,
     `server.py:133`) → `_append_fm_edge` False → 409 →
     **`index_file(str(full_path), get_db(), str(_vault_root()))`** (v6 #10: `_vault_root()`
     returns `Path(_app_state["vault"]).resolve()`, `server.py:100-102` — resolved on both
     sides so `index_file`'s lexical `os.path.relpath` computes a clean vault-relative
     `node.path` even across a symlinked vault) → `edge_id = upsert_edge(...)` (idempotent;
     returns the row the reindex minted — verified: conflict path returns the existing row's
     id) → existing 201 shape. Normalize `relation=None → ""` for the fm entry.
   - `delete_edge`: `get_edge` → 404 if None. If relation not reserved and the source node
     exists: `target = get_db().get_node(edge["target_id"])`;
     `full_path = _vault_root() / source.path` (stored paths are vault-relative);
     `_remove_fm_edge(full_path, edge["relation"], edge["target_id"], target.title if target else "")`
     (a vanished target degrades to id-only matching) +
     `index_file(str(full_path), get_db(), str(_vault_root()))`. Always `delete_edge(edge_id)`
     last, ignoring return. 204. Docstring: prose-derived `wikilink` edges return 204 but
     resurrect on rescan — edit the prose; typed FOLDED edges are deleted for real: the fm
     entry is removed AND the inline shorthand is de-typed, so re-indexing cannot re-fold it.

3. **Tests — `tests/phase_06/test_server.py`** (same commit — this is the un-pin):
   `test_post_edge_writes_frontmatter_entry` · `test_manual_edge_survives_db_rebuild`
   (POST edge; close app; delete db+wal+shm; new app over same vault; edge still served) ·
   `test_reindex_after_post_does_not_duplicate` · `test_post_duplicate_edge_returns_409` ·
   `test_post_self_edge_returns_400` · `test_post_reserved_relation_returns_400` ·
   `test_delete_edge_removes_frontmatter_entry` ·
   **`test_delete_folded_typed_edge_stays_dead`** (v6 #2) — vault where `a-source.md`'s BODY
   contains `[[Target Note | supports]]` and `b-target.md` exists; lifespan scan folds it
   (fm entry with `target_id: ""`, DB row with the resolved UUID — the shape pinned by
   `tests/phase_02/test_indexer.py:578-609`); DELETE the edge via the API; then
   `full_scan_and_index` again and assert: (a) NO edge with relation `"supports"` between
   the two ids (an untyped `wikilink` row is expected and allowed — the de-typed
   `[[Target Note]]` legitimately produces it), (b) the source frontmatter has no
   `(supports, Target Note)` entry, (c) the body now reads `[[Target Note]]` ·
   **`test_post_duplicate_of_folded_edge_returns_409`** — same folded fixture; POST
   `{source, target, relation: "supports"}` → 409 (the title-fallback branch).
   Where the fixture hides paths, build `create_app(vault=..., db_path=...)` directly
   (pattern: `test_lifespan_indexes_existing_vault`). Existing edge tests (lines 195–273)
   pass unchanged.

4. **Skeleton** — `skeletons/phase_06/src/akanga_core/server.py` `create_edge`/`delete_edge`
   WHAT/WHY/HOW rewritten to the file-first sequence incl. the matching rule and de-typing
   (WHY cites Phase 2's "DB is expendable"; note `get_edge` as a GraphDatabase method to
   add). Keep `NotImplementedError`.

5. **Docs**: `docs/learning/phase-06-rest-api.md` — endpoint list (~:180) gains
   "(writes frontmatter `edges:` entry, then indexes)"; "What the tests check" (~:437)
   gains the new test names; add pitfall box "DB-only manual edges violate Phase 2's
   invariant" (pre-fix bug + `rm *.db` failure mode); insert the **phase-06 "Changed
   2026-06" admonition** (text in Workstream-amendment appendix below — v6 #4c).

6. **Decision log**: N1 (amended text in the register above).

### Gate
```bash
make test-solution PHASE=2 && make test-solution PHASE=6
make sync-forward FROM=2 FILE=src/akanga_core/db.py BASE=solutions APPLY=1
make sync-forward FROM=6 FILE=src/akanga_core/server.py BASE=solutions APPLY=1
uv run python scripts/sync_forward.py --check-all
make skeleton-check PHASE=6 && make verify PHASE=8
uv run ruff check solutions/ skeletons/ tests/
uv run python scripts/check_doc_contracts.py   # A1 edits phase-06's Deliverable + endpoint list (lint check 4)
```
**Effort M.** POST/DELETE now rewrite the source file — no test asserts source-file
byte-stability after edge creation (verified). Phase-6 lifespan runs no watcher.

## A2 (F4, P1) — Pass-2 rederive-all trigger

**Decision (N2, scoped per v6 #9): port the trigger — it lives in `full_scan_and_index`
only.** The per-file watcher path (`index_file`) still re-derives only the changed node.
Hash-skip fast path untouched.

Canonical `solutions/phase_02/src/akanga_core/indexer.py`, propagate 3–8:
- `_index_node` (line 115) returns a third element `is_new = existing is None`; update
  docstring + both call sites (`index_file` :226, pass 1 :253).
- `full_scan_and_index`: pass 1 accumulates `new_files`; tombstone pass counts `removed`;
  pass 2: `rederive_all = new_files or removed > 0` → iterate `db.list_nodes(limit=10_000)`,
  reuse parsed objects for nodes in `changed`, else `parse_node_file` + force
  `parsed.id = node.id` (stored id canonical), `_reindex_edges` in the existing try/except.
- Rewrite the "Known limit" docstring (:32-34) **scoped to `full_scan_and_index`**:
  "Rederive-all trigger: when a scan adds or removes any file, pass 2 re-derives edges for
  ALL nodes (not just changed ones), so a wikilink in an unchanged file resolves as soon as
  its target appears — at the next full scan. The per-file path (`index_file`, the watcher's
  path) still re-derives only the changed node." **Keep `index_file`'s :220-221 sentence
  essentially as-is** ("A wikilink whose target is not indexed yet resolves on the next
  `full_scan_and_index`…") — it documents a limit that remains true on the per-file path;
  optionally append "(the rederive-all trigger fires because the target is a new file)".
  Do NOT delete it (v6 #9).
- Skeleton `skeletons/phase_02/.../indexer.py` `full_scan_and_index` HOW: add the trigger step.

**Tests** (`tests/phase_02/test_indexer.py`): `test_new_file_resolves_links_in_unchanged_files`
(write `a.md` with `[[Beta]]`, scan, write `b-beta.md`, scan WITHOUT touching a.md → edge A→B);
`test_rederive_all_not_triggered_on_pure_rescan` (two scans, counts stable).

## A3 (F5) — Unresolved wikilinks log a warning

**Decision (N3): warning only; stub auto-creation = doc-only stretch mention (lands with C6).**
Same file/commit as A2.
- `_reindex_edges` wikilink loop (:183-186): on `resolve_wikilink` None →
  `logger.warning("Unresolved wikilink [[%s]] in node %s — no edge created (target not indexed)", title, parsed.id)`.
- fm loop (:190-200): falsy `target_id` after both lookups → warn with relation + target
  ("entry kept in file, no edge created").
- `links.py` `resolve_wikilink` docstring (:44-47): "silently skip" → "skip-and-warn"
  (composes with A7's same-commit docstring edit).

**Tests**: `test_unresolved_wikilink_logs_warning` (caplog WARNING, no edge row);
`test_unresolvable_fm_edge_logs_warning_and_stays_in_file`.

## A7 (v6 #12a, N10) — Deterministic duplicate-title resolution

**Decision (N10): port noteapp's deterministic resolution; substitute path-order for
oldest-wins.** noteapp resolves in `get_node_by_title` with
`ORDER BY created_at ASC, id ASC` + a warning naming both nodes (mirror `db.py:180-201`);
the curriculum's `nodes` schema (`db.py:47-54`) has **no timestamp column**, and a minted
one wouldn't survive `rm *.db` rebuilds (re-mint = nondeterministic across rebuilds —
strictly worse). `ORDER BY path ASC` is the stable equivalent: `path` is NOT NULL UNIQUE
(total order), vault-relative, rebuild-identical, human-explainable. Rejected: `ORDER BY id`
(opaque UUIDs), `ORDER BY rowid` (insertion order — the roulette being fixed). Same
file/commit as A2/A3 — A2's rederive-all is precisely what would otherwise re-roll the
nondeterministic winner vault-wide on every file add/remove.

Canonical `solutions/phase_02/src/akanga_core/links.py`, propagate 3–8. Add
`import logging` + `logger = logging.getLogger(__name__)` (the module has neither today).
Replace `resolve_wikilink`'s body (:50-54):

```python
with db._lock:
    rows = db.conn.execute(
        "SELECT id, path FROM nodes WHERE lower(title) = lower(?) ORDER BY path ASC",
        (title,),
    ).fetchall()
if not rows:
    return None
if len(rows) > 1:
    logger.warning(
        "Duplicate title %r: resolving to %s (%s) — first in vault path order; "
        "shadowed: %s",
        title, rows[0]["id"], rows[0]["path"],
        ", ".join(f"{r['id']} ({r['path']})" for r in rows[1:]),
    )
return rows[0]["id"]
```

(One query, `fetchall`; `path` is UNIQUE so the order is total.) Docstring: replace
":46-47's 'first match wins — disambiguation is out of scope'" with "Duplicate titles
resolve deterministically: the node first in vault path order wins and a warning names
every shadowed duplicate (N10) — stable across `rm *.db` rebuilds, unlike insertion
order." Skeleton `skeletons/phase_02/.../links.py` `resolve_wikilink` HOW gains the
ORDER BY + warning step.

**Test** (`tests/phase_02/test_links.py` — where `resolve_wikilink` is tested today,
:113-138): `test_duplicate_title_resolves_deterministically` — upsert two nodes with the
same title at paths `b-second.md` and `a-first.md` (inserted in THAT order, so insertion
order ≠ path order — pins that the rule is path, not rowid); assert resolution returns
`a-first.md`'s id; assert a WARNING containing "Duplicate title" via
`caplog.at_level(logging.WARNING)` (match message text, not logger name). Rich failure
message per house convention.

### Gate (A-2 commit: A2+A3+A7)
```bash
make test-solution PHASE=2
make sync-forward FROM=2 FILE=src/akanga_core/indexer.py BASE=solutions APPLY=1
make sync-forward FROM=2 FILE=src/akanga_core/links.py BASE=solutions APPLY=1
uv run python scripts/sync_forward.py --check-all
make skeleton-check PHASE=2 && make verify PHASE=8
```
**Effort S+S+S.** `_index_node` arity is internal (no test imports it — verified).
`test_rescan_after_editing_one_file_changes_only_that_nodes_edges` holds.

## A4 (F2, P1) — Alias rule for the pipe grammar (+ N11 hyphen tolerance)

**Decision (N4): adopt.** Compatibility verified: spaced canonical syntax strips before
classification; all 72 vocabulary slugs + every relation used in docs/tests are snake_case
→ nothing reclassifies. Also: strip inline code in both extractors; fix escaped-pipe capture.

1. **`parser.py`** — canonical `solutions/phase_02` (propagate 3–8) AND hand-edit
   `solutions/phase_01` (pre-intro form; phase_00 has no inline-edge code):
   - New public grammar (placed with the Phase-1A section):
     ```python
     RELATION_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")
     def split_pipe_segment(segment: str) -> tuple[str, str]  # ("relation", slug) | ("alias", text)
     ```
     Docstring: THE wikilink pipe grammar; links.py defers; callers handle escaped pipes.
   - `_INLINE_CODE_RE = re.compile(r"`[^`]+`")`; `extract_inline_edges` strips fences THEN inline code.
   - Classification per `_INLINE_EDGE_RE` match: raw target ends `"\"` (escaped pipe) → skip;
     `split_pipe_segment(seg)[0] == "relation"` → emit Edge; else skip (alias — plain-wikilink
     edge is links.py's job). Update module/function docstrings with rule + examples.
2. **Dual-spelling read tolerance (N11, v6 #3).** Phase_01's parser already tolerates both
   spellings (`solutions/phase_01/src/akanga_core/parser.py:187-203`, `_edge_from_dict`'s
   `raw.get(key, raw.get(key.replace("_", "-"), ""))`). Port the same fallback to the TWO
   canonical readers:
   - `solutions/phase_02/src/akanga_core/parser.py:230-240` (`write_back`'s existing-edge
     reader): add module-level `_fm_get(raw: dict, key: str) -> str` implementing the
     phase_01 pattern; build the `Edge` from `_fm_get(d, k)` for all four keys. This kills
     the destructive case: a fold no longer rewrites a hand-authored hyphenated entry with
     empty ids — ids are read, preserved, re-serialized under underscore keys
     (**read both, write underscores**).
   - `solutions/phase_02/src/akanga_core/indexer.py:190-200` (`_reindex_edges`'s fm loop):
     same `_fm_get` helper (module-local copy — two-line helper). indexer.py is
     re-propagated in this commit (gate below).
   - **Test** (`tests/phase_02/test_indexer.py`): `test_hyphenated_edge_keys_are_read` —
     `b-target.md` (known UUID) + `a-source.md` whose fm `edges:` entry uses
     `relation-id:`/`target-id:` and whose BODY contains one unrelated typed inline link
     (forces a fold rewrite); scan; assert (i) the typed edge row exists (reader honored
     `target-id`), (ii) the re-parsed frontmatter still carries the original ids, now under
     underscore keys (fold preserved, not destroyed, them).
3. **Skeletons**: `skeletons/phase_01/.../parser.py` `extract_inline_edges` HOW gets the
   classification steps + `split_pipe_segment` as a stubbed helper with its own WHAT/WHY/HOW;
   `skeletons/phase_02/.../links.py` HOW references it.
4. **Tests**: `tests/phase_01/test_schema.py` — `test_alias_with_spaces_is_not_inline_edge`,
   `test_uppercase_segment_is_alias_not_edge`, `test_digit_first_segment_is_alias`,
   `test_escaped_pipe_never_a_relation`, `test_spaced_canonical_syntax_still_typed`
   (`[[Blink — Gladwell | contradicts]]` → relation `contradicts`),
   `test_inline_code_is_ignored`, + **`test_split_pipe_segment_table`** (parametrized, ported
   from mirror `tests/data/wikilink_cases.json`, markdown-link cases dropped — the name is
   contractual: it appears in the phase-01a Deliverable list, lint check 4).
   `tests/phase_02/test_links.py` — `test_extract_wikilinks_alias_link_returns_target`,
   `test_extract_wikilinks_ignores_inline_code`, `test_extract_wikilinks_escaped_pipe_target_clean`.
5. **Docs**: phase-01a (all in this commit):
   - Insert the alias rule after the "Inline shorthand in prose" block (:143-147); update
     the `extract_inline_edges` function-table row (:187).
   - **Hyphen→underscore canonical block (v6 #3)**: in the YAML block (:121-131),
     `relation-id:` → `relation_id:` and `target-id:` → `target_id:` (×2 each); same in the
     four prose mentions (:135, :137, :139, :145). Add one sentence after the block:
     "Underscore keys are canonical (they match the `Edge` dataclass fields below);
     hyphenated spellings found in hand-authored vaults are tolerated on read (N11) and
     normalized to underscores on the next write-back." (The `Edge` dataclass at :169-176
     already uses underscores — no change.)
   - **Registry location fix (v6 #7)**: `:181` "The relation registry (in `akanga.yaml` or
     `vocabulary.yaml`) maps IDs to names…" → "The relation registry
     (`docs/foundations/relation-vocabulary.md`) maps IDs to names…" — B4's rewritten yaml
     tail (Stage 7) asserts "Relation types do NOT live here"; A4 lands at Stage 3, so the
     contradiction never exists on main.
   - **Function table (v6 #4b)**: add a row under `extract_inline_edges`:
     `` | `split_pipe_segment(segment) → tuple[str, str]` | Classify a pipe segment: `("relation", slug)` when it matches `^[a-z][a-z0-9_-]*$` after strip, else `("alias", text)` | ``
     (legal under lint check 5 only because the skeleton stub lands in this same commit).
   - **Deliverable (:199-200, v6 #4b)**: de-count the brittle total — "(15 tests; the names
     differ)" → "(the names differ)". Append the seven new test names incl.
     `test_split_pipe_segment_table`.
   - Insert the **phase-01a "Changed 2026-06" admonition** (appendix below).
   - One sentence (with A5): "a typed link produces exactly one edge — the typed one."

### Gate (A-3 commit: A4+A5+N11)
```bash
make test-solution PHASE=1 && make test-solution PHASE=2
make sync-forward FROM=2 FILE=src/akanga_core/parser.py BASE=solutions APPLY=1
make sync-forward FROM=2 FILE=src/akanga_core/links.py BASE=solutions APPLY=1
make sync-forward FROM=2 FILE=src/akanga_core/indexer.py BASE=solutions APPLY=1   # N11
uv run python scripts/sync_forward.py --check-all
make skeleton-check PHASE=1 && make skeleton-check PHASE=2
make verify PHASE=1 && make verify PHASE=2   # hand-edited solutions/phase_01 is unmanifested — verify PHASE=8 never exercises it
make verify PHASE=8
uv run python scripts/check_doc_contracts.py   # A4+A5 edit phase-01a in this commit
```
**Effort M.** Phase_01 parser.py is hand-edited — the `extract_inline_edges` bodies must end
up textually identical across phase_01/phase_02. No phase 3–8 fixture feeds non-slug pipes
(grep-verified).

## A5 (F10) — `[[A|relation]]` produces ONE edge

**Decision (N5): accident — port single-edge.** Same commit as A4 (needs `split_pipe_segment`).

Canonical `solutions/phase_02/src/akanga_core/links.py`:
- `_WIKILINK_RE` → `r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]"`; `extract_wikilinks` switches to
  `finditer`. No segment → include; escaped pipe → strip backslash, include (alias);
  `("relation", _)` → **skip** (typed edge owned by the fold pipeline); `("alias", _)` → include.
- Update module + function docstrings: typed links contribute NO wikilink edge.

**Tests**: `test_extract_wikilinks_skips_typed_relation_links` (`[[Flow State | supports]]` → `[]`);
strengthen `test_inline_typed_edge_folds_on_index` to `relations == {"supports"}` (the formal
un-pin, with failure message explaining single-edge semantics);
`test_typed_link_yields_exactly_one_edge_row` (count == 1 after two scans).

## A6 (F3, P1) — Single slugify + collision-safe create()

**Decision (N6).** New module adapted verbatim from mirror `textutil.py` (drop the nvim
sentence): `slugify` (lowercase, collapse `[^a-z0-9]+` runs to `-`, strip edges, `"untitled"`
fallback) + `unique_path(vault, slug, ext=".md")` (numeric suffixes starting at `-1`).

1. **Entry point: Phase 0.** Copies `solutions/phase_NN/src/akanga_core/textutil.py` for
   NN ∈ {00..08}, all byte-identical.
2. **Manifest** (same commit, or completeness fails):
   ```toml
   [[modules]]
   file = "src/akanga_core/textutil.py"
   introduced_in = 0
   applies_to = [0, 1, 2, 3, 4, 5, 6, 7, 8]
   ```
3. **Call sites**: `solutions/phase_00/.../parser.py` (~:126) and `phase_01/.../parser.py`
   (delete `_SLUG_STRIP_RE`/`_slugify` :47-48, :248-256) — hand-edits. Canonical
   `phase_02/.../parser.py` :173-174 → `target = unique_path(str(vault), slugify(title))`
   (**fixes the silent overwrite**); propagate 3–8. `phase_06/.../server.py` :235 →
   `body.path or f"{slugify(body.title)}.md"`; keep the 409; propagate 7–8.
   `phase_08/src/akanga_mcp/server.py` — delete `_slugify` (:129-138); switch the collision
   loop (:208-213) to **`target = Path(unique_path(str(vault_root), slug))`** (v6 #10:
   `unique_path` returns `str`; the next statement calls `target.resolve()` — the bare
   string would `AttributeError` on every `create_node`). Drop the ValueError branch
   (`"untitled"` fallback covers it). **Behavior change noted**: the MCP loop's suffix
   series starts at `-2` today; `unique_path` starts at `-1` — nothing pins the old series;
   `-1,-2,…` is now the single cross-surface convention.
4. **Skeletons**: NEW `skeletons/phase_00/src/akanga_core/textutil.py` stub (WHAT/WHY/HOW
   for both functions; WHY = three surfaces minting different filenames is silent
   divergence + collision-unsafe slug silently overwrites notes). Update create() HOW step 4
   in skeletons/phase_00 + phase_01 parser.py; update `skeletons/phase_08/src/akanga_mcp/server.py`
   :241-249 HOW (SEC-02 note stays). No later-phase skeleton markers needed (verified).
5. **Tests**: NEW `tests/phase_00/test_textutil.py` — loader via `tests/_helpers.load_attr`;
   **`test_slugify_conformance_table`** (parametrized, all 16 cases inlined byte-identical
   from mirror `tests/data/slug_cases.json`, comment credits the source — the name is
   contractual: lint check 4 vs the phase-00 Deliverable edit below) +
   `test_unique_path_no_collision` + `test_unique_path_suffixes_in_order`. NEW
   `tests/phase_00/test_parser.py::test_create_same_title_twice_does_not_overwrite` (two
   creates → two files, first intact). Inspect `tests/phase_08/test_mcp.py` for old-slug
   pins during execution (grep found none).
6. **`__init__.py` rosters**: each phase's `__init__.py` docstring roster gains a `textutil`
   line — 9 intentionally-divergent one-line hand-edits ([[ignore]] entry, no propagation).
7. **Docs — phase doc (same commit; v6 #4a/#4d/#12c)**:
   `docs/learning/phase-00-file-system-as-database.md`:
   - **What You Build (:214-223)**: lead line "Single module: `parser.py`" → "Two modules:
     `parser.py` and `textutil.py`"; add two rows after the `content_hash` row:
     `` | `slugify(title) → str` | Lowercase; collapse non-alphanumeric runs to `-`; strip edge hyphens; `"untitled"` fallback | ``
     `` | `unique_path(vault, slug) → str` | First free filename: `slug.md`, then numeric suffixes — never overwrite an existing note | ``
     (omit `ext=".md"` — lint check 1 allows omitting trailing defaulted params). Amend the
     `create()` row's tail: "…stamps `author` from `akanga.yaml`; filename via `textutil` —
     collision-safe". Legal under check 5 only because item 4's skeleton stub lands in this
     same commit — do not split.
   - **Deliverable (:306)**: "…runs `tests/phase_00/test_parser.py`." → "…runs
     `tests/phase_00/test_parser.py` and `tests/phase_00/test_textutil.py`." Add
     `test_create_same_title_twice_does_not_overwrite` to the **Creating** list; add a new
     group: **Slug + collision safety (`test_textutil.py`)**: `test_slugify_conformance_table`,
     `test_unique_path_no_collision`, `test_unique_path_suffixes_in_order`.
   - **Conformance-table tip (v6 #12c)**: directly under the amended suite line, insert:
     ```
     !!! tip "Testing pattern: the conformance table"
         `test_textutil.py` asserts one JSON table of input→expected-slug cases instead of
         hand-writing a test per case. The payoff is that SEVERAL implementations can assert
         the SAME table: noteapp replays its shared wikilink case table through both its
         Python core and its TypeScript mirror (and pins its Lua slug mirror to the Python
         source), so the surfaces can't drift apart silently. One table beats N parallel
         hand-written suites — adding a case upgrades every implementation's coverage at
         once. The 16 slug cases are inlined at the top of `tests/phase_00/test_textutil.py`;
         read them before implementing `slugify`.
     ```
   - Insert the **phase-00 "Changed 2026-06" admonition** (appendix below).
   - **phase-06 collision-policy sentence (v6 #4d)** — `docs/learning/phase-06-rest-api.md`:
     append to the "**Why `path` is in the request model:**" paragraph (:357-362):
     "One deliberate asymmetry: an explicit `path` that already exists gets **409 Conflict**
     rather than a suffixed filename — a REST client stated exact intent and can retry with
     a different path — while `create()` and the MCP `create_node` auto-suffix
     (`my-note-1.md`), because a capture utility must never lose a note to a name collision
     (decision N6)." Also append ", 409 Conflict" to the status-code roll-call at :58
     (phase-06 contains no "409" today — this sentence introduces it).

### Gate (A-4 commit)
```bash
make test-solution PHASE=0 && make test-solution PHASE=1 && make test-solution PHASE=2
make sync-forward FROM=0 FILE=src/akanga_core/textutil.py BASE=solutions APPLY=1
make sync-forward FROM=2 FILE=src/akanga_core/parser.py BASE=solutions APPLY=1
make sync-forward FROM=6 FILE=src/akanga_core/server.py BASE=solutions APPLY=1
uv run python scripts/sync_forward.py --check-all
make skeleton-check PHASE=0 && make skeleton-check PHASE=1 && make skeleton-check PHASE=8
make verify-all && make examples-all   # NOT verify PHASE=8: A6 hand-edits phase_00/01 and fans textutil into all nine trees
uv run python scripts/check_doc_contracts.py   # phase-00 + phase-06 doc edits
```
**Effort M** — widest fan-out. Slug output changes for punctuated titles; no fixture pins
old slugs (verified). Post-push, CI's `transition` job (`.github/workflows/ci.yml:111`) is
the check for the new skeleton stubs — it walks every phase boundary with the previous
solution + merged skeleton, which no local gate reproduces (v6 #11).

### "Changed 2026-06" admonition texts (v6 #4c — insert after line 3, `**Estimated time**`, of each doc)

**phase-00-file-system-as-database.md** (commit A-4):
```
!!! warning "Changed 2026-06 (noteapp-alignment round)"
    Phase 0's contract grew: a new `textutil.py` module (`slugify` + `unique_path`) is now
    the single title→filename rule, and `create()` must never overwrite an existing note
    (collisions get numeric suffixes: `my-note-1.md`). New tests: `tests/phase_00/test_textutil.py`
    plus `test_create_same_title_twice_does_not_overwrite`. If you finished this phase before
    the change: run `make skeleton PHASE=0` — it copies the new `textutil.py` stub and never
    touches files you already own — then implement the two functions and route `create()`
    through them. A green recorded by `make resume` before this change predates these tests.
```

**phase-01a-data-modeling-edge-schema.md** (commit A-3):
```
!!! warning "Changed 2026-06 (noteapp-alignment round)"
    The pipe grammar changed: a pipe segment is a relation only when it matches
    `^[a-z][a-z0-9_-]*$` (after strip) — spaces, uppercase, digit-first, or an escaped `\|`
    now mean an Obsidian-style display alias, which yields a plain wikilink instead. The
    grammar lives in one new public helper, `split_pipe_segment`, and a typed link now
    produces exactly ONE edge (the typed one). Seven new tests in `tests/phase_01/test_schema.py`.
    If you finished this phase before the change: run `make skeleton PHASE=1` — the merge
    appends the new `split_pipe_segment` stub into your `parser.py` without modifying your
    code — then implement the classification and update `extract_inline_edges` to use it.
```

**phase-03-graph-algorithms.md** (commit C-4):
```
!!! warning "Changed 2026-06 (noteapp-alignment round)"
    `build_ego_graph` gained a node budget: a `limit` keyword (default `None` = the old
    unbounded behavior) and an `EgoGraph.truncated` flag. Your existing implementation still
    passes every pre-existing test, but the two NEW tests call `build_ego_graph(..., limit=3)`
    and read `ego.truncated` — a previously green Phase 3 FAILS them (TypeError, then
    AttributeError) until you add both. See the new "Node Budget (Supernode Guard)" concept
    and the updated traversal block; `make skeleton PHASE=3` will print a signature-change
    notice but cannot edit your file — the small addition is yours to make.
```

**phase-06-rest-api.md** (commit A-1):
```
!!! warning "Changed 2026-06 (noteapp-alignment round)"
    Manual edge endpoints became file-first: `POST /api/v1/edges` now writes an `edges:`
    entry into the source note's frontmatter and reindexes (DELETE removes the entry), with
    new guards — 400 for self-edges, the reserved `wikilink` relation, or missing endpoints;
    409 for duplicates. New tests in `tests/phase_06/test_server.py`, including one that
    deletes the DB and asserts the edge survives. If you finished this phase before the
    change: rework `create_edge`/`delete_edge` per the rewritten WHAT/WHY/HOW in
    `skeletons/phase_06/src/akanga_core/server.py` (re-running `make skeleton PHASE=6`
    cannot update docstrings inside files you already own — open the skeleton file directly),
    and add the small `get_edge` accessor to your `GraphDatabase`.
```

(Verified: `make skeleton` copies only files absent from src/ and `skeleton_merge.py` is
append-only with a signature-collision notice — the phase-00/01a "non-destructive" claims
are TRUE; phase-03/06 deliberately do NOT claim the merge delivers the change. Test names
inside admonitions are lint-safe: check 4 only harvests `## Deliverable` sections.)

### Copy-inventory appendix

| Module | Solution copies | Skeleton stubs | Manifest | Touched by |
|---|---|---|---|---|
| `parser.py` | 00, 01 (pre-intro, hand-edit); **02 canonical**; 03–08 | 00, 01, 02 real; 03–08 markers | `introduced_in=2, [2..8]` | A4, A6 |
| `links.py` | **02 canonical**; 03–08 | 02 real; 03–08 markers | `[2..8]` | A3, A4, A5, A7 |
| `indexer.py` | **02 canonical**; 03–08 | 02 real; 03–08 markers | `[2..8]` | A2, A3, A4(N11) |
| `db.py` | **02 canonical**; 03–08 | 02 real (untouched); markers | `[2..8]` | A1 |
| `server.py` | **06 canonical**; 07, 08 | 06 real; 07–08 markers | `[6,7,8]` | A1, A6 |
| `akanga_mcp/server.py` | 08 only | 08 real | single-copy | A6 |
| `textutil.py` (NEW) | 00–08 byte-identical, **00 canonical** | 00 new stub | NEW `[0..8]` | A6 |
| `__init__.py` | 00–08 divergent rosters | — | `[[ignore]]` | A6 |

---

# Workstream B — Documentation correctness

Execution order: B1 → B2 → B3 → B4 → B5+B6 → B7 → B8.

## B1 — 71→72 sweep + inverse recount (Commit B-1, Effort M)

**Derivations (verified, reproduced by code in v6):** registry = exactly 72 unique ID-first
rows; 12 symmetric; 4 pairs/8 members; **52 of the 72 have no defined inverse**. The
phase-08 runtime parse yields exactly 72 (no double-counting). Internal inconsistency:
`:118-119` flag SC-005/SC-006 as `↔` inverses but the Pairs section correctly omits them
(complementary, not inverses) — fix the flags; `:335` "(the other 56 directed types)" → 52.

**Edit table (old → new):**

| Location | Edit |
|---|---|
| `relation-vocabulary.md:118-119` | SC-005/SC-006 `↔` flags → empty; add note below the SC table: "**Note:** `satisfies` and `verifies` are complementary (both point at the requirement), not inverses." |
| `relation-vocabulary.md:335` | "the other 56 directed types" → "the other 52 directed types" |
| `phase-01a:73` / `:79` | "71-type vocabulary" → "72-type" (×2) |
| `phase-01b:154` | "neither in the 71-type registry" → 72 |
| `phase-03:240` | "71-type relation vocabulary" → 72 |
| `phase-08:16` | "71 typed edges is a structural asset" → "72 typed relations…" |
| `phase-08:237` | "The 71-type vocabulary only" → 72 |
| `phase-08:437,445` | docstring/comment "71" → 72 (×2) |
| `phase-08:534` | "51 of the 71 … no defined inverse" → "52 of the 72 …" |
| `phase-08:575` | Deliverable line → `` `test_list_relation_types_returns_72` — the full 72-type registry (the test asserts all 72; learner-defined custom types may append beyond)`` |
| `design-patterns.md:175,187,194` | "71-type" → "72-type" (×3) |
| `tests/phase_08/test_mcp.py:372-388` | rename `test_list_relation_types_returns_71` → `_72`; docstring 71s → 72; `assert len(result) >= 71` → `>= 72` + message |
| `tests/phase_08/test_rag.py:337` | "(51 of the 71 directed types" → "(52 of the 72 relation types" |
| `tests/phase_02/test_db.py:262` | "guts the 71-type vocabulary" → 72 |
| `skeletons/phase_02/src/akanga_core/db.py:406` | 71 → 72 |
| `skeletons/phase_08/src/akanga_mcp/server.py:20,37,160,171,175,196` | 71 → 72 (×6) |
| `skeletons/phase_08/src/akanga_core/rag.py:150` | "51 of the 71" → "52 of the 72" |
| `skeletons/phase_08/README.md:56` | "(71 entries)" → "(72 entries)" |
| `solutions/phase_02/src/akanga_core/db.py:445` | 71 → 72, then **sync-forward 2→8** |
| `solutions/phase_03/src/akanga_core/graph.py:16` | 71 → 72, then **sync-forward 3→8** |
| `docs/roadmap.md:37`, `docs/facilitator-guide.md:259`, `docs/plan-kg-theory-and-integration.md:22`, `scripts/validate_vault.py:10` | 71 → 72 |
| `docs/index.md:65` | "the 71 built-in relation types" → 72 |
| `docs/plan-kg-theory-and-integration.md:157` (v6 #7) | YAML comment `# ... existing 71 entries unchanged ...` → `72` (B1 already edits this file at `:22` — never half-fix a file) |
| `docs/implementation-plan.md:115` (v6 #7) | `[DONE — 71 built-in relation types]` → 72. README:44 labels the file "historical sprint plan (stale)", but it is NOT on the frozen list — **decision: fix it** (one token; avoids growing a frozen-file allow-list for a live count) |

**Deliberately untouched:** `docs/adversarial-analysis*.md` (incl. v6),
`docs/status-remediation.md:342`, `docs/analysis-and-enhancements.md:150` (frozen historical
logs — the registry's `:10-11` note covers them); `relation-vocabulary.md:10-11` itself;
`docs/archive/` (superseded, site-excluded); `docs/noteapp-alignment-audit.md` and
`docs/plan-noteapp-alignment.md` (round artifacts that quote pre-fix text).

**Gate**: sync-forward db.py(2→)/graph.py(3→) → `--check-all` → `check_doc_contracts.py`
(test rename atomic with the Deliverable line — lint check 4) → `test-solution 2,8` →
the **final-gate grep command** (path-`--exclude` form, quoted in the Execution sequence
section — NEVER the content-pipe `| grep -v relation-vocabulary`, which hides
index.md:65, phase-01a:79, phase-08:445, implementation-plan:115) → zero;
`grep -rn 'the other 56\|returns_71'` → zero.

## B2 — Phase 3 traversal rewrite (Commit B-2, Effort M)

**Verified:** `phase-03:182-230` does `edge.target_id` attribute access; the real contract
(D7) is `get_edges_from/to → list[tuple[NodeRecord, str, str]]` where the node is the
*neighbour*. Also wrong: `:116-117` ("return full edge rows") and `:169` (`Node` → `NodeRecord`).

**Edits:**
1. `:116-117` → "Phase 2's `get_edges_from(node_id)` / `get_edges_to(node_id)` return
   `(neighbour_node, relation, relation_id)` **tuples** — the neighbour `NodeRecord` travels
   with the labels, so the relation comes for free during traversal (and you never need a
   second `get_node` lookup for a neighbour)."
2. `:169` → `root: NodeRecord` / `nodes: dict[str, NodeRecord]  # the DB read model — six fields, no content`.
3. Replace the fenced block `:182-230` with the corrected reference implementation
   (verified in v6 as semantically identical to `solutions/phase_03/graph.py` — same dedup
   key, boundary semantics, field/enum names; signature unchanged → lint check 1 green;
   helper `_record` → checks 1/5 skip it):

```python
def build_ego_graph(root_id: str, db: GraphDatabase, max_depth: int = 2) -> EgoGraph:
    root = db.get_node(root_id)
    if root is None:
        raise ValueError(f"Node {root_id!r} not found")

    nodes      = {root_id: root}
    edges      = []
    seen_edges = set()   # dedup key: (source_id, target_id, relation)
    visited    = {root_id}
    queue      = deque([(root_id, 0)])

    def _record(source_id, target_id, relation, relation_id, direction):
        key = (source_id, target_id, relation)
        if key in seen_edges:
            return       # BFS reaches both endpoints — add each logical edge once
        seen_edges.add(key)
        edges.append(EgoEdge(source_id=source_id, target_id=target_id,
                             relation=relation, relation_id=relation_id,
                             direction=direction))

    while queue:
        current_id, depth = queue.popleft()
        if depth >= max_depth:
            continue   # include the node but don't expand further

        # Outgoing — get_edges_from returns (target_node, relation, relation_id)
        # TUPLES (Phase 2 API): unpack them; the neighbour NodeRecord is the
        # first element, so no extra get_node() lookup is needed.
        for node, relation, relation_id in db.get_edges_from(current_id):
            if node.id not in visited:
                visited.add(node.id)
                nodes[node.id] = node
                queue.append((node.id, depth + 1))
            _record(current_id, node.id, relation, relation_id, EdgeDirection.OUTGOING)

        # Incoming — get_edges_to returns (source_node, relation, relation_id):
        # the OTHER node is the edge's source. Natural direction is preserved;
        # only the direction flag differs.
        for node, relation, relation_id in db.get_edges_to(current_id):
            if node.id not in visited:
                visited.add(node.id)
                nodes[node.id] = node
                queue.append((node.id, depth + 1))
            _record(node.id, current_id, relation, relation_id, EdgeDirection.INCOMING)

    return EgoGraph(root=root, nodes=nodes, edges=edges)
```

Keep the ":180 written out explicitly" lead-in and everything after `:230`.
**C4 (stage 11) amends this same block** (adds `limit`/`truncated`) — code, skeleton, and
doc block in ONE commit (doc-first split trips lint check 1).

**Gate**: `check_doc_contracts.py`; `grep -n 'edge\.target_id\|edge\.source_id\|edge\.relation'
docs/learning/phase-03-graph-algorithms.md` → zero; `make test-solution PHASE=3`.

## B3 — sqlite-basics FTS5 rewrite + phase-02 DB_SCHEMA block (Commit B-3, Effort M)

**Verified:** `sqlite-basics.md:172-220` shows an FTS table with `id UNINDEXED` + a prose
`content` column and teaches plain `DELETE FROM nodes_fts` — wrong twice for external-content
tables. Real schema: `fts5(title, tags, content='nodes', content_rowid='rowid')`. Correct
mechanism: `skeletons/phase_02/.../db.py:154-196` / `solutions/phase_02/.../db.py:204-248`.

**Replace `:170-220`** with three subsections:
1. *Creating an FTS5 virtual table (external content)* — the exact Phase-2 table; bullets:
   title+tags only, never the prose body (bodies = ripgrep's job); `content='nodes'` =
   external-content (FTS5 stores only the inverted index; sync is YOUR job).
2. *Searching with MATCH* — join back through rowid:
   `SELECT nodes.id, nodes.title FROM nodes JOIN nodes_fts ON nodes.rowid = nodes_fts.rowid
   WHERE nodes_fts MATCH ? ORDER BY nodes_fts.rank;` (keep the existing MATCH bullets + rank
   paragraph — correct).
3. *Keeping external-content FTS5 in sync — the `'delete'`-command dance* — the four-step
   pattern inside ONE locked transaction: fetch OLD row BEFORE upsert (its title/tags are
   the tokens FTS5 must retract; INSERT OR REPLACE destroys them and assigns a NEW rowid) →
   upsert → `INSERT INTO nodes_fts(nodes_fts, rowid, title, tags) VALUES('delete', old…)` —
   wrong values corrupt the index → insert new tokens under the new rowid. Close with
   pointers to `GraphDatabase.upsert_node`/`delete_node` and the skeleton walkthrough.

**Same commit — phase-02 `:247-280`**: the block claims "the exact `DB_SCHEMA` constant"
but omits `UNIQUE (source_id, target_id, relation)` and both `CREATE INDEX` lines. Insert
the three lines, making it byte-equal to the skeleton constant's body.

**Gate**: `check_doc_contracts.py`; `grep -n "DELETE FROM nodes_fts\|id UNINDEXED"
docs/foundations/sqlite-basics.md` → zero; diff the doc DB_SCHEMA block vs skeleton.

## B4 — yaml-and-markdown-frontmatter.md tail rewrite (Commit B-4, Effort M)

**Verified:** `:471-559` describes noteapp's schema (`note|active|active-service|diagram|virtual`,
path-keyed workspaces, an akanga.yaml `relations:` list). Ground truth: phase-00 `:240-291`
(D3: `type: "note" | "reference"`), canonical akanga.yaml phase-00 `:174-185`, registry =
relation-vocabulary.md + UUID-minted custom types.

**Replace `:471-559`** (three sections; Quick Reference table from `:563` stays) with the
curriculum-true versions (full drafted replacement in the Rev-1 workstream output): node
frontmatter example with `id`/`title`/`type: note`/`tags`/`graph:` (dual-key)/`author`/dates/
`meta:`/`edges: []` + five key-decision bullets; canonical `akanga.yaml` + safe_load read
example + "Relation types do NOT live here" sentence; "In Your Implementation" rewritten to
`parse_node_file`/`write_node_file`/`create()` + Phase 1B workspace registry + "never
`yaml.load` without SafeLoader". Removes the tail's active-manager mention (:499).
**Cross-check:** phase-1B `:162-167` `custom_relations:` deferred-spec framing (B7e) must
not be contradicted — "no pre-registration required" agrees.

**Gate**: `grep -n "active\|virtual\|diagram\|external_type" docs/foundations/yaml-and-markdown-frontmatter.md`
→ no schema hits in the tail; `uv run mkdocs build`. **C5c lands after this, same region.**

## B5 — asyncio-primer drift (Commit B-5, with B6, Effort M)

**Verified:** references to `ActiveNodeManager`/`active.py`/`aiohttp`/`AkangaApp.start_all`
(`:105,158-166,174,224-226,249-257,312-313`) — none exist in solutions/skeletons. The
`publish()` pseudocode (`:204-218`) **drops** pre-loop events, contradicting D6's buffering
contract (`solutions/phase_04/.../eventbus.py`).

**Edits** (full replacement text in the Rev-1 workstream output): `:105` → FastAPI-tasks
framing + "(an earlier active-node design was cut; see future-ideas.md)"; `:158-166` →
generic `create_task` example (keep-a-reference note); `:174` → "EventBus subscribers can
be async"; `:199-228` → the REAL three-rule dispatch contract (async+loop →
`run_coroutine_threadsafe` + done-callback logging; async+no-loop → **buffered, never
dropped**, drained FIFO by `set_loop`; sync → direct call in try/except) with pseudocode
matching `publish(self, event, **kwargs)` and the locked loop-check/buffer-append;
`:249-257` → real Phase 6 lifespan shape; `:309-314` table → watcher.py/server.py rows.

## B6 — Active-manager ghost sweep (Commit B-5, Effort S — extended per v6 #7)

One-sentence treatment per occurrence: `phase-04:6` (drop "active manager pings URLs"),
`:80-81`, `:275` (`app.py`/`AkangaApp` → "there is no app.py — you wire this inside Phase
6's create_app lifespan"); `phase-02:77`, `:143`, `:286-287` (`active_results` table → "a
deferred extension no phase builds — see future-ideas.md"); `phase-06:72`, `:82-83`, `:103`
(drop `active_result` event), `:314,317` (delete the two `active_manager` lifespan lines —
block marked illustrative, lint-safe); **`phase-06:191` (v6 #7 — DELETE the stretch-endpoint
line `GET /api/v1/nodes/{id}/results — active check results`: a ghost endpoint of the cut
active manager; B6 owns this even though C4 edits the adjacent `:190`)**;
**`json-rpc-basics.md:296-298` (v6 #7)**: `When you ask Claude "what are my active nodes?",
Claude decides to call the search_nodes tool with type="active".` → `When you ask Claude
"what do I have tagged psychology?", Claude decides to call the search_nodes tool with
query="psychology".` (the real tool is `search_nodes(query: str)` — it has NO `type`
parameter); `design-patterns.md:134,136,139-144` (replace ghost constructors with
`VaultWatcher`/`GraphDatabase`/`create_app` examples), `:155` (§7 Strategy relabeled
"deferred design — no phase builds active.py; see future-ideas.md"), `:238,241,243` (table
rows); **plus the v6 gate-consistency additions: `design-patterns.md:19` (drop "the active
node manager, " from §1's consumer list), `:39` (§2 Where → `watcher.py` —
`_EventHandler._debounced()` only), `:107-120` (§5 "Facade — AkangaApp" → "Facade —
create_app", `server.py` — `create_app()`, body rewritten around the real lifespan wiring,
reusing B5's lifespan shape)**.

**Gate (B5+B6)**:
```bash
grep -rnE 'active manager|active_manager|ActiveNodeManager|AkangaApp|start_all|active check|active_result|type="active"|active node' docs/learning docs/foundations
```
Expected output — **exactly one hit**:
`docs/learning/phase-05-terminal-ui.md:488` — `AkangaApp` as the alternate TUI class name.
**Do not edit — test-pinned**: `tests/phase_05/test_tui.py:42-44` loads
`("akanga_tui.app", "AkangaApp")` / `("tui", "AkangaApp")` as accepted aliases.
Any other hit = a missed ghost; fix before commit. (Known deliberate pattern escapes:
design-patterns §7's relabeled "Active nodes…" body and asyncio-primer's "an earlier
active-node design was cut" line — both intentionally invisible to the pattern.)
Then `uv run python scripts/check_doc_contracts.py`; `uv run mkdocs build` (strict).

## B7 — Small fixes + glossary (Commit B-6, Effort S)

- **(a) phase-07:324** — replace the "per-key timer pattern" sentence: "This is Phase 4's
  debounce design again — a monotonic deadline that every new event pushes forward, checked
  by a single worker — with one twist: there is only one key (the whole vault), not one per
  path. Do not reach for a `threading.Timer` per change; that is exactly the anti-pattern
  Phase 4's Common Pitfalls names."
- **(b)** folded into B3.
- **(c) http-fundamentals.md:247** — replace `return vars(node)` with the explicit dict +
  comment "NOT vars(node): the DB layer's records are slots dataclasses (no `__dict__`), so
  vars() raises TypeError — build the dict explicitly (Phase 6's rule)."
- **(d) phase-00:128** — "renames the inode" → "repoints the directory entry at the temp
  file's inode (names live in the directory, not in the inode)".
- **(e) phase-1B:144-176 Relation Hygiene — mark as SPEC, don't implement** (verified:
  `scripts/validate_vault.py:295-320` implements the soft check; `write_back` has none;
  nothing reads `custom_relations:`). Three edits: `:153-159` reframe to "the contract is
  soft validation… today this check lives in `make vault-check`"; `:163-171` prefix
  "*Future work (not built in this learning path):*" and reword pre-registration as
  deferred spec (keep the YAML snippet); `:172-176` → "The second deferred half is moving
  the same check into `write_back` itself… both halves specced for completeness and
  deliberately deferred."
- **(f) Glossary one-liners**: ripgrep (phase-02:131), slugify (phase-06:358 +
  http-fundamentals:243), Tauri (phase-06:8), anti-entropy (phase-1B:190), force-directed
  (phase-05:133), Bresenham (phase-05:140), supersampling (phase-05:146).

**Gate**: `check_doc_contracts.py`; greps for "per-key timer", "vars(node)", "renames the
inode" → zero; `mkdocs build`.

## B8 — Lint pin + handoff log (Commit B-7, Effort S)

1. **Extend `scripts/check_doc_contracts.py` with check 6 — RELATION-COUNT DRIFT** (~35
   lines, existing `Finding` plumbing): derive `registry_count` by counting unique ID-first
   rows in relation-vocabulary.md (currently 72); scan phase docs + `docs/foundations/*.md`
   (excluding relation-vocabulary.md) for `(\d{2,3})(-type|…relation types?|…typed relations?)`
   and the **context-anchored** `of the (\d{2,3})(?=\s+(?:relation|typed|directed|have no))`
   (v6 #6 — the bare `of the (\d{2,3})` form is FORBIDDEN: it false-positives on node
   counts). Any captured number ≠ registry_count → error ("relation-vocabulary.md is the
   registry — fix the doc"). **Known-negative test case (pin in the check's self-test/
   comment — must NOT match):** phase-08:106 "roughly 22 of the 170 consume the whole
   12,000-char budget". **Known-positive (must match → 72 post-B1):** phase-08:534 "52 of
   the 72 relation types have no defined inverse". Support `ALLOW` entries
   `relcount:<filename>:<number>` (expected to stay empty).
2. **`docs/status-remediation.md`** — append the round section: N1–N11 entries (register
   above) + the Workstream-B prose log (71→72 sweep with the 52-of-72 recount and
   SC-005/006 flag fix; phase-03 tuple-contract rewrite; FTS5 'delete'-dance rewrite; yaml
   tail rewrite; asyncio D6 contract; extended ghost sweep; small fixes; lint check 6; v6
   #12b/c resolved by adoption — the F5 stub-creation TEACH half ships as a Phase 2
   "Stretch (untested)" mention (C6 commit) and the F9/F11 conformance-table sidebar ships
   with A6's phase-00 doc edits — both folded into N9's doc-only batch).
   **Also (v6 #8): insert one line directly under the header `# NOTEAPP SYNC — Cross-repo
   port batch (2026-06-12)` (status-remediation.md:354):**
   > **Superseded note (2026-06-12, second pass):** a full alignment audit
   > (`docs/noteapp-alignment-audit.md`) found core-integrity gaps invisible to this
   > section's classification — file-first manual edges (F1, a P0) among them. "Most
   > core-integrity fix classes were already absorbed" no longer stands; see the
   > NOTEAPP ALIGNMENT (N-series) section below.

---

# Workstream C — New content

All C items match verified curriculum conventions. Citation policy for C1/C2: no inline
citations — house pattern is a closing "Further Reading" list (≤6 links).

## C1 — `docs/foundations/graph-theory-basics.md` (NEW, required tier; Effort M, ~2,000 words)

Source: adapt mirror `04-graphs-for-engineers.md`, every example rewritten onto the real
schema. Header: `**Audience:** Python devs who know dicts, lists, and basic SQL — no prior
graph theory · **Read time:** ~15 min`.
**Commit includes its own `mkdocs.yml` nav entry** (strict mode fails otherwise) — gate:
`uv run mkdocs build`.

Sections (key claims each — full detail in the Rev-1 output):
1. Framing: "you have been building a graph since Phase 1A; this names what you built."
2. *Graph = the general case* — linked list/tree as constrained graphs; generality is why
   graphs feel harder; everything after re-imposes discipline.
3. *Four representations + cheat sheet* — adjacency list (dict-of-lists, O(V+E)); matrix
   (O(V²)); edge list ("the wire format — what C9's Mermaid export emits"); CSR (named, not
   built). Mirror's table + a fifth "SQL edge table" row.
4. **Centerpiece: *Your edges table IS an adjacency list*** — the real `CREATE TABLE edges`
   + the two indexes as exactly what makes neighbors/backlinks range scans; `relation`
   column = multigraph for free; the recursive-CTE bounded BFS against real columns:
   ```sql
   WITH RECURSIVE reachable(id, depth) AS (
     SELECT :root_id, 0
     UNION
     SELECT e.target_id, r.depth + 1
     FROM edges e JOIN reachable r ON e.source_id = r.id
     WHERE r.depth < 2 AND e.target_id IS NOT NULL
   )
   SELECT DISTINCT n.* FROM nodes n JOIN reachable r ON n.id = r.id;
   ```
   Teach: the depth cap IS the cycle guard (verified live: the no-cap variant never
   terminates); `UNION` dedups; `target_id IS NOT NULL` because unresolved links leave NULL.
5. *Flavors* — directed, weighted (typed relations → C2 PPR), DAGs/topo-sort.
6. *Supernodes* — skew is inevitable; quote the curriculum's own published number — **phrase
   the 170 figure WITHOUT "of the" directly before the number** (e.g. "a depth-2 ego graph
   around a hub reaches ~170 nodes at 1k scale", per phase-08:101) — keeps lint check 6
   from ever needing an ALLOW entry (v6 #6); mitigations; the rule: "if you expose an
   ego/neighbors API, give it `limit` and `depth` from day one" → pointer to C4.
7. *Library landscape* — NetworkX (sourced 40–250× figure; "already in this repo's `[graph]`
   extra"); igraph/rustworkx at 10⁵+; graph DBs only when multi-hop IS the product; SQL edge
   table = right default. Decision shortcut line.
8. *Further Reading* — SQLite WITH docs, Brandes 2001, adjacency comparison, graph-tool perf
   page, Neo4j supernodes, Diestel.

Cross-links INTO it: phase-01a:64, phase-02:98, phase-03:34-35 + :61, phase-05 ~:133.

## C2 — `docs/foundations/graph-algorithms-beyond-bfs.md` (NEW, enrichment; Effort M, ~1,800 words)

Source: condensed mirror `01` + `02`. Header: `**Audience:** learners who finished Phase 3
and want to know what their graph can do next — enrichment, no phase requires this ·
**Read time:** ~15 min`. Depends on C1.
**Commit includes its own `mkdocs.yml` nav entry** — gate: `uv run mkdocs build`.

Sections: framing — **mirror-faithful speed honesty (v6 #12d)**: "Phase 3 ends at BFS on
purpose; this is the map beyond, scoped to a 100–5,000-node vault. Speed honesty, per the
source benchmarks: scoring the note you're ON — link-prediction candidates over its 2-hop
neighbourhood — is sub-millisecond, and Personalized PageRank converges in well under
100 ms; whole-vault passes are slower — all-pairs Adamic-Adar runs milliseconds to low
seconds at 5k nodes, structural-hole constraint takes seconds. Of the 'what next' list at
the end, the orphan/island scan is pure SQL; Adamic-Adar and PPR are NetworkX one-liners;
the structural-gap capstone composes a few NetworkX calls on top of community output." ·
centrality family table (keep the A–B–C–D–E worked example; "degree = popularity, closeness
= broadcast speed, betweenness = brokerage, PageRank = influence by association") ·
community detection (modularity Q + barbell; Louvain → Leiden; label propagation; "tags are
the clusters you declared; detection finds the ones you actually wrote") · link prediction
(CN vs **Adamic-Adar** 1/log(degree); `nx.adamic_adar_index`) · **Personalized PageRank as
the ego-graph upgrade** (`nx.pagerank(G, personalization={seed: 1.0})`; typed relations as
weights; multi-seed; hook to phase-08:604) · "what your Phase 3 graph can do next" priority
list · Reflect (Solo: Adamic-Adar + the Index MOC; Group: damping walk + PPR ranking
question) · Further Reading (Brandes, Brin & Page, Traag, Liben-Nowell & Kleinberg, NetworkX).

Cross-links: phase-03 Reflect (after :343) "Going further" callout; phase-08:604 pointer.

## C3 — Audience/effort header rollout (Effort S; decision N7; **Stage 9.5 — strictly after Stage 8**)

Format, one line directly under the H1: `**Audience:** <who> · **Read time:** ~N min`.
The three docs with the old two-line block (direnv, makefile, mkdocs) convert (prerequisite
folds into audience). relation-vocabulary gets the reference variant. **Locate every
insertion by H1 text, never by line number** (B3/B4/B5 rewrote three of these files in
stages 7–8). Per-doc values (word-count-calibrated — full table in the Rev-1 output):
asyncio ~12 · design-patterns ~18 · direnv ~15 · git ~8 · http ~12 · json-rpc ~10 ·
makefile ~15 · mkdocs ~20 · dataclasses ~10 · threading ~10 · type-annotations ~10 ·
relation-vocabulary "~10 min skim; reference, don't memorize" · sqlite ~18 · terminal-tmux
~12 · yaml ~18 · the two new docs as specced in C1/C2.

## C4 — Ego-graph node budgeting (Effort M; decision N8; Stage 11 — after B2, one commit)

**Tested deliverable.** Backward compatible at the API level; **previously-green learners
fail the two NEW tests** (they call `limit=3` → TypeError, read `truncated` →
AttributeError) — stated honestly in the phase-03 admonition, which lands in THIS commit.

- **Code** (canonical `solutions/phase_03/src/akanga_core/graph.py`, propagate 3→8):
  `build_ego_graph(root_id, db, max_depth=2, limit=None)`; `EgoGraph` gains
  `truncated: bool = False` (appended last). Semantics (into the docstring): when adding a
  neighbor would make `len(nodes) > limit`, the neighbor is NOT added to nodes/queue and its
  edge is NOT recorded (preserves "every edge's endpoints are in nodes"); `truncated=True`
  on first hit; `limit=None` = today's behavior; `limit < 1` → ValueError. Add one docstring
  sentence (v6 verified pre-existing): "edges between two nodes both sitting at
  `max_depth` are never enumerated — a property of depth-bounded BFS, independent of
  `limit`." WHY: supernode rationale + pointer to graph-theory-basics §Supernodes. Mirror
  the param into `skeletons/phase_03/.../graph.py` (stub keeps NotImplementedError; HOW
  gains the budget step).
- **Tests** (`tests/phase_03/test_graph.py`): `test_ego_graph_limit_truncates` (star root +
  5 neighbors, `limit=3` → 3 nodes, `truncated`, every edge's endpoints ⊆ nodes — assert
  counts and flag, NEVER which neighbors survived); `test_ego_graph_no_limit_not_truncated`.
- **Phase 3 doc** (same commit): new Concepts block `### Node Budget (Supernode Guard)`
  after Ego-Graph (:97) — hubs inevitable; depth alone doesn't bound size (the 170-node
  figure, phrased without "of the"); the budget is an API contract so the caller must be
  TOLD when it bit ("a silent partial answer is a lie" → `truncated`); budget ≠ the ASCII
  render ceiling. `> Akanga node: Node Budget` · foundation pointer. Update What-You-Build
  signature + dataclass listing; add the 2 test names to Deliverable; add a Vault-Nodes
  row. **Amend B2's rewritten block** with the `limit` param. Insert the **phase-03
  admonition** (text in Workstream A's appendix).
- **Phase 6 doc** `:190`: `GET /api/v1/nodes/{id}/ego-graph  ego-graph data (?depth= ·
  ?limit= — response carries "truncated": bool)` — still stretch, still untested.

## C5 — Three design sidebars

**C5a — "Dataclasses + services, not OOP"** (Effort S–M, ~600 words; no dependency). New
`## 11. Dataclasses + Services (the deliberately anemic domain model)` in
`docs/foundations/design-patterns.md` between §10 and the Summary Table. Arc: the OOP
expectation (`node.save()`, `node.link_to()`); the honest counterpoint **"graphs are the
perfect OOP example"**; the resolution pinned to curriculum facts — (a) a self-saving Node
welds parse model to storage model (the repo keeps `models.Node` vs `db.NodeRecord` apart,
W9); (b) behavior lives where its dependencies live (`build_ego_graph(root_id, db)` declares
the DB; DI §6 only works when functions ask); (c) dumb data crosses thread/serialization
boundaries, objects with handles don't. Boundary: `GraphDatabase` IS a class (Repository §3).
Rule: **state that owns a resource → class; data that crosses a boundary → dataclass;
behavior → module function with injected dependencies.** Add the Summary-Table row.
Cross-links: phase-01a:181 pointer; `docs/index.md:55` bullet append.

**C5b — Alias-rule tradeoff sidebar** (Effort S, ~400 words; after A-3 — the ADOPTED
variant). `!!! note "Design Decision: what does the pipe mean? (interop vs typed edges)"`
in phase-01a after the inline-shorthand paragraph (post-A4 text). Arc: the collision
(everywhere else `[[Title|text]]` = display alias; both readings can't win) · "decide
before data accretes" (the real R2 #7 lesson) · the shape mitigation (include the 5-row
shape table from mirror concepts.md) · the accepted residual (slug-shaped Obsidian aliases
still mint relations) · close: "Akanga adopts the shape rule (decision N4); the residual is
the documented cost" + pointer to A4's tests.

**C5c — Schema-vs-open-dict sidebar** (Effort S, ~400 words; after B4, same file region).
New `## When Would Frontmatter Earn a Schema?` in yaml-and-markdown-frontmatter.md right
after B4's rewritten "Akanga's Node Frontmatter Format"; 2-line pointer admonition in
phase-00's YAML Frontmatter concept (:65-92). Arc: the temptation (a typed
FRONTMATTER_SCHEMA, e.g. Pydantic `extra="allow"`) · why it was sketched and **rejected** —
(a) frontmatter is user-authored text; a schema turns typos into parse failures on files the
user owns (contrast: Phase 6's API bodies ARE Pydantic-validated — the trust boundary
differs); (b) `extra="allow"` keeps unknown keys but silently launders known ones; (c) the
vault must round-trip · what the curriculum does instead: ONE targeted coercion at the parse
boundary, `_normalize_fm` · the rule: **validate at boundaries you own (API), normalize at
boundaries you don't (user files); a schema only when a wrong shape must be a hard error.**
Cross-link the doc's Implicit Typing section.

## C6 — Edge-lifecycle pitfall box + stub-stretch mention (Effort S; Stage 13 — lines RESOLVED per N1/N2/N3/N10/N11)

`!!! note "Edge lifecycle — every way an edge disappears"` appended to phase-02 Common
Pitfalls (:343-350). Content: the two species (body-derived = re-derived from prose every
index; frontmatter `edges:` = persistent source of truth; typed inline shorthand is folded
INTO frontmatter by `write_back` at index time (V4) — after one cycle it has become the
persistent kind) · the taxonomy:
- deleted the wikilink text → gone next index, expected;
- target doesn't exist yet → **logs a warning, no edge** (N3; resolves automatically at the
  next **full scan** after the target appears, N2 — the live watcher re-derives only the
  file that changed, so a running app waits for the next full scan);
- link inside a ``` fence → stripped, never an edge (W1, feature);
- API-created edge → **persisted file-first to frontmatter — survives re-index and
  `rm *.db`** (N1; deleting a folded typed edge also de-types its inline shorthand so it
  cannot re-fold — see the Phase 6 pitfall for the DB-only failure mode this design prevents);
- deleted file → tombstone + CASCADE removes outgoing edges;
- two notes share a title → **resolved deterministically (N10)**: the node first in vault
  path order wins and a warning names both — frontmatter edges with a stored `target_id`
  are immune (UUIDs bypass title resolution entirely); the real fix is still to retitle.
  noteapp resolves oldest-wins by `created_at`; this schema stores no timestamps, so path
  order is the stable equivalent.
Cross-link phase-01a's Source-of-Truth concept (:81).

**Same commit — stub-creation stretch mention (v6 #12b, amends N3):** directly after the
edge-lifecycle box, add:

> ### Stretch (untested): stub nodes for unresolved links
>
> Akanga logs a warning and creates no edge when a wikilink's target doesn't exist yet (N3).
> noteapp goes one step further: `create_stub_node` auto-creates a minimal note
> (`type: note`, tagged `stub`) in the vault root and attaches the edge to it — a link you
> wrote is never lost, and a second unresolved reference to the same title reuses the
> existing stub. Porting it is a genuine end-to-end exercise: it touches `create()` (minting
> the file), the parser (the stub must round-trip), and the indexer (pass 2 must see the new
> node) — plus two design questions noteapp answered that you'd have to answer too: a
> `create_stubs=False` opt-out, and what happens when the real note finally arrives under a
> different filename. No shipped test pins this; if you build it, write your own (the
> "Optional self-written test" at the end of the Deliverable shows the pattern).

## C7 — Vector-RAG + prompt-injection concepts + Pydantic pointer (Effort S)

**C7a** — `### Vector RAG (what Graph RAG is defined against)` inserted BEFORE phase-08's
Graph RAG concept (:84): embedding = dense vector (cosine similarity); the pipeline (chunk →
embed → ANN index → top-k → stuff prompt); superpower = zero schema; structural blindness =
retrieves "Fast Thinking" and "Blink" because they're similar — whether one CONTRADICTS the
other is left to the LLM (completes the half-contrast at :88-92); they compose — embeddings
can replace FTS5 in seed selection only (explains :99-100). `> Akanga node: Vector RAG`
(closes the dangling Vault-table reference at :181).

**C7b** — `### Prompt Injection` near it: LLMs have no type system separating instructions
from data; the Akanga attack (a note body that reads like instructions enters via
`get_context`); the built mitigation (`[KNOWLEDGE GRAPH CONTEXT]` delimiters, SEC-01 +
SERVER_INSTRUCTIONS); honest caveat — delimiters are mitigation, not a boundary; layered
defense. Fix the bare prerequisite at :41 → "→ Covered in this phase's Prompt Injection
concept below".

**C7c** — phase-06:33 Pydantic prerequisite gains `→ See docs/foundations/http-fundamentals.md
("Pydantic models for request bodies")` (target verified at :225).

## C8 — Fence-regex technique tip (Effort S)

`!!! tip "Technique: don't skip code blocks — delete them"` in phase-01a under the
`extract_inline_edges` function-table row: the wrong instinct (lookaround mega-regex =
tarpit) vs the taught idiom — strip first, match second:
```python
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
stripped = _FENCED_CODE_RE.sub("", body)
edges = _INLINE_EDGE_RE.findall(stripped)
```
Why each flag matters: DOTALL crosses newlines; **non-greedy `.*?`** stops at the nearest
closing fence — greedy would swallow everything between the first and last fence. Scope
note: positions don't survive stripping — fine (extractor returns matches); need offsets →
replace fences with same-length whitespace. Pointer: same idiom guards
`links.extract_wikilinks` (W1).

## C9 — Stretch TEACH items (Effort S each; doc-only, decision N9)

**C9a — relation soft-validation → Phase 8** (the registry only becomes machine-readable
there). Stretch spec sketch: `suggest_relation(relation) -> str | None` via
`difflib.get_close_matches(relation.lower(), known_slugs, n=1, cutoff=0.6)`; wired as a
**logged warning only** ("Minting unknown relation 'suports' — did you mean 'supports'?
(open vocabulary: the edge is kept either way)"). Principle: open vocabulary by decision;
warn, never reject. Optional self-written test framing. Cross-link from
relation-vocabulary.md:238. Phase-1A Reflect teaser: "write_back mints a UUID relation-id
for any unknown relation — including 'suports'. At what layer would you catch the typo, and
why must the answer be a warning rather than an error?"

**C9b — export → Phase 3 + Phase 6**: Phase 3 `### Stretch (untested)`:
`to_mermaid(ego: EgoGraph) -> str` (~20 lines; alias map `n0, n1…`; `graph TD`;
`n0["Title"]` escaping `"` as `#quot;`; `n0 -->|relation| n1` falling back to bare arrow;
sanitize `|`; mirror `cli.py:_export_mermaid` is the reference). Payoff: "paste into
mermaid.live or a GitHub README." Phase 6 stretch list:
`GET /api/v1/export?format=json|mermaid` (graphml named-only; the lesson is
edge-list-as-serialization → cross-link C1 §3).

## C10 — Wiring + round close (Effort S; LAST)

1. `mkdocs.yml` nav: VERIFY the two foundation entries landed in C1/C2's own commits
   (strict mode made a missing entry fail their gates) — C10 only confirms.
2. `docs/README.md` tree: "15 background explainers" → 17; add both new foundation
   filenames. Map maintenance in the contributor-doc block (README lists adversarial
   analyses individually): add `noteapp-alignment-audit.md  noteapp gap audit — source
   findings for the N-series round`; add `adversarial-analysis-v6.md  Round 6 risk analysis
   — noteapp-alignment plan (CURRENT)` and change v5's tag to `(historical, resolved)`;
   extend the plan-glob parenthetical to "…, noteapp alignment" (`plan-noteapp-alignment.md`
   needs no own line).
3. `docs/index.md` (:54-68): two new foundation bullets (B1 already fixed :65's count).
4. `relation-vocabulary.md`: top cross-link to graph-theory-basics + the C9a line at :238.
5. `docs/status-remediation.md`: confirm the round section is complete (N1–N11 + B's prose
   log + the NOTEAPP SYNC superseding line — B8 drafted them).
6. Gate: `uv run mkdocs build --strict` (nav + internal-link + anchor validation — this IS
   the link check; no separate tool exists or is needed) +
   `uv run python scripts/check_doc_contracts.py`.
7. **CLAUDE.md round close (v6 #8)**: "Current focus" → noteapp-alignment round (N-series)
   is **COMPLETE** — all audit findings plus the 12 adversarial-analysis-v6 plan amendments
   resolved; decisions N1–N11 logged in `docs/status-remediation.md`. No round is currently
   in progress — `make status` and `docs/status-remediation.md` are the live state. One
   deferred item with a trigger: `check_doc_contracts.run_checks` extraction, revisit only
   if that file grows. **Delete `.tmp-noteapp-mirror/`.**

---

## Effort summary

| Workstream | Items | Effort |
|---|---|---|
| G-0 | kickoff commit | S (three one-line hardening edits, verified green) |
| A (code) | 4 commits | M(F1+) + S(F4+F5+N10) + M(F2+F10+N11) + M(F3+docs) — every commit gated by test-solution + sync-forward + cumulative verify + doc lint where docs change |
| B (docs-correctness) | 7 commits | 4×M + 3×S — mechanical once specs are followed |
| C (new content) | ~9 commits | 2×M docs + M budgeting + the rest S |

Total: ~21 commits across 15 stages (0–14). Stages 1–4 (code) are strictly sequential;
stages 5–9 (B) and 10/12 (C, ungated parts) can interleave; 9.5/11/13/14 close out.
