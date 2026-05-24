# YAML and Markdown Frontmatter

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
active:
  action: http
  url: https://example.com/health
  interval: 60
  timeout: 5
```

Equivalent Python:

```python
{"active": {"action": "http", "url": "https://example.com/health", "interval": 60, "timeout": 5}}
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

## Akanga's Node Frontmatter Format

Every node in the vault is a `.md` file with this frontmatter shape:

```yaml
---
id: "550e8400-e29b-41d4-a716-446655440000"   # UUID, generated once and never changed
title: My Node                                 # human-readable name
type: note                                     # note | active | active-service | diagram | virtual
tags: [tag1, tag2]                             # optional list of strings
active:                                        # only for active/active-service nodes
  action: http                                 # http | tcp
  url: https://example.com/health
  interval: 60                                 # seconds between checks
  timeout: 5                                   # seconds before giving up
virtual:                                       # only for virtual nodes
  url: https://github.com/user/repo
  external_type: github                        # github | webpage | app | file | api
  description: External resource description
---

Markdown body content here. [[wikilinks]] and [markdown links](other-file.md) are supported.
```

Key design decisions:

- **`id` is a UUID string, quoted.** Quoting prevents YAML from misinterpreting UUID-like strings
  (hyphens are fine unquoted, but quoting makes intent explicit).
- **`type` drives behavior.** The parser, indexer, and active manager all branch on this field.
- **`active` and `virtual` sections are optional dicts.** Code checks `post.metadata.get("active")`
  and treats `None` as "no active config."
- **`tags` defaults to `[]`.** Always call `.get("tags", [])` — never assume the field exists.

---

## Akanga's Vault Config: `akanga.yaml`

In addition to per-node frontmatter, the vault root contains an `akanga.yaml` config file that
describes the vault itself. This is a plain YAML file (no Markdown, no frontmatter):

```yaml
owner: alice
default_workspace: personal

workspaces:
  - name: personal
    path: ./personal
  - name: work
    path: ./work

relations:
  - name: depends_on
    inverse: is_dependency_of
  - name: documents
    inverse: is_documented_by
  - name: references
    inverse: is_referenced_by
```

Reading it is straightforward:

```python
import yaml

with open("akanga.yaml") as f:
    config = yaml.safe_load(f)

owner = config["owner"]
workspaces = config.get("workspaces", [])
relations = config.get("relations", [])
```

This config is introduced in Phase 1 of the learning path. It lets users define custom relation
types with their inverses — a building block for the full graph model.

---

## In This Codebase

- **`src/akanga_core/parser.py`** — `parse_node(path)` calls `frontmatter.load()` and returns a
  `Node` dataclass. `write_node(path, node)` calls `frontmatter.dumps()` and writes atomically.
  All metadata access uses `.get()` with safe defaults.

- **Phase 1 work** — introduces `akanga.yaml` vault config. `yaml.safe_load` is the correct parser.
  The config schema includes `owner`, `default_workspace`, `workspaces`, and `relations`.

- **Never use `yaml.load` without `Loader=yaml.SafeLoader`** anywhere in this codebase. The vault
  directory is user-controlled, but it is still good practice to use `safe_load` everywhere.

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
