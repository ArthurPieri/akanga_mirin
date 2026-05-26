# Phase 1A — Data Modeling: Edge Schema and Inline Shorthand

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
make skeleton PHASE=1    # copy the starting code into ./src/
make test PHASE=1        # run the tests (they will fail initially)
make study PHASE=1       # open the tmux study session
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
drawn from the 71-type vocabulary.

> Akanga node: `Labeled Property Graph`

> → Foundation doc: `docs/foundations/design-patterns.md` (Labeled Property Graph section)

> → Foundation doc: `docs/foundations/relation-vocabulary.md` (full 71-type vocabulary)

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
    relation-id: EP-002
    target: Blink — Malcolm Gladwell
    target-id: d4e1f9cc-5678-1234-efab-012345678901
  - relation: supports
    relation-id: EP-001
    target: Kahneman System 1 and System 2
    target-id: b2c3d4e5-abcd-ef01-2345-678901234567
```

The dual-key pattern applies to both fields:
- `relation` — human-readable display cache; may be stale after a relation rename
- `relation-id` — stable ID from the vocabulary (`EP-002`, `CT-005`, etc.); never changes
- `target` — human-readable title; may be stale after the target node is renamed
- `target-id` — UUID of the target node; stable forever; empty string if unresolved

For custom relation types not in the built-in vocabulary, `relation-id` is a UUID
generated at first use. Built-in IDs use the category-prefix format (`EP-001`…`TC-004`)
— see `docs/foundations/relation-vocabulary.md` for the full table.

**Inline shorthand in prose:** `[[Target Title | relation]]`

On write-back, this becomes an entry in the `edges:` block. `target-id` is resolved
by looking up the title in the DB index — left empty if the target node does not exist
yet (dangling reference, resolved on next sync after the target is created).

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
stable machine keys. The relation registry (in `akanga.yaml` or `vocabulary.yaml`)
maps IDs to names, descriptions, and flags (symmetric, inverse pair).

**New functions in `parser.py`:**

| Function | What it does |
|---|---|
| `extract_inline_edges(body) → list[Edge]` | Regex scan for `[[Target \| relation]]`; skips code blocks |
| `merge_edges(existing, inline) → list[Edge]` | Deduplicate: add inline edges not already in existing |
| `write_back(path)` | parse → extract inline → merge → write atomically if changed |

**Deduplication rule:** an edge is a duplicate if `(relation, target)` matches an
existing edge. `target_id` is not part of the key — an empty `target_id` in an inline
edge does not override a resolved `target_id` in frontmatter.

---

## Deliverable

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
    node = create(title="Test", type="note", vault=tmp_path)
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
    node = create(title="Test", type="note", vault=tmp_path)
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
