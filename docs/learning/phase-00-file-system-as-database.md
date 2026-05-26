# Phase 0 — File System as Database

**Core concept:** The file is the database. Not a cache, not a representation — the
file *is* the record. Everything downstream (index, TUI, API) is derived from files
and is expendable. Delete the index: rebuild it from files. The files are never
derived from anything else.

**What makes this non-obvious:** Every database tutorial starts with a schema and
inserts rows. Here the "schema" is a text format with a human-editable header, and
the "insert" is writing a file to disk. The instinct is to treat files as inputs to
a real database. The point of this phase is to break that instinct.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Explain what YAML frontmatter is and why it serves as Akanga's node schema instead of a traditional database schema
- Implement a `parse → write → parse` roundtrip that is fully idempotent — no fields reordered, no whitespace added, no encoding changed
- Explain the role of UUID as a stable node identity that survives file renames and title changes
- Implement an atomic file write using `os.replace` and explain why naive `open(..., 'w')` is unsafe

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the
linked foundation doc before proceeding.

- [ ] I can open a file in Python, read its contents, and write new contents back to it
  → Basic Python I/O (`open`, `read`, `write`)
- [ ] I know what a Python dictionary is and how to access and mutate its keys
  → Prerequisite: core Python knowledge
- [ ] I know what a Python dataclass is and how `@dataclass` generates `__eq__` automatically
  → See `docs/foundations/python-dataclasses.md`
- [ ] I understand what YAML is and can read a simple YAML block
  → See `docs/foundations/yaml-and-markdown-frontmatter.md`

---

## Quick Start

```bash
make skeleton PHASE=0    # copy the starting code into ./src/
make test PHASE=0        # run the tests (they will fail initially)
make study PHASE=0       # open the tmux study session
```

> First time here? Run `make setup` first, then `direnv allow` to activate the environment.
> See `docs/foundations/makefile-basics.md` for a full Makefile walkthrough.

## Toolbox — Foundation Docs

Three tools you will use throughout this learning path. If you have not used them
before, read these first — each takes 15–20 minutes and you can return here immediately after.

- **Make** — `docs/foundations/makefile-basics.md` — the Makefile is your primary interface to this repo. Every workflow is a `make <target>` call.
- **Direnv** — `docs/foundations/direnv-basics.md` — auto-activates your Python environment and project variables when you `cd` into the repo.
- **MKDocs** — `docs/foundations/mkdocs-basics.md` — renders your Markdown docs as a browsable website. Used in Phase 8 to publish your knowledge graph, available anytime via `make docs-serve`.

## Concepts

### YAML Frontmatter

Structured metadata embedded at the top of a Markdown file, delimited by `---`
lines. The parser reads everything between the first and second `---` as YAML,
everything after as the body. It is Akanga's node schema: UUID, title, type, tags,
and edges all live here. Because it is plain text, it is human-readable,
git-diffable, and editable in any text editor — no proprietary format, no lock-in.

> Akanga node: `YAML Frontmatter`

> → Foundation doc: `docs/foundations/yaml-and-markdown-frontmatter.md`

### UUID (Universally Unique Identifier)

A 128-bit randomly generated identifier (e.g., `a3f7c2be-1234-5678-abcd-ef01`).
The probability of two colliding is ~10⁻³⁷. In Akanga, the UUID is the stable
identity of a node: generated once on creation, written into frontmatter, and
never changed — even if the file is renamed, moved, or its title changes. This
makes UUID the correct key for edges, not the filename or title.

> Akanga node: `UUID`

### Idempotence

An operation is idempotent if applying it multiple times produces the same result
as applying it once. For the parser, `parse → write → parse` must be idempotent:
reading and writing back a file must not change it. Without this, every save
silently corrupts the file — reordering fields, adding whitespace, changing
encoding. Idempotence is also required for write-back in Phase 1: merging inline
edges into frontmatter repeatedly must not accumulate duplicates.

> Akanga node: `Idempotence`

### Atomic Write

A file write that either fully completes or has no effect — no observable
intermediate state. A naive write (`open(path, 'w')` then stream content) is not
atomic: if the process dies mid-write, the file is left partially written with no
recovery. The atomic pattern writes to a temp file first, then calls
`os.replace(temp, target)` — a single OS syscall that renames the inode. The
reader always sees the old complete file or the new complete file, never a partial
one.

> Akanga node: `Atomic Write`

> → Foundation doc: `docs/foundations/design-patterns.md` (Atomic Write section)

### Content Hash (SHA-256)

A fixed-size fingerprint derived deterministically from file content. SHA-256
produces 256 bits: the same content always gives the same hash; any change gives
a completely different one. In Akanga, the hash is stored in the DB index. When
the file watcher fires, the indexer hashes the changed file and compares to the
stored value — match means skip, difference means re-index. This avoids
unnecessary DB writes on saves that didn't change content.

> Akanga node: `Content Hash`

### Python Dataclass

A class decorated with `@dataclass` that auto-generates `__init__`, `__repr__`,
and `__eq__` from its field declarations. The generated `__eq__` makes
`assert parsed == re_parsed` work in tests without custom comparison code. Can be
made immutable with `@dataclass(frozen=True)` to prevent accidental mutation after
creation.

> Akanga node: `Python Dataclass`

> → Foundation doc: `docs/foundations/python-dataclasses.md`

### Vault Configuration

A single YAML file at the vault root (`akanga.yaml`) that stores vault-level
settings: the vault owner's name (written as `author` on every new node) and the
workspace registry — the list of named workspaces with their UUIDs. The parser
reads it on `create()` to stamp `author` and assign the default workspace.
Keeping config separate from node files means changing your name or renaming a
workspace does not require touching every node — only the config changes, and the
sync queue handles the lazy display-name update in node files.

The default workspace is **Nhamandu** (Mbya Guaraní: the primordial being whose
unfolding thought gave rise to the cosmos — the source before all things). Its
UUID is generated once at `akanga init` and never changes, even if the user
renames the workspace.

```yaml
# akanga.yaml
owner: Arthur Pieri
default_workspace:
  name: Nhamandu
  id: a3f7c2be-1234-5678-abcd-ef0123456789   # generated at init, never changes
workspaces:
  - name: ProjectX
    id: b2c3d4e5-abcd-ef01-2345-678901234567
  - name: BookNotes
    id: c3d4e5f6-bcde-f012-3456-789012345678
```

> Akanga node: `Vault Configuration`

---

## Vault Nodes to Create

After completing Phase 0, create these nodes in your Akanga vault with the typed
edges below. The vault is proof of understanding — not just the tests.

| Node | Type | Key Edges |
|---|---|---|
| `YAML Frontmatter` | note | `is_part_of` → `Node File Format` |
| `UUID` | note | `satisfies` → `Stable Node Identity` |
| `Idempotence` | note | `qualifies` → `Parser Roundtrip` |
| `Atomic Write` | note | `solves` → `Partial Write Corruption`; `uses` → `os.replace` |
| `Content Hash` | note | `uses` → `SHA-256`; `enables` → `Change Detection` |
| `Python Dataclass` | note | `is_applied_in` → `Node Data Model` |
| `os.replace` | reference | `implements` → `Atomic Write`; `is_part_of` → `Python Standard Library` |
| `Vault Configuration` | note | `enables` → `Default Author Stamping`; `is_part_of` → `Vault Structure` |

---

## What You Build

Single module: `parser.py`

| Function | What it does |
|---|---|
| `parse_node_file(path) → Node` | Read `.md` file → `Node` dataclass |
| `write_node_file(path, frontmatter_dict, content)` | Serialize frontmatter + content to `.md` file, atomically |
| `create(title, type, vault) → Node` | Generate new node file with fresh UUID |
| `content_hash(path) → str` | SHA-256 hex digest of file content |

The canonical frontmatter schema:

```yaml
---
id: a3f7c2be-1234-5678-abcd-ef0123456789
title: Fast Thinking is Unreliable
type: note
tags: [cognition, decision-making]
graph:
  - name: Nhamandu
    id: a3f7c2be-1234-5678-abcd-ef0123456789
  - name: ProjectX
    id: b2c3d4e5-abcd-ef01-2345-678901234567
author: Arthur Pieri
created_at: 2026-05-23
updated_at: 2026-05-23
meta:
  status: draft
edges: []
---
```

`graph` is a list of workspace references — each entry has `name` (display cache,
may become stale after a rename) and `id` (UUID, authoritative, never changes).
This is the same dual-key pattern as edges. Absent or empty `graph` auto-populates
with the default workspace (Nhamandu) on first write-back.

`meta` is an optional block of user-defined key:value pairs — no schema
enforcement. It is stored only in the `.md` file; the Phase 02 DB schema does not
index `meta` as a column (you access it by re-parsing the file).

The `Node` dataclass at this phase:

```python
@dataclass
class Node:
    id: str             # UUID — generated once, lives in frontmatter
    title: str
    type: str           # "note" | "reference"
    tags: list[str]
    content_hash: str   # SHA-256 hex digest — computed at parse/index time
    content: str = ""   # raw markdown body (everything below frontmatter)
    path: str = ""      # runtime only — not written to frontmatter
```

> **Phase 00 introduces a simplified Node for learning. By Phase 02, the full Node
> dataclass uses exactly these fields: `id`, `path`, `title`, `type`, `tags`,
> `content_hash`, `content`. You'll evolve your Node incrementally across phases —
> fields like `graph`, `author`, `created_at`, `updated_at`, `meta`, and `edges`
> that appear in Phase 00 concepts are frontmatter keys accessible via
> `node.frontmatter` (the raw dict). They are not dedicated dataclass fields in
> the final shape.**

`create()` reads vault config to stamp author and default workspace:

```python
def create(title: str, type: str, vault: Path) -> Node:
    config = load_vault_config(vault)  # reads akanga.yaml
    # stamps author, assigns default_workspace as graph[0]
    ...
```

---

## Deliverable

Three tests that prove the contract:

```python
def test_roundtrip():
    node = create(title="Fast Thinking is Unreliable", type="note", vault=tmp_path)
    parsed = parse_node_file(node.path)
    assert parsed.id == node.id
    assert parsed.title == node.title
    assert parsed.content == node.content
    write_node_file(parsed.path, dict(parsed.frontmatter), parsed.content)
    re_parsed = parse_node_file(parsed.path)
    assert re_parsed == parsed           # write → parse is idempotent

def test_uuid_stability():
    node = create(title="Test", type="note", vault=tmp_path)
    original_id = node.id
    content = Path(node.path).read_text().replace("Test", "Test Renamed")
    Path(node.path).write_text(content)
    re_parsed = parse_node_file(node.path)
    assert re_parsed.id == original_id  # UUID unchanged after external edit

def test_atomic_write_leaves_no_temp_files():
    node = create(title="Test", type="note", vault=tmp_path)
    write_node_file(node.path, dict(node.frontmatter), node.content)
    temp_files = list(tmp_path.glob("*.tmp"))
    assert temp_files == []
```

Plus 7 vault nodes created with typed edges. The vault is the proof of
understanding, not just the tests.

---

## Reflect

> **Solo:** You wrote `os.replace(temp, target)` instead of streaming directly to the file. Without looking at the code, explain to yourself in one sentence why this matters. If you can't explain it without using the word "atomic," try again.

> **Group:** The file is described as "the source of truth — never derived from anything else." But the `content_hash` in the DB is derived from the file. Is the hash part of the source of truth, or part of the derived index? Where exactly is the boundary, and does the distinction matter for how you reason about correctness?
