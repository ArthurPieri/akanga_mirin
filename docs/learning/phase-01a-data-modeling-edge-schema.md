# Phase 1A — Data Modeling: Edge Schema and Inline Shorthand

**Estimated time: 2–3h + ~1h vault/reflect**

!!! warning "Changed 2026-06 (noteapp-alignment round)"
    The pipe grammar changed: a pipe segment is a relation only when it matches
    `^[a-z][a-z0-9_-]*$` (after strip) — spaces, uppercase, digit-first, or an escaped `\|`
    now mean an Obsidian-style display alias, which yields a plain wikilink instead. The
    grammar lives in one new public helper, `split_pipe_segment`, and a typed link now
    produces exactly ONE edge (the typed one). Seven new tests in `tests/phase_01/test_schema.py`.
    If you finished this phase before the change: run `make skeleton PHASE=1` — the merge
    appends the new `split_pipe_segment` stub into your `parser.py` without modifying your
    code — then implement the classification and update `extract_inline_edges` to use it.

**Core concept:** Deciding how to represent a *connection* between two nodes as plain
text. Phase 0 gave you a file with metadata and a body. Phase 1A asks: what does a
typed edge look like inside a file? What happens when a user writes connections
informally in prose? How do you merge informal prose edges into the authoritative
frontmatter block — reliably and without duplication?

The central decisions are already made from the product discussion. This phase is
about understanding why those decisions were made and building the code that enforces
them.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Explain the four fields of the `Edge` dataclass and why both `relation` + `relation_id` (and `target` + `target_id`) are stored together
- Implement `extract_inline_edges` using a regex that correctly skips fenced code blocks
- State the deduplication rule for `merge_edges` and explain why `target_id` is excluded from the key
- Implement `write_back` such that calling it twice on the same file produces the same result as calling it once (idempotence)

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] Phase 0 is complete: I have a working `parse`, `write`, `create`, and `hash` in `parser.py`
  → Required: complete Phase 0 deliverable tests first
- [ ] I know what a Python dataclass is and how `@dataclass` auto-generates `__eq__`
  → See `docs/foundations/python-dataclasses.md`
- [ ] I can write a basic Python regex with a capture group and use `re.findall`
  → Prerequisite: basic Python `re` module knowledge
- [ ] I understand what YAML dicts and lists look like, and how `python-frontmatter` parses them
  → See `docs/foundations/yaml-and-markdown-frontmatter.md`

---

## Quick Start

```bash
make skeleton PHASE=1    # copy the starting code into ./src/ (shared by 1A and 1B)
make test PHASE=1 PYTEST_ARGS="-k 'not sync_queue'"  # 1A tests only (edge schema)
make study PHASE=1a      # open the tmux study session for 1A
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Concepts

### Directed Graph

A graph where edges have direction: A → B is not the same as B → A. "Fast Thinking
`contradicts` Blink" is a different statement than "Blink `contradicts` Fast Thinking."
The direction carries meaning. This matters for traversal (Phase 3) and ego-graph
display: outgoing edges (this node makes a claim about something else) are shown
differently from incoming edges (something else makes a claim about this node).

> Akanga node: `Directed Graph`

### Labeled Property Graph (LPG)

A graph model where edges carry a type label — the relation — rather than being
anonymous connections. "A links to B" is a hyperlink graph. "A *supports* B" is a
knowledge graph. The label is what gives the edge semantic value: you can ask "what
does this node contradict?" or "what does this node depend on?" and get meaningful,
filtered answers. Akanga stores Tier 2 semantics: every edge has a `relation` field
drawn from the 72-type vocabulary.

> Akanga node: `Labeled Property Graph`

> → Foundation doc: `docs/foundations/design-patterns.md`

> → Foundation doc: `docs/foundations/relation-vocabulary.md` (full 72-type vocabulary)

### Source of Truth

The single authoritative record of a fact. All other copies are derived and
expendable. In Akanga, the frontmatter `edges:` block is the source of truth for a
node's connections. The SQLite index is derived from it. The inline `[[wikilinks]]`
in prose are a convenience shorthand — not authoritative on their own. When there is
a conflict between prose and frontmatter, frontmatter wins. When prose declares an
edge not yet in frontmatter, write-back adds it.

> Akanga node: `Source of Truth`

### Eventual Consistency

A consistency model where replicas of the same data may diverge temporarily but are
guaranteed to converge given enough time and no new updates. In Akanga, inline prose
and the frontmatter `edges:` block can be out of sync between sync events (file save,
TUI open, explicit trigger, schedule). This is acceptable because convergence is
guaranteed — the write-back process will run. The alternative (strong consistency,
where every inline edit immediately updates frontmatter) would require the editor to
be Akanga-aware, which kills the "any text editor" promise.

> Akanga node: `Eventual Consistency`

### Two-Pass Parsing

Parsing an Akanga node requires two distinct passes with different tools. Pass 1:
extract the YAML frontmatter block into structured data — a YAML parser handles this.
Pass 2: scan the Markdown body for inline edge shorthand `[[Target | relation]]` —
a regex handles this. The results are merged and deduplicated. Keeping the passes
separate keeps responsibilities clean: the YAML parser never sees prose, the regex
never sees structured data.

> Akanga node: `Two-Pass Parsing`

---

## The Edge Format

The canonical frontmatter edge block:

```yaml
edges:
  - relation: contradicts
    relation_id: EP-002
    target: Blink — Malcolm Gladwell
    target_id: d4e1f9cc-5678-1234-efab-012345678901
  - relation: supports
    relation_id: EP-001
    target: Kahneman System 1 and System 2
    target_id: b2c3d4e5-abcd-ef01-2345-678901234567
```

Underscore keys are canonical — they match the `Edge` dataclass fields below.
Hyphenated spellings (`relation-id:`/`target-id:`) found in hand-authored or
Obsidian-exported vaults are tolerated on read (the parser accepts both) and
normalized to underscores on the next write-back: **read both, write underscores.**

The dual-key pattern applies to both fields:
- `relation` — human-readable display cache; may be stale after a relation rename
- `relation_id` — stable ID from the vocabulary (`EP-002`, `CT-005`, etc.); never changes
- `target` — human-readable title; may be stale after the target node is renamed
- `target_id` — UUID of the target node; stable forever; empty string if unresolved

For custom relation types not in the built-in vocabulary, `relation_id` is a UUID
generated at first use. Built-in IDs use the category-prefix format (`EP-001`…`TC-004`)
— see `docs/foundations/relation-vocabulary.md` for the full table.

**Inline shorthand in prose:** `[[Target Title | relation]]`

On write-back, this becomes an entry in the `edges:` block. `target_id` is resolved
by looking up the title in the DB index — left empty if the target node does not exist
yet (dangling reference, resolved on next sync after the target is created).

**Not every pipe is a relation.** Akanga shares the `[[Title | text]]` syntax with
Obsidian, where the pipe means a display *alias*. The grammar that settles the overload
(`split_pipe_segment`): a segment is a **relation** only when it is slug-shaped —
`^[a-z][a-z0-9_-]*$` after stripping (e.g. `supports`, `relates-to`). Anything with
spaces, uppercase, a leading digit, or an escaped pipe (`[[Note \| text]]`) is an
Obsidian-style **display alias** and yields a plain wikilink, never a typed edge. The
canonical spaced form `[[Target Title | relation]]` still works — the segment is
stripped before classification. One consequence: a typed link produces exactly **one**
edge (the typed one), not a typed edge plus a redundant untyped wikilink.

!!! note "Design Decision: what does the pipe mean? (interop vs typed edges)"
    The pipe in `[[Title|segment]]` is overloaded. Obsidian reads it as a display
    alias; Akanga also wants it for relations. Both readings cannot win — and this is
    exactly the kind of syntax overload you must **decide before data accretes**. A
    vault already full of ambiguous pipes is far more expensive to disambiguate later
    than a rule chosen on day one (the real lesson behind the R2 interop review).

    Akanga resolves it by **shape**:

    | You write | Segment shape | Result |
    |---|---|---|
    | `[[Auth]]` | — | plain edge, relation `wikilink` |
    | `[[Auth\|depends_on]]` | slug `^[a-z][a-z0-9_-]*$` | **typed edge**, relation `depends_on` |
    | `[[Auth\|the auth note]]` | has spaces | plain edge, alias "the auth note" |
    | `[[Auth\|Supports]]` | has uppercase | plain edge, alias "Supports" |
    | `[[Auth\\|alias]]` | escaped pipe | always an alias, never a relation |

    **The accepted residual:** a slug-shaped Obsidian alias — `[[Title|the-talk]]` —
    still mints a relation, because shape is all the parser can see. Akanga adopts the
    shape rule anyway (decision N4): it keeps the common cases compatible in both
    directions, and the residual is the documented cost of reusing one pipe for two
    jobs. Opening an Akanga vault in Obsidian renders a typed link's relation as its
    link text; a future importer with slug-alias quarantine is the planned mitigation.
    The classification is pinned by `split_pipe_segment`'s tests (this phase's Deliverable).

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Directed Graph` | note | `subtype_of` → `Graph`; `contrasts_with` → `Undirected Graph` |
| `Labeled Property Graph` | note | `subtype_of` → `Directed Graph`; `implements` → `Semantic Edge Types` |
| `Source of Truth` | note | `qualifies` → `Frontmatter Edge Block`; `contrasts_with` → `Derived Index` |
| `Eventual Consistency` | note | `qualifies` → `Write-Back Sync`; `contrasts_with` → `Strong Consistency` |
| `Two-Pass Parsing` | note | `is_applied_in` → `Akanga Parser`; `enables` → `Inline Edge Shorthand` |

---

## What You Build

Extensions to `parser.py` from Phase 0.

> `Edge` and `Node` are deliberately *anemic* dataclasses — data with no behavior; the
> logic lives in module functions like `write_back` and `build_ego_graph`. See
> `docs/foundations/design-patterns.md` §11 for why Akanga models data this way.

**`Edge` dataclass:**

```python
@dataclass
class Edge:
    relation: str      # display cache — human-readable name, may be stale after rename
    relation_id: str   # authoritative ID (e.g. "EP-002") — stable forever
    target: str        # display cache — target node title, may be stale after rename
    target_id: str     # authoritative UUID — stable forever, empty if unresolved
```

The dual-key pattern applies to both the relation and the target: `relation` and
`target` are human-readable display caches; `relation_id` and `target_id` are the
stable machine keys. The relation registry (`docs/foundations/relation-vocabulary.md`)
maps IDs to names, descriptions, and flags (symmetric, inverse pair).

**New functions in `parser.py`:**

| Function | What it does |
|---|---|
| `extract_inline_edges(body) → list[Edge]` | Scan for `[[Target \| relation]]`; skips code blocks and inline code; only slug-shaped segments are relations |
| `split_pipe_segment(segment) → tuple[str, str]` | Classify a pipe segment: `("relation", slug)` when it matches `^[a-z][a-z0-9_-]*$` after strip, else `("alias", text)` |
| `merge_edges(existing, inline) → list[Edge]` | Deduplicate: add inline edges not already in existing |
| `write_back(path)` | parse → extract inline → merge → write atomically if changed |

!!! tip "Technique: don't skip code blocks — delete them"
    `extract_inline_edges` must ignore `[[wikilinks]]` that appear inside a fenced code
    block (a code sample is not a link). The wrong instinct is one lookaround mega-regex
    that matches links *except* inside fences — that way lies an unreadable tarpit. The
    taught idiom is **strip first, match second**: remove the fenced blocks, then run the
    link regex on what's left.

    ~~~python
    _FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
    stripped = _FENCED_CODE_RE.sub("", body)
    edges = _INLINE_EDGE_RE.findall(stripped)
    ~~~

    Why each flag matters: `re.DOTALL` lets `.` cross newlines so a multi-line fence matches
    whole; the **non-greedy** `.*?` stops at the *nearest* closing fence — greedy `.*` would
    swallow everything between the first fence and the last. Scope note: character offsets do
    not survive stripping, which is fine here (the extractor returns matches, not positions);
    if you ever need offsets, replace each fence with the same length of whitespace instead
    of deleting it. The same strip-first idiom guards `links.extract_wikilinks` (W1).

**Deduplication rule:** an edge is a duplicate if `(relation, target)` matches an
existing edge. `target_id` is not part of the key — an empty `target_id` in an inline
edge does not override a resolved `target_id` in frontmatter.

---

## Deliverable

The snippets below are illustrative — the shipped suite is
`tests/phase_01/test_schema.py` (the names differ):
`test_extract_inline_edges_basic` / `_multiple` / `_ignores_code_blocks` /
`_ignores_regular_wikilinks` / `_empty_body`, `test_merge_edges_deduplicates` /
`_adds_new` / `_empty_inputs` / `_conflicting_target_id_keeps_existing`,
`test_merge_is_not_order_sensitive`, `test_edge_dataclass_fields`,
`test_write_back_moves_inline_to_frontmatter` / `_idempotent` /
`_preserves_existing_edges` / `_malformed_edges_yaml_raises`, plus the alias-rule
tests (2026-06): `test_alias_with_spaces_is_not_inline_edge`,
`test_uppercase_segment_is_alias_not_edge`, `test_digit_first_segment_is_alias`,
`test_escaped_pipe_never_a_relation`, `test_spaced_canonical_syntax_still_typed`,
`test_inline_code_is_ignored`, `test_split_pipe_segment_table`.

The illustrative sketches:

```python
def test_inline_edge_extraction():
    body = "This idea [[Blink — Gladwell | contradicts]] fast thinking."
    edges = extract_inline_edges(body)
    assert len(edges) == 1
    assert edges[0].relation == "contradicts"
    assert edges[0].target == "Blink — Gladwell"

def test_inline_inside_code_block_ignored():
    body = "```\n[[Some Node | supports]]\n```"
    assert extract_inline_edges(body) == []

def test_merge_deduplicates():
    existing = [Edge(relation="contradicts", target="Blink", target_id="abc")]
    inline   = [Edge(relation="contradicts", target="Blink", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 1            # not doubled
    assert merged[0].target_id == "abc"  # resolved target_id preserved

def test_merge_adds_new_inline_edge():
    existing = [Edge(relation="contradicts", target="Blink", target_id="abc")]
    inline   = [Edge(relation="supports", target="Kahneman", target_id="")]
    merged = merge_edges(existing, inline)
    assert len(merged) == 2

def test_writeback_roundtrip():
    # File with inline edge in body but empty frontmatter edges block.
    # After write_back(), frontmatter edges block contains the inline edge.
    node = create(title="Test", node_type="note", vault=tmp_path)
    node.path.write_text(node.path.read_text() + "\n[[Blink | contradicts]]")
    write_back(node.path)
    re_parsed = parse_node_file(node.path)
    # Edges live in the frontmatter dict, not as a dedicated Node field. In Phase 02+,
    # edges move to the DB edges table and are accessed via db.get_neighbors().
    # For Phase 01A, read edges from the parsed frontmatter:
    edges = re_parsed.frontmatter.get("edges", [])
    assert len(edges) == 1
    assert edges[0]["relation"] == "contradicts"

def test_writeback_is_idempotent():
    node = create(title="Test", node_type="note", vault=tmp_path)
    node.path.write_text(node.path.read_text() + "\n[[Blink | contradicts]]")
    write_back(node.path)
    write_back(node.path)  # second call must not duplicate the edge
    re_parsed = parse_node_file(node.path)
    edges = re_parsed.frontmatter.get("edges", [])
    assert len(edges) == 1
```

Plus 5 vault nodes with typed edges. The vault is the proof of understanding,
not just the tests.

---

## Reflect

> **Solo:** The deduplication key is `(relation, target)` — not `(relation_id, target_id)`. Why? What would break if you used the UUID-based keys as the dedup key instead, given that `target_id` can be an empty string when parsed from inline shorthand?

> **Group:** `write_back` is described as "write atomically *if changed*." What is the check that determines "changed"? Who should own that check — `write_back` itself, or the caller? Discuss the tradeoffs of each approach and which leads to more correct behavior at scale.
