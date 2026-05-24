# Implementation Plan — Security & Deployment Section

> **Status:** Pre-implementation. All decisions are agreed (see `analysis-and-enhancements.md`).
> This document covers S1–S4 and A3 only. It is the direct input for the developer who
> implements those items.

---

## Part 1 — Security Callout Content (S1–S4)

Each section below is the exact content block that should be inserted into its phase
document. Formatting follows the existing style in the learning path: plain prose
callout, code blocks with Python or YAML, no headers deeper than `###`.

---

### S1 — SQL Injection (insert into phase-02-storage-and-indexing.md)

Place this section immediately after the "Thread Safety" concept and before the
"Complete DB Schema" block.

---

> **Security: Parameterized Queries — Never Do This**
>
> Every query in `db.py` must use parameterized queries. This is the single most
> important security rule in any database layer, and it is also the rule beginners
> most commonly get wrong by accident, not by intent.

**The vulnerable pattern (never write this):**

```python
# WRONG — string formatting opens a SQL injection vector
def search(self, query: str) -> list[Node]:
    cursor = self.conn.execute(
        f"SELECT * FROM nodes_fts WHERE nodes_fts MATCH '{query}'"
    )
    return [self._row_to_node(row) for row in cursor.fetchall()]
```

If `query` is `' OR 1=1 --`, this executes as:

```sql
SELECT * FROM nodes_fts WHERE nodes_fts MATCH '' OR 1=1 --'
```

which bypasses the search entirely and returns every row. Against a personal
knowledge graph this is not a network attack — but the same mistake in any
boundary-facing code (API query parameters, filenames, tag filters) produces a
real vulnerability. The habit must be built here.

**The safe pattern (always do this):**

```python
# CORRECT — ? placeholder, value passed as a tuple
def search(self, query: str) -> list[Node]:
    cursor = self.conn.execute(
        "SELECT * FROM nodes_fts WHERE nodes_fts MATCH ?",
        (query,)          # <-- the comma makes this a tuple, not a string
    )
    return [self._row_to_node(row) for row in cursor.fetchall()]
```

The SQLite driver sends the query string and the values to the database engine
separately. The engine never concatenates them — it cannot misinterpret the value
as SQL syntax regardless of what it contains.

**Three real examples from Akanga's own queries:**

```python
# Node lookup by UUID
cursor = self.conn.execute(
    "SELECT * FROM nodes WHERE id = ?",
    (node_id,)
)

# Tag filter (pass a LIKE pattern, not raw input)
tag_pattern = f"%{tag}%"
cursor = self.conn.execute(
    "SELECT * FROM nodes WHERE tags LIKE ?",
    (tag_pattern,)
)

# Edge lookup
cursor = self.conn.execute(
    "SELECT * FROM edges WHERE source_id = ? AND relation_id = ?",
    (source_id, relation_id)
)
```

**Why this also prevents logic errors (beyond security):**

A misplaced comma or quote in a hand-formatted query string produces a syntax error
at runtime — difficult to trace in a test failure. Parameterized queries move
all value binding to the driver, which means the query string is a constant that
can be read and reviewed at a glance. Linters and static analysis tools can catch
typos in constant SQL strings; they cannot catch errors in f-strings that assemble
SQL dynamically.

> **Common Pitfall:** Forgetting the trailing comma when passing a single value:
> `(node_id)` is just `node_id` in Python — a string, not a tuple. The driver
> will try to iterate it character by character and raise an error or silently
> bind the wrong value. Always write `(node_id,)`.

---

### S2 — CORS Configuration (insert into phase-06-rest-api.md)

Place this section after the "Key Design Decisions" block and before "What You Build".

---

> **Security: CORS and Localhost Binding**

**What CORS is and why it matters for a local server:**

CORS (Cross-Origin Resource Sharing) is a browser security mechanism. When a
web page running at `http://evil.example.com` makes a JavaScript `fetch()` call
to `http://localhost:8000/api/v1/nodes`, the browser first sends a preflight
`OPTIONS` request asking: "does this server permit requests from my origin?" If
the server does not respond with the correct `Access-Control-Allow-Origin` header,
the browser blocks the response before the JavaScript code ever sees it.

This protects you from a class of attack called Cross-Site Request Forgery (CSRF):
a malicious web page silently reading your vault via your local server because
you happened to have a browser tab open. The attack does not require the user to
click anything — loading the page is enough.

**Why localhost binding is the first line of defence:**

The Akanga server binds to `127.0.0.1` by default. This means it only accepts
TCP connections from the same machine. A browser tab on the same machine *can*
reach it (CORS applies), but no device on your local network can reach it at all
— the connection is refused at the network layer before CORS is even relevant.

If you change `--host 0.0.0.0`, the server accepts connections from any device on
your network. At that point, anyone on the same Wi-Fi network can reach your vault.
CORS will not protect you from this — CORS only runs in browsers. A `curl` command
on a network-adjacent machine bypasses it entirely.

```
127.0.0.1 (default)  →  network-level isolation  →  no auth needed
0.0.0.0              →  network-exposed           →  CORS alone is not enough
```

**Safe CORS configuration for local-only use:**

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type"],
)
```

`allow_origins` should list only the specific origins that need access: if you
are building a local web GUI that runs at `localhost:3000`, list exactly that.
Do not use `allow_origins=["*"]` — a wildcard allows any browser tab on any
site to read your vault content.

**What becomes dangerous if you expose on 0.0.0.0:**

| Setting | Localhost only | 0.0.0.0 (network-exposed) |
|---|---|---|
| `allow_origins=["http://localhost:3000"]` | Safe | Still safe for browsers, but non-browser callers bypass CORS |
| `allow_origins=["*"]` | Convenient | Any browser tab on any site can read your vault |
| No CORSMiddleware at all | Same-origin only (browser) | No browser cross-origin access |

**Relationship to path traversal protection:**

Path traversal protection (already in this phase) prevents a caller from escaping
the vault directory via crafted filenames. CORS prevents untrusted browser tabs from
reaching the server at all. These are independent controls at different layers:
network binding → CORS → path validation. Each layer fails open if the one above it
is misconfigured. All three need to be correct simultaneously.

> **If you expose on 0.0.0.0 for a legitimate reason** (e.g., accessing your vault
> from a phone on the same network), add basic HTTP authentication or bind to a VPN
> interface. There is no authentication mechanism in Akanga MVP — this is a documented
> and deliberate scope decision for a single-user local tool, but you must understand
> what you are trading away when you change the default binding.

---

### S3 — YAML Safe Loader (insert into phase-00-file-system-as-database.md)

Place this section immediately after the "YAML Frontmatter" concept definition and
before the "UUID" concept.

---

> **Security: YAML Injection and the Safe Loader**

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
attachment) could carry this payload.

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

**How to verify the loader in use programmatically:**

```python
import frontmatter
import yaml

# python-frontmatter delegates YAML parsing to a Handler.
# The default YAMLHandler passes yaml.safe_load internally.
# You can confirm by inspecting the handler:
handler = frontmatter.YAMLHandler()
print(handler.__class__.__name__)  # YAMLHandler

# And verify it raises on a !!python/ tag:
assert_safe_frontmatter_loader()  # write this as a one-line utility in your test suite
```

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
payloads, anything not written by your own `write()` function.

> **Akanga node to create:** `YAML Injection` | note | `solves` → `YAML Safe Loader`;
> `is_a` → `Injection Attack`; `is_mitigated_by` → `python-frontmatter SafeLoader`

---

### S4 — Git Remote Trust (insert into phase-07-version-control.md)

Place this section after the ".gitignore as Contract" concept and before the
"Vault Nodes to Create" table.

---

> **Security: Auto-Push and Remote Trust**

**Why auto-push to a public remote exposes your knowledge graph:**

The vault contains everything you think — notes, research threads, unfinished ideas,
references to projects, relationships between concepts. A single `git push` to a
public GitHub repository makes every node, every edge, and the complete history of
your thinking permanently public and indexed by search engines. Unlike a database
breach, a git push to a public repo is not reversible: forks and crawlers may
already have the content before you delete the repository.

`auto_push: false` is the correct default and should remain the default for any
Akanga installation. Do not change it to `true` without understanding exactly
where the content is going.

**The safe defaults and what each setting means:**

```yaml
git:
  enabled: true
  commit_on_session_end: true   # local commits only — always safe
  commit_interval: null         # periodic local commits — always safe
  auto_push: false              # NEVER enable without reading this section
  remote: origin
```

Local commits (`commit_on_session_end`, `commit_interval`) produce only local
git history. They are safe regardless of what `remote` is configured — nothing
leaves your machine. The only setting that sends data off-machine is `auto_push: true`.

**Private remote vs public remote:**

| Remote type | Auto-push safe? | Conditions |
|---|---|---|
| Self-hosted Gitea (LAN-only, no public route) | Yes | Server not reachable from the internet |
| Private GitHub/GitLab repository | Yes | Repository visibility set to Private; your account uses SSH key or token auth |
| Public GitHub/GitLab repository | No | Any push is permanently public |
| Shared team repository | Depends | Does every team member intend to share your vault content? |
| Cloud sync via git (Dropbox-as-remote, etc.) | Depends | Who has access to the sync destination? |

**How to audit your vault before enabling auto-push:**

Before enabling `auto_push: true` for the first time, review what you are about
to send:

```bash
# 1. Check the configured remote:
git remote -v

# 2. Check the remote repository's visibility (GitHub CLI):
gh repo view --json isPrivate

# 3. Review what files are tracked (nothing in .gitignore should appear):
git ls-files

# 4. Check that .akanga.db is NOT tracked:
git ls-files | grep -E '\.(db|db-wal|db-shm)$'  # should return nothing

# 5. Review recent commits before they go up:
git log --oneline -20
git show HEAD
```

Only after this audit should you change `auto_push` to `true`.

**The explicit push keybinding (`P`) is intentional:**

The TUI's `P` keybinding (push to remote with confirmation) exists precisely
because push is the one irreversible action in Akanga's version control model.
The confirmation dialog shows what branch is being pushed and to which remote.
Read it before pressing Enter. This is not a UX nicety — it is the control
point for an action that cannot be undone.

> **If you want automatic off-site backup:** configure a private repository on a
> self-hosted Gitea instance or a private GitHub repo, verify the remote URL with
> `git remote -v`, and only then set `auto_push: true`. The backup value of
> auto-push is real; the risk is in doing it without knowing where the data goes.

---

## Part 2 — docs/deployment.md

See the separate `docs/deployment.md` file written as part of this plan. Content
summary:

- macOS launchd plist (`~/Library/LaunchAgents/com.akanga.server.plist`)
- Linux systemd user service (`~/.config/systemd/user/akanga.service`)
- Makefile targets (`serve`, `tui`, `index`, `mcp-server`)
- tmux named-session approach (recommended for developer use)

---

## Part 3 — Security Review of the Learning Path

### Assessment: Is Security a First-Class Concern?

The short answer is no — and this is worth addressing structurally, not just by
adding four callout boxes.

**What the current path does well:**

- Phase 6 introduces "Path Traversal Protection" as a first-class concept with a
  named Akanga vault node. It is not a footnote; it is a concept the learner must
  understand well enough to create a node and wire edges.
- Phase 7's `auto_push: false` default is a security decision baked into the design,
  not retrofitted.
- The file-as-database model (Phase 0) gives learners an implicit lesson in
  minimising attack surface: there is no daemon listening on a port, no persistent
  process, no credentials to leak during parsing.

**What the current path does not do:**

The security callouts (S1–S4) are bolt-ons. They teach "don't do this specific bad
thing here" rather than "here is the mental model for thinking about trust
boundaries." A learner who passes all four callouts has not necessarily learned
to ask "where is the trust boundary?" in a new context.

The phases also introduce security in the wrong order for a learning path:

```
Phase 0  →  file parsing         →  YAML injection (S3)           [added]
Phase 2  →  database layer       →  SQL injection (S1)             [added]
Phase 6  →  REST API             →  path traversal (existing)
Phase 6  →  REST API             →  CORS (S2)                      [added]
Phase 7  →  version control      →  remote trust (S4)              [added]
```

This is correct chronologically (each issue is introduced when the vulnerable
component is built), but the learner has no framework for why these are the right
questions to ask. They appear as surprising facts rather than as instances of a
general pattern.

**Structural recommendations:**

1. **Add a "Trust Boundary" concept to Phase 0's concepts section.** Phase 0 already
   teaches the distinction between the file (source of truth) and the DB (derived).
   That is a trust boundary. Name it. "Code that consumes user-controlled files must
   treat their content as untrusted input." This gives learners a framework they can
   apply at every subsequent phase rather than learning each injection variant in
   isolation.

2. **Add a one-paragraph "Security posture" note to Phase 6's introduction**, before
   the concepts. Something like: "The REST API is the first surface that accepts
   arbitrary input from a caller who is not your own code. Every phase before this
   one consumed input you controlled (files you wrote, a DB you built). From this
   phase forward, you validate everything at the boundary and trust nothing from
   outside it. The security controls in this phase — path traversal, CORS — follow
   directly from this posture."

3. **Thread the "derived index" lesson into the SQL injection callout.** The DB is
   already framed as expendable and reconstructible. The learner already understands
   "the DB is not sacred." Extend that lesson: "because the DB is derived from files
   you control, SQL injection here has limited blast radius — an attacker can corrupt
   the index, not the vault. But the same parameterized-query habit must be carried
   to any DB layer that is not expendable."

4. **Phase 8 (AI integration) needs a security section that does not yet exist.**
   The MCP server introduces a new trust boundary: an AI model consuming your vault
   content. A learner who builds Phase 8 should understand: (a) what content the
   model can see, (b) whether the MCP server is local-only or network-exposed, and
   (c) what happens if the model is instructed (via a prompt-injected node) to
   perform destructive operations on the vault. Prompt injection via vault nodes is
   a real attack surface for any RAG or MCP-based system.

5. **Do not add a standalone "security phase."** Security taught as a separate module
   is security that learners treat as optional. The structural changes above keep
   security woven into the phases where the code that requires it is built. The
   additions are small (one paragraph each) and load-bearing: they give learners the
   frame before the specific callouts, rather than after.

**Verdict:** The four callouts (S1–S4) should be added as planned. The structural
changes above are recommended but are not blocking — they are the difference between
learners who know four specific rules and learners who can derive the rules themselves.

---

## Part 4 — Task List

Tasks are in dependency order. Each task is independently completable once its
dependencies are done. Effort estimates assume a developer familiar with the
codebase.

---

### T1 — Verify python-frontmatter safe loader (S3 prerequisite)

**Depends on:** nothing  
**Effort:** 30 minutes  
**Who:** any contributor

Run the verification script from S3 against the current `python-frontmatter`
version pinned in `pyproject.toml`. Confirm that `yaml.constructor.ConstructorError`
is raised on a `!!python/object/apply:` tag. Document the version number and
loader class name in the S3 callout.

**Acceptance criteria:**
- Verification script runs in the Phase 0 dev environment without error.
- Output shows `ConstructorError` (not silent success).
- The confirmed version is noted in the callout text (e.g., "verified against
  `python-frontmatter==3.1.0`").

---

### T2 — Insert S3 callout into phase-00-file-system-as-database.md

**Depends on:** T1  
**Effort:** 20 minutes  
**Who:** any contributor

Insert the S3 content block (Part 1, S3 section above) into phase-00 after the
"YAML Frontmatter" concept definition. Add `YAML Injection` to the "Vault Nodes
to Create" table.

**Acceptance criteria:**
- Section is present in the file at the correct position.
- The `YAML Injection` node row is added to the vault nodes table with the edges
  listed in the callout.
- No existing content is modified.

---

### T3 — Insert S1 callout into phase-02-storage-and-indexing.md

**Depends on:** nothing (independent of T1/T2)  
**Effort:** 20 minutes  
**Who:** any contributor

Insert the S1 content block (Part 1, S1 section above) after "Thread Safety" and
before "The Complete DB Schema". No vault node addition required (the callout
addresses implementation practice, not a new concept node).

**Acceptance criteria:**
- Section is present at the correct position.
- Code examples are syntactically correct Python.
- The "never do this" example is clearly visually distinct from the "always do
  this" example (use the comment-based labeling shown above).

---

### T4 — Insert S2 callout into phase-06-rest-api.md

**Depends on:** nothing  
**Effort:** 25 minutes  
**Who:** any contributor

Insert the S2 content block (Part 1, S2 section above) after "Key Design Decisions"
and before "What You Build". Add `CORS` to the "Vault Nodes to Create" table with
edges: `is_a` → `Browser Security Mechanism`; `solves` → `Cross-Site Request
Forgery`; `is_applied_in` → `Akanga API`.

**Acceptance criteria:**
- Section is present at the correct position.
- The comparison table (localhost vs 0.0.0.0) renders correctly in Markdown.
- The `CORSMiddleware` import and code example is syntactically correct.
- Vault node row is added.

---

### T5 — Insert S4 callout into phase-07-version-control.md

**Depends on:** nothing  
**Effort:** 20 minutes  
**Who:** any contributor

Insert the S4 content block (Part 1, S4 section above) after ".gitignore as
Contract" and before "Vault Nodes to Create". Add `Remote Trust` to the vault
nodes table: `is_a` → `Security Posture`; `qualifies` → `Git as User Feature`;
`is_applied_in` → `GitManager`.

**Acceptance criteria:**
- Section is present at the correct position.
- The audit bash commands are correct and runnable on a macOS/Linux shell.
- The remote type comparison table renders correctly.
- Vault node row is added.

---

### T6 — Write docs/deployment.md

**Depends on:** nothing (standalone document)  
**Effort:** 2 hours  
**Who:** any contributor with macOS and Linux experience

Write the complete `docs/deployment.md` as specified in Part 2 and the A3 decision.
The document must cover all four sections: launchd plist, systemd user service,
Makefile targets, and tmux approach.

**Acceptance criteria:**
- File exists at `docs/deployment.md`.
- The launchd plist is a complete, valid XML plist — not a template with
  placeholders. Paths use `$HOME`-equivalent expansions or clear instructions for
  substitution.
- The systemd unit file is complete and the `ExecStart=` path uses the `uv run`
  invocation consistent with the project's `pyproject.toml`.
- All `launchctl` and `systemctl` commands are listed: load, unload, status, logs.
- The Makefile in the document is standalone (a learner could paste it into their
  project without modification), and all targets use `uv run python -m
  akanga_core.cli` consistent with the existing `noteapp/Makefile`.
- The tmux section includes the exact `tmux new-session` and `tmux attach` commands.

---

### T7 — Structural security additions (optional, recommended)

**Depends on:** T2, T3, T4, T5 all merged  
**Effort:** 1.5 hours  
**Who:** contributor comfortable editing the conceptual framing of the docs

Implement the four structural recommendations from Part 3:

- Add "Trust Boundary" paragraph to Phase 0 Concepts.
- Add "Security posture" paragraph to Phase 6 introduction.
- Thread "derived index" lesson into S1 callout (already partially written — add
  one paragraph connecting the two concepts).
- Add Phase 8 security section covering MCP trust boundary and prompt injection
  risk via vault nodes.

**Acceptance criteria:**
- Each addition is 1–2 paragraphs maximum — no new top-level sections.
- Phase 8 security section covers: what content the model sees, local-only binding
  for the MCP server, and prompt injection via node content as a named risk.
- No existing concept definitions are modified — these are additions only.

---

### T8 — Review and cross-link

**Depends on:** T2, T3, T4, T5, T6 all done  
**Effort:** 45 minutes  
**Who:** any contributor

Read the modified phase docs and `deployment.md` end-to-end as a learner would.
Verify:

- S3 in Phase 0 → learner knows to run the verification before trusting the library.
- S1 in Phase 2 → both code examples present, "never" and "always" are unambiguous.
- S2 in Phase 6 → CORS section does not contradict the "localhost binding" design
  decision that precedes it.
- S4 in Phase 7 → the audit commands work on a fresh git repo with no remote.
- `deployment.md` → tmux approach, launchd plist, and systemd unit are each
  independently actionable without reading the others.

Cross-link `deployment.md` from the Phase 6 and Phase 7 docs with a one-line
note: "For running Akanga unattended, see `docs/deployment.md`."

**Acceptance criteria:**
- At least one person who did not write the content has read it and confirmed it
  is clear.
- Cross-links are in place.
- No broken relative paths in the Markdown links.

---

### Summary Table

| Task | Dependency | Effort | Blocks |
|---|---|---|---|
| T1 — Verify safe loader | — | 30 min | T2 |
| T2 — S3 into phase-00 | T1 | 20 min | T8 |
| T3 — S1 into phase-02 | — | 20 min | T8 |
| T4 — S2 into phase-06 | — | 25 min | T8 |
| T5 — S4 into phase-07 | — | 20 min | T8 |
| T6 — docs/deployment.md | — | 2 h | T8 |
| T7 — Structural additions | T2–T5 | 1.5 h | — |
| T8 — Review and cross-link | T2–T6 | 45 min | — |
| **Total** | | **~6 h** | |

T1, T3, T4, T5, and T6 can all be parallelised across different contributors.
T2 must wait for T1. T7 and T8 are the only tasks that require all prior work to
be merged first.
