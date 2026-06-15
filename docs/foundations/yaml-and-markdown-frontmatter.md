# YAML and Markdown Frontmatter

**Audience:** Python developers working with YAML frontmatter in the vault · **Read time:** ~18 min

A practical guide for Python developers working with structured text files in a knowledge graph.

---

## What is YAML?

YAML ("YAML Ain't Markup Language") is a human-readable data serialization format. Where JSON uses
braces and brackets, YAML uses indentation and whitespace. It maps directly to the same data
structures you already use in Python: dicts, lists, strings, numbers, and booleans.

If you can read a Python dict, you can read YAML. The two are close enough that beginners often
confuse them — but the syntax rules are different.

---

## YAML Syntax Fundamentals

### Key-value pairs (mappings)

YAML mappings are like Python dicts. Each entry is `key: value` on its own line:

```yaml
title: My Note
type: note
created: 2024-01-15
priority: 3
```

Equivalent Python dict:

```python
{"title": "My Note", "type": "note", "created": "2024-01-15", "priority": 3}
```

### Lists (sequences)

Use a dash-space (`- `) prefix for each item:

```yaml
tags:
  - python
  - knowledge-graph
  - sqlite
```

Or inline (flow style) with square brackets:

```yaml
tags: [python, knowledge-graph, sqlite]
```

Both parse to the same Python list: `["python", "knowledge-graph", "sqlite"]`.

### Nested dicts

Indentation creates nesting. YAML requires consistent indentation (spaces only — never tabs):

```yaml
meta:
  status: draft
  priority: 2
  reviewed: false
```

Equivalent Python:

```python
{"meta": {"status": "draft", "priority": 2, "reviewed": False}}
```

### Scalar types

YAML infers types automatically:

```yaml
a_string: hello world
a_number: 42
a_float: 3.14
a_bool: true
nothing: null
```

Parses to:

```python
{"a_string": "hello world", "a_number": 42, "a_float": 3.14, "a_bool": True, "nothing": None}
```

### The `---` document delimiter

Three dashes on their own line signal the start of a YAML document. This is how frontmatter blocks
begin in Markdown files (more on that below). A second `---` (or `...`) signals the end of the
document. In standalone `.yaml` files you can omit it; in Markdown frontmatter it is required.

---

## Common YAML Gotchas

These are the mistakes that will bite you when writing or parsing YAML by hand.

### 1. `yes`, `no`, `true`, `false` are booleans — not strings

```yaml
enabled: yes      # bool True
disabled: no      # bool False
confirmed: true   # bool True
rejected: false   # bool False
```

If you want the literal string `"yes"`, you must quote it:

```yaml
answer: "yes"     # str "yes"
```

In YAML 1.1 (used by PyYAML by default) `on`/`off` are also booleans. This is a frequent source of
bugs when tag values like `on` or `off` are used without quotes.

### 2. Bare strings with colons need quoting

A colon followed by a space is the key-value separator. If your string contains `: `, YAML will
misparse it as a nested mapping:

```yaml
# BAD — YAML sees this as a key "url" with value "https" and then a broken mapping
url: https://example.com

# GOOD — quote it
url: "https://example.com"

# Also fine — no space after the colon in the value, so YAML handles it correctly
# (but quoting is safer and more explicit)
```

Akanga always quotes URLs and any string that contains special characters.

### 3. Indentation must be spaces, never tabs

YAML parsers reject tab characters. If you get a `ScannerError: found character '\t'`, check for
tabs in your YAML.

### 4. Trailing spaces matter in multiline strings

The `|` (literal block) and `>` (folded block) scalars are sensitive to trailing whitespace.
When in doubt, use quoted strings.

### 5. Duplicate keys are silently last-wins (in most parsers)

```yaml
title: First
title: Second  # This silently overwrites the first
```

PyYAML and `python-frontmatter` use the last value. No error is raised. Always lint your YAML.

---

## Implicit Typing: The Value You See Is Not the Type You Get

The "scalar types" rule above — YAML infers types automatically — is convenient right up until
it isn't. YAML resolves every *unquoted* scalar against a set of patterns, silently. Gotcha 1
(`yes`/`no` as booleans) is one instance of a much broader rule:

```yaml
due: 2026-07-01      # datetime.date(2026, 7, 1) — not the string "2026-07-01"
version: 1.0         # float 1.0 — not the string "1.0"
enabled: no          # bool False — the "Norway problem" (country code NO becomes False)
id: 0x1A             # int 26 — YAML 1.1 resolves hex literals
```

Parses to:

```python
{"due": datetime.date(2026, 7, 1), "version": 1.0, "enabled": False, "id": 26}
```

No warning, no error. The value the author *sees* in the file is not the type the program *gets*.

### Why this matters in Akanga

The parser stores the parsed metadata dict in `Node.frontmatter` as-is. If a node's frontmatter
contains an unquoted date, that dict now carries a `datetime.date` — which is **not
JSON-serializable**. Nothing fails at parse time; the break happens later, in whichever consumer
first calls `json.dumps()` on the frontmatter:

```python
import json, datetime

json.dumps({"due": datetime.date(2026, 7, 1)})
# TypeError: Object of type date is not JSON serializable
```

This is why the reference parser normalizes `date`/`datetime` values to ISO strings
at the parse boundary — the `_normalize_fm` helper in `parser.py` (a fix that
originated in noteapp, the codebase this curriculum is distilled from) — so no
downstream consumer ever sees a non-JSON type. You build this in Phase 2.

You can watch the mistyping happen in your Phase 0 environment:

```python
import frontmatter

post = frontmatter.loads("""---
due: 2026-07-01
version: 1.0
enabled: no
---
body""")
print({k: type(v).__name__ for k, v in post.metadata.items()})
# {'due': 'date', 'version': 'float', 'enabled': 'bool'}
```

### Defenses

1. **Quote ambiguous scalars.** Dates, version numbers, things that look like booleans, hex-ish
   IDs: `due: "2026-07-01"`, `version: "1.0"`, `enabled: "no"`. Quoting always produces a string.
2. **Normalize at the boundary.** Don't trust authors to quote. The parse function is the single
   place where raw YAML becomes program data — convert `date`/`datetime` to ISO strings (and
   reject or coerce any other non-JSON type) there, once, instead of defending in every consumer.
3. **Know your YAML version.** PyYAML implements YAML 1.1, where `yes`/`no`/`on`/`off` are
   booleans and `0x1A` is an int. The YAML 1.2 core schema drops those resolutions (only
   `true`/`false` are booleans), so two parsers can type the same file differently. Quoting and
   boundary normalization protect you under either schema.

---

## Markdown Frontmatter

Frontmatter is a YAML block embedded at the very top of a Markdown file, fenced by `---` delimiters:

```
---
id: "550e8400-e29b-41d4-a716-446655440000"
title: My Note
type: note
tags: [tag1, tag2]
---

# My Note

Markdown body content here.
```

The first `---` must be on line 1 of the file (no blank lines before it). Everything between the
two `---` lines is parsed as YAML. Everything after the closing `---` is the Markdown body.

This convention is used by Jekyll, Hugo, Obsidian, and many other tools. Akanga uses it for every
node in the vault.

### Why frontmatter?

It keeps structured metadata and human-readable content in the same file. You can open any node in
a text editor and read both the metadata and the body without any special tools. The file is still
valid Markdown — the frontmatter block just looks like a horizontal rule and a code block to
renderers that don't support it.

---

## `python-frontmatter`: Reading and Writing

The `python-frontmatter` library handles the parsing for you. It splits the file into metadata and
content, and serializes them back together.

### Installation

```bash
pip install python-frontmatter
# or with uv:
uv add python-frontmatter
```

### Reading a file

```python
import frontmatter

# Load from a file path
post = frontmatter.load("my-note.md")

# .metadata is a plain Python dict
print(post.metadata)
# {'id': '550e8400-e29b-41d4-a716-446655440000', 'title': 'My Note', 'type': 'note', 'tags': ['tag1', 'tag2']}

# .content is the Markdown body as a string (frontmatter stripped)
print(post.content)
# "# My Note\n\nMarkdown body content here."

# Access individual fields
node_id = post.metadata.get("id")
node_type = post.metadata.get("type", "note")  # default to "note"
tags = post.metadata.get("tags", [])
```

### Reading from a string

```python
import frontmatter

raw = """---
title: My Note
type: note
---

Body text here.
"""

post = frontmatter.loads(raw)  # note: loads() not load()
```

### Writing / updating

```python
import frontmatter

post = frontmatter.load("my-note.md")

# Mutate metadata
post.metadata["tags"] = ["updated", "tags"]
post.metadata["title"] = "Revised Title"

# Serialize back to a string
output = frontmatter.dumps(post)
print(output)
# ---
# id: 550e8400-e29b-41d4-a716-446655440000
# title: Revised Title
# type: note
# tags:
# - updated
# - tags
# ---
#
# Body text here.

# Write back to disk (akanga does this atomically — see below)
with open("my-note.md", "w") as f:
    f.write(output)
```

### Atomic writes

Writing directly to a file risks corruption if the process crashes mid-write. The safe pattern is
to write to a temporary file then replace:

```python
import os
import tempfile
import frontmatter

def write_node(path: str, post: frontmatter.Post) -> None:
    content = frontmatter.dumps(post)
    dir_name = os.path.dirname(path)
    # Write to a temp file in the same directory (ensures same filesystem)
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    # Atomic replace — either the old file or the new file, never a partial write
    os.replace(tmp_path, path)
```

Akanga's `parser.py` uses exactly this pattern.

---

## `yaml.safe_load` vs `yaml.load`

If you use the `pyyaml` library directly, always use `yaml.safe_load`:

```python
import yaml

# GOOD — safe_load parses only basic YAML types
data = yaml.safe_load("""
title: My Note
count: 42
""")
# {'title': 'My Note', 'count': 42}

# BAD — yaml.load with the default Loader can execute arbitrary Python code
# embedded in the YAML document. Never use this with untrusted input.
data = yaml.load(input_string)  # DANGEROUS — don't do this

# If you must use yaml.load, pass the SafeLoader explicitly:
data = yaml.load(input_string, Loader=yaml.SafeLoader)  # equivalent to safe_load
```

The attack vector: YAML supports a `!!python/object` tag that, with the default `Loader`, instructs
PyYAML to instantiate arbitrary Python objects. A malicious YAML file can execute code during
parsing. `safe_load` restricts parsing to the YAML core schema (strings, ints, floats, booleans,
lists, dicts, null) and raises an error on any constructor tag.

Rule: if you are parsing YAML from disk (user files, vault nodes, configs), always use `safe_load`.

---

## Security: Trust Boundaries and Safe Loading

This section expands on the attack above in the context of vault files — what YAML
injection looks like, how to verify your stack is safe, and what to do if a library
does not use safe loading by default.

**What YAML injection is:**

PyYAML's default `Loader` supports a tag system that can instantiate arbitrary
Python objects from YAML input. A frontmatter file containing:

```yaml
---
title: !!python/object/apply:os.system ["rm -rf /"]
---
```

would — with the unsafe loader — execute `os.system("rm -rf /")` the moment the
file is parsed. This is not a theoretical concern: it is a known, documented attack
against Python applications that parse untrusted YAML. A vault file modified by
another party (shared storage, cloned from a public repo, received as a file
attachment) could carry this payload. The trust boundary is the file system: every
`.md` file is input you did not necessarily author.

**How python-frontmatter handles this:**

`python-frontmatter` uses PyYAML's `SafeLoader` by default. `SafeLoader` only
permits YAML's built-in types (strings, integers, floats, booleans, lists,
dictionaries) and raises an error on any `!!python/` tag. You can verify this
yourself:

```python
import frontmatter

# This should raise yaml.constructor.ConstructorError, not execute anything:
malicious = """---
title: !!python/object/apply:os.system ["echo injected"]
---
body text
"""
try:
    post = frontmatter.loads(malicious)
    print("WARNING: loaded without error — check loader")
except Exception as e:
    print(f"Safe: raised {type(e).__name__}: {e}")
```

Run this in your Phase 0 environment. The expected output is a `ConstructorError`,
not a print from `os.system`.

**What to do if a library does not use safe loading by default:**

If you replace `python-frontmatter` with a different YAML library, or if a future
version changes the default, apply the safe loader explicitly:

```python
import yaml

# Never:
data = yaml.load(content)           # unsafe — uses FullLoader or Loader depending on version

# Always:
data = yaml.safe_load(content)      # SafeLoader — built-in types only
# or, explicitly:
data = yaml.load(content, Loader=yaml.SafeLoader)
```

The same rule applies to any YAML that arrives from outside: config files, webhook
payloads, anything not written by your own `write_node_file()`.

---

## Akanga's Node Frontmatter Format

Every node in the vault is a `.md` file with this frontmatter shape:

```yaml
---
id: a3f7c2be-1234-5678-abcd-ef0123456789        # UUID, generated once and never changed
title: Fast Thinking is Unreliable               # human-readable name
type: note                                       # note | reference
tags: [cognition, decision-making]               # list of strings; defaults to []
graph:                                           # workspace membership (dual-key: name + id)
  - name: Nhamandu
    id: a3f7c2be-1234-5678-abcd-ef0123456789
author: Arthur Pieri                             # stamped from akanga.yaml on create()
created_at: 2026-05-23
updated_at: 2026-05-23
meta:                                            # optional, user-defined, no schema
  status: draft
edges: []                                        # persistent typed edges (source of truth)
---

Markdown body content here. [[wikilinks]] and [[Other Note | supports]] typed
shorthand are supported.
```

Key design decisions:

- **`id` is a UUID, generated once and never changed.** The filename can drift (a
  rename repoints the path); the `id` is the authoritative identity that edges and
  `graph` references point at.
- **`type` is `note` or `reference` — and that is the whole vocabulary.** There is no
  `active`, `active-service`, `diagram`, or `virtual` node type; an earlier active-node
  design was cut (see `future-ideas.md`). The parser and indexer never branch on
  exotic types.
- **`graph` is workspace membership, dual-keyed.** Each entry carries `name` (a display
  cache that can go stale after a rename) and `id` (the authoritative UUID) — the same
  dual-key pattern as edges. An absent or empty `graph` auto-populates with the default
  workspace on first write-back.
- **`meta` is an optional, schema-free block** of user key/value pairs. It lives only in
  the `.md` file; the Phase 2 DB does not index it as a column (you read it by
  re-parsing the file).
- **`edges` is the persistent edge list** — the source of truth for typed links. Inline
  `[[Target | relation]]` shorthand in the body is folded into `edges:` by `write_back`
  at index time.
- **`tags` defaults to `[]`.** Always read it as `.get("tags", [])` — never assume the
  key exists.

---

## When Would Frontmatter Earn a Schema?

It is tempting to give frontmatter a typed schema — a Pydantic `FRONTMATTER_SCHEMA` with
`extra="allow"`, say — so a malformed note fails loudly instead of silently. Akanga sketched
that and **rejected** it. Three reasons:

1. **Frontmatter is user-authored text.** The vault is a folder of files the user owns and
   edits in any editor. A schema turns an honest typo (`tag:` instead of `tags:`) into a
   *parse failure* on a file the user controls — the tool refusing to open the user's own
   note. Contrast Phase 6: the REST API's request bodies ARE Pydantic-validated, because the
   trust boundary there is different — the bytes arrive from a client over the wire, not from
   a file the user hand-edited.
2. **`extra="allow"` launders the known keys.** Keeping unknown keys sounds safe, but Pydantic
   still coerces and re-emits the keys it *does* know — silently rewriting the user's text (a
   quoted UUID comes back unquoted; a date string becomes a `date` object) on round-trip.
3. **The vault must round-trip.** `parse → write_back` has to return a file byte-near the
   original; an aggressive normalization layer breaks that contract.

What Akanga does instead is one **targeted coercion at the parse boundary** — `_normalize_fm`
fixes only the few shapes that actually bite (see *Implicit Typing: The Value You See Is Not
the Type You Get* above — the Norway problem, dates, hex-looking strings) and leaves
everything else verbatim.

**The rule:** validate at boundaries you own (the API), normalize at boundaries you don't
(user files); reach for a real schema only when a wrong shape must be a hard error.

---

## Akanga's Vault Config: `akanga.yaml`

In addition to per-node frontmatter, the vault root holds an `akanga.yaml` config file
describing the vault itself. It is a plain YAML file (no Markdown, no frontmatter),
created by `make vault-init`:

```yaml
# akanga.yaml
owner: Arthur Pieri
default_workspace:
  name: Nhamandu
  id: a3f7c2be-1234-5678-abcd-ef0123456789   # generated at vault-init, never changes
workspaces:
  - name: ProjectX
    id: b2c3d4e5-abcd-ef01-2345-678901234567
  - name: BookNotes
    id: c3d4e5f6-bcde-f012-3456-789012345678
```

Read it with `safe_load`:

```python
import yaml

with open("akanga.yaml") as f:
    config = yaml.safe_load(f)

owner = config["owner"]
default_workspace = config["default_workspace"]   # dict: {name, id}
workspaces = config.get("workspaces", [])
```

`create()` reads this on every new node to stamp `author` and assign the default
workspace as the node's first `graph` entry.

**Relation types do NOT live here.** The 72 built-in relations live in
`docs/foundations/relation-vocabulary.md`, and custom relations are minted on demand —
`write_back` assigns a fresh UUID `relation_id` to any unknown relation name, no
pre-registration required. (Phase 1B sketches an optional `custom_relations:` block for
*soft validation* of those names; it is a deferred spec, not something `akanga.yaml`
requires today.)

---

## In Your Implementation

- **`parser.py`** (Phase 0) — `parse_node_file(path)` calls `frontmatter.load()` and
  returns a `Node` dataclass; `write_node_file(path, frontmatter_dict, content)` calls
  `frontmatter.dumps()` and writes atomically. All metadata access uses `.get()` with
  safe defaults.
- **`create()`** (Phase 0) — reads `akanga.yaml` with `yaml.safe_load`, stamps `author`,
  and assigns `default_workspace` as the first `graph` entry.
- **Phase 1B** — adds the workspace registry and the deferred `custom_relations:`
  soft-validation spec; relation *types* are still vocabulary + UUID-minted, never an
  `akanga.yaml` schema.
- **Never `yaml.load` without `SafeLoader`.** The vault is user-controlled text;
  `safe_load` everywhere is the rule, not a nicety.

---

## Quick Reference

| Concept | YAML | Python |
|---|---|---|
| String | `hello` or `"hello"` | `"hello"` |
| Integer | `42` | `42` |
| Float | `3.14` | `3.14` |
| Boolean | `true` / `false` / `yes` / `no` | `True` / `False` |
| Null | `null` or `~` | `None` |
| List | `[a, b]` or dash-prefixed | `["a", "b"]` |
| Dict | `key: value` | `{"key": "value"}` |
| Nested | indented `key: value` | nested dict |

| Task | Code |
|---|---|
| Load frontmatter | `post = frontmatter.load(path)` |
| Get metadata | `post.metadata["title"]` |
| Get with default | `post.metadata.get("tags", [])` |
| Get body | `post.content` |
| Serialize | `frontmatter.dumps(post)` |
| Parse plain YAML | `yaml.safe_load(f)` |
