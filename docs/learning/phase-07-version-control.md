# Phase 7 — Version Control as a Feature

**Core concept:** The vault is a directory of Markdown files that change over time.
That is exactly what git was built for. The insight is treating git not as optional
developer infrastructure but as a first-class user feature: every node you write,
edit, or delete is tracked automatically. Your knowledge graph has a complete,
navigable history from day one — without you thinking about it.

**What makes this non-obvious:** The hard part is not the git operations themselves
(those are one-liners with GitPython). The hard part is *when* to commit and *what*
to commit. Naive solutions — commit on every save, commit on every navigate-away —
produce noisy histories that defeat the purpose. The right model is an event log
with a smart squash step: record everything, clean it up before committing.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Implement a GitPython wrapper with non-fatal error handling
- Understand why git errors must be swallowed (git is optional, not required)
- Implement debounced auto-commit (5s) that batches rapid file changes
- Distinguish `is_dirty`, `status`, `commit`, and `push` — and when each is needed

---

## Before You Start — 2-Minute Self-Assessment

Check each item you can answer confidently. If you can't check 3 or more, review the linked foundation doc before proceeding.

- [ ] I understand git commit workflow (add → commit → push) → See `docs/foundations/git-basics.md`
- [ ] I know how to use GitPython's `Repo` class → See `docs/foundations/git-basics.md`
- [ ] I've completed Phases 0–6

---

## Concepts

### Git as User Feature

Most tools treat version control as a developer concern. Akanga treats it as a user
concern: the history of your thinking is as valuable as the thinking itself. Every
auto-commit is a dated snapshot of your knowledge graph. You can `git log` to see
your editing sessions, `git diff` a specific note to see how your understanding of
a topic evolved, or `git restore` a node you deleted by accident. The vault's git
history is the undo system, the audit trail, and the backup — all without the user
ever running a git command.

> Akanga node: `Git as User Feature`

→ Foundation doc: `docs/foundations/git-basics.md`

### GitPython

A Python library that wraps git operations without shelling out: `Repo.init()`,
`repo.index.add()`, `repo.index.commit()`, `origin.push()`. Raises `GitCommandError`
on failure. Akanga always catches this and logs it as a warning — never re-raises.
Git failure is non-fatal by design.

> Akanga node: `GitPython`

→ Foundation doc: `docs/foundations/git-basics.md`

### Change Queue

An append-only in-memory log of write events, populated by the EventBus. Every
`node_created`, `node_updated`, or `node_deleted` event adds an entry:

```python
@dataclass
class ChangeEntry:
    type: str        # "create" | "edit" | "delete"
    node_id: str
    title: str
    timestamp: str
```

Reads never append to the queue. The queue is the raw, unfiltered record of what
happened in a session — it may contain the same node multiple times if the user
edited it, left, and returned. The queue does not commit anything by itself; it only
records. Commits are triggered separately (see Commit Triggers).

> Akanga node: `Change Queue`

### Squash Algorithm

Before committing, the squash step collapses the raw event log into a clean summary:

```python
def squash(queue: list[ChangeEntry]) -> CommitSummary:
    creates, edits, deletes = {}, {}, {}

    for entry in queue:
        if entry.type == "create":
            creates[entry.node_id] = entry.title
        elif entry.type == "edit":
            edits[entry.node_id] = entry.title
        elif entry.type == "delete":
            deletes[entry.node_id] = entry.title
            creates.pop(entry.node_id, None)  # created + deleted → nothing

    # created then edited → just created (no separate edit entry)
    for nid in creates:
        edits.pop(nid, None)

    # edited then deleted → just deleted
    for nid in deletes:
        edits.pop(nid, None)

    return CommitSummary(
        created=list(creates.values()),
        edited=list(edits.values()),
        deleted=list(deletes.values()),
    )
```

Example: `edit A → read B → edit A → read C → edit A` produces queue entries
`[edit:A, edit:A, edit:A]` → squashed to `{edited: ["Note A"]}` → one commit,
message: `"update: Note A"`. The user's editing pattern never leaks into git history.

> Akanga node: `Squash Algorithm`

### Queue Persistence

The queue is persisted to `.akanga/commit_queue.json` after every append. On startup,
Akanga checks for a non-empty persisted queue — if found, it auto-commits it
immediately before starting the session. This means a previous session's work is
never lost even if the process was killed, the machine crashed, or the app was
force-quit. The persistence file is excluded from git tracking (it's internal state,
not vault content).

> Akanga node: `Queue Persistence`

### Commit Triggers

Three independent triggers decide when to squash and commit. All are configurable
in `akanga.yaml`:

**Session-end (always on):** When the user quits Akanga cleanly (`q`, SIGINT,
SIGTERM, or FastAPI lifespan shutdown), the queue is squashed and committed if
non-empty. This is the safety net — every session ends with a commit. The message
summarises the whole session: `"session: add BFS; update: Akanga, SQLite"`.

**Periodic (opt-in, default off):** An asyncio timer fires every N minutes (user-
configured). If the queue is non-empty, squash and commit. Useful for users who keep
Akanga open for hours. Message prefix: `"auto:"`.

**Manual (`C` keybinding, always available):** Opens a commit overlay in the TUI
showing the squashed summary and a pre-filled message the user can edit before
committing. The only trigger that shows the user what they're committing before it
happens.

> Akanga node: `Commit Triggers`

### Commit Message Generation

Generated messages are human-readable in `git log`:

```
1 create            →  "add: BFS"
1 edit              →  "update: Fast Thinking is Unreliable"
3 edits             →  "update: 3 notes (Fast Thinking, Akanga, SQLite)"
mixed               →  "add: BFS; update: Akanga; delete: Old Note"
first commit ever   →  "init: akanga vault"
periodic trigger    →  "auto: 2 notes updated"
```

If the node title is too long to fit cleanly, truncate with `…`. The message is
always overridable when committing manually via `C`.

> Akanga node: `Commit Message Generation`

### Non-Fatal Git Errors

Git can fail for many reasons: no remote configured, network timeout, no commits yet
(empty repo cannot push), detached HEAD, filesystem permission issues. None of these
should crash or degrade Akanga's core functionality. All git operations are wrapped
in `try/except GitCommandError` (and bare `except Exception` for edge cases). Failures
are logged at WARNING level. The EventBus never receives a git error. The queue is
NOT cleared on a failed commit — it will be retried at the next trigger.

> Akanga node: `Non-Fatal Git Errors`

### .gitignore as Contract

The `.gitignore` written on `--git-init` is a declaration of Akanga's architecture:
what is vault (tracked) vs what is derived/internal (untracked). Tracked: all `.md`
files, `akanga.yaml`. Untracked: `.akanga.db` (derived index — expendable), `.venv/`,
`__pycache__/`, `.akanga/` (internal state including the commit queue). The file
documents the source-of-truth boundary as clearly as any README.

> Akanga node: `.gitignore as Contract`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Git as User Feature` | note | `contrasts_with` → `Git as Dev Tool`; `enables` → `Knowledge History`; `is_applied_in` → `Akanga` |
| `GitPython` | reference | `implements` → `Git as User Feature`; `is_applied_in` → `GitManager` |
| `Change Queue` | note | `is_applied_in` → `GitManager`; `uses` → `Event Bus`; `enables` → `Squash Algorithm` |
| `Squash Algorithm` | note | `consumes` → `Change Queue`; `enables` → `Commit Message Generation`; `is_applied_in` → `GitManager` |
| `Queue Persistence` | note | `qualifies` → `Change Queue`; `solves` → `Work Loss on Crash`; `is_applied_in` → `Akanga App` |
| `Commit Triggers` | note | `is_applied_in` → `GitManager`; `uses` → `Change Queue`; `uses` → `asyncio` |
| `Commit Message Generation` | note | `is_applied_in` → `GitManager`; `enables` → `Readable Git Log` |
| `Non-Fatal Git Errors` | note | `qualifies` → `GitManager`; `is_applied_in` → `Akanga App` |
| `.gitignore as Contract` | note | `qualifies` → `Derived Index`; `is_applied_in` → `Akanga Vault` |

---

## What You Build

**`commit_queue.py`** — `ChangeQueue`:

```python
@dataclass
class ChangeEntry:
    type: str        # "create" | "edit" | "delete"
    node_id: str
    title: str
    timestamp: str

@dataclass
class CommitSummary:
    created: list[str]
    edited: list[str]
    deleted: list[str]

    @property
    def is_empty(self) -> bool:
        return not (self.created or self.edited or self.deleted)

class ChangeQueue:
    def __init__(self, persist_path: Path): ...

    def append(self, entry: ChangeEntry):
        """Add entry and persist to disk."""

    def squash(self) -> CommitSummary:
        """Collapse raw log → clean summary (dedup, cancel, reconcile)."""

    def generate_message(self, summary: CommitSummary, prefix: str = "") -> str:
        """Human-readable commit message from squashed summary."""

    def clear(self):
        """Called after successful commit. Clears memory + disk."""

    def load(self):
        """Load persisted queue on startup. Auto-commits leftover if non-empty."""
```

**`gitmgr.py`** — `GitManager`:

```python
class GitManager:
    def __init__(self, vault: Path, queue: ChangeQueue, enabled: bool = True): ...

    def init_or_open(self) -> bool:
        """Detect existing repo; init if absent. Write .gitignore. Returns True if active."""

    def _write_gitignore(self):
        content = """# Akanga derived index — rebuilt by `akanga index`
.akanga.db
.akanga.db-wal
.akanga.db-shm

# Akanga internal state
.akanga/

# Python
.venv/
__pycache__/
*.pyc
.coverage

# Editor
.DS_Store
*.swp
*.tmp
"""

    def stage_and_commit(self, message: str | None = None) -> bool:
        """Squash queue → git add .md + akanga.yaml → commit. Non-fatal. Returns success."""

    def push(self, remote: str = "origin") -> bool:
        """Push to remote. Returns False and logs on failure. Never raises."""

    def status(self) -> dict:
        """{'is_repo': bool, 'clean': bool, 'modified': int, 'untracked': int, 'ahead': int}"""

    async def on_session_end(self):
        """Called on quit. Squash + commit if queue non-empty."""

    async def on_periodic_tick(self):
        """Called every N minutes. Squash + commit if queue non-empty."""
```

**`akanga.yaml` git config block:**

```yaml
git:
  enabled: true
  commit_on_session_end: true
  commit_interval: null      # minutes, null = disabled. e.g. 15
  auto_push: false           # explicit P keybinding only
  remote: origin
```

**TUI keybinding additions** (to Phase 5's keybinding table):

| Key | Action |
|---|---|
| `C` | Manual commit — opens overlay with squashed summary + editable message |
| `P` | Push to remote — explicit, with confirmation |

**`C` overlay in TUI:**

```
╭─ Commit ──────────────────────────────────────────────╮
│ Message: update: Fast Thinking is Unreliable          │
│                                                       │
│ 3 edits squashed → 1 commit                           │
│ Files: fast-thinking-is-unreliable.md                 │
│                                                       │
│  [Enter] commit    [e] edit message    [Esc] cancel   │
╰───────────────────────────────────────────────────────╯
```

**EventBus wiring in `app.py`:**

```python
eventbus.subscribe("node_created", lambda node_id, title, **_:
    queue.append(ChangeEntry(type="create", node_id=node_id, title=title, ...)))
eventbus.subscribe("node_updated", lambda node_id, title, **_:
    queue.append(ChangeEntry(type="edit",   node_id=node_id, title=title, ...)))
eventbus.subscribe("node_deleted", lambda node_id, title, **_:
    queue.append(ChangeEntry(type="delete", node_id=node_id, title=title, ...)))
```

---

## Common Pitfalls

**Not checking is_dirty before committing:** `repo.index.commit(message)` on a clean repo creates an empty commit. Always check `is_dirty()` first.

**Using os.path instead of GitPython:** `git.status()` via GitPython returns structured output; `os.system("git status")` returns a raw string that's harder to parse. Use the library.

**Forgetting git user config in CI:** Git commits fail without `user.email` and `user.name`. In tests, configure these explicitly with `repo.config_writer().set_value("user", "email", "test@test.com").release()`.

**Re-raising git exceptions:** Git is optional. A user without git should still be able to use Akanga. Wrap all GitPython calls in `try/except` and log errors rather than raising.

---

## Deliverable

```python
def test_git_init_creates_repo(tmp_path):
    gm = GitManager(tmp_path, ChangeQueue(tmp_path / ".akanga" / "queue.json"))
    gm.init_or_open()
    assert (tmp_path / ".git").exists()
    assert (tmp_path / ".gitignore").exists()

def test_db_not_committed(tmp_path):
    gm = GitManager(tmp_path, ChangeQueue(...))
    gm.init_or_open()
    (tmp_path / ".akanga.db").write_bytes(b"sqlite")
    (tmp_path / "note.md").write_text("# Note")
    gm.stage_and_commit("test")
    repo = Repo(tmp_path)
    assert ".akanga.db" not in repo.head.commit.stats.files

def test_queue_deduplicates_edits():
    q = ChangeQueue(Path("/tmp/queue.json"))
    for _ in range(5):
        q.append(ChangeEntry(type="edit", node_id="abc", title="Note A", timestamp="..."))
    summary = q.squash()
    assert summary.edited == ["Note A"]
    assert len(summary.edited) == 1

def test_queue_cancels_create_delete():
    q = ChangeQueue(Path("/tmp/queue.json"))
    q.append(ChangeEntry(type="create", node_id="abc", title="Temp Note", timestamp="..."))
    q.append(ChangeEntry(type="delete", node_id="abc", title="Temp Note", timestamp="..."))
    summary = q.squash()
    assert summary.is_empty   # created + deleted in same session → nothing

def test_queue_edit_then_delete():
    q = ChangeQueue(Path("/tmp/queue.json"))
    q.append(ChangeEntry(type="edit",   node_id="abc", title="Note A", timestamp="..."))
    q.append(ChangeEntry(type="delete", node_id="abc", title="Note A", timestamp="..."))
    summary = q.squash()
    assert summary.deleted == ["Note A"]
    assert summary.edited == []   # edited then deleted → just deleted

def test_queue_message_generation():
    q = ChangeQueue(Path("/tmp/queue.json"))
    q.append(ChangeEntry(type="create", node_id="a", title="BFS", timestamp="..."))
    q.append(ChangeEntry(type="edit",   node_id="b", title="Akanga", timestamp="..."))
    q.append(ChangeEntry(type="delete", node_id="c", title="Old Note", timestamp="..."))
    msg = q.generate_message(q.squash())
    assert "add: BFS" in msg
    assert "update: Akanga" in msg
    assert "delete: Old Note" in msg

def test_queue_persists_to_disk(tmp_path):
    persist_path = tmp_path / "queue.json"
    q = ChangeQueue(persist_path)
    q.append(ChangeEntry(type="edit", node_id="abc", title="Note A", timestamp="..."))
    assert persist_path.exists()
    # Reload
    q2 = ChangeQueue(persist_path)
    q2.load()
    assert len(q2._entries) == 1

def test_startup_commits_leftover_queue(tmp_path):
    # Simulate crash: queue has entries, no commit yet
    persist_path = tmp_path / ".akanga" / "queue.json"
    persist_path.parent.mkdir()
    q = ChangeQueue(persist_path)
    q.append(ChangeEntry(type="edit", node_id="abc", title="Note A", timestamp="..."))
    (tmp_path / "note-a.md").write_text("# Note A")
    gm = GitManager(tmp_path, q)
    gm.init_or_open()
    # On startup, load() detects non-empty queue and commits
    gm.commit_from_queue_if_needed()
    repo = Repo(tmp_path)
    assert len(list(repo.iter_commits())) >= 1

def test_git_failure_non_fatal(tmp_path):
    gm = GitManager(tmp_path, ChangeQueue(...))
    gm.init_or_open()
    import shutil
    shutil.rmtree(tmp_path / ".git" / "refs")
    # Must not raise:
    result = gm.stage_and_commit("test")
    assert result is False   # failed but did not crash

def test_push_non_fatal_without_remote(tmp_path):
    gm = GitManager(tmp_path, ChangeQueue(...))
    gm.init_or_open()
    (tmp_path / "note.md").write_text("# Note")
    gm.stage_and_commit("init")
    result = gm.push()
    assert result is False   # no remote → False, no exception
```

Plus 9 vault nodes with typed edges. The `test_queue_cancels_create_delete` and
`test_startup_commits_leftover_queue` tests are the most important — the first proves
the squash step eliminates noise correctly, the second proves work is never lost even
if the process dies between commits.

---

## Reflect

> **Solo:** The auto-commit debounce is 5 seconds. What are the tradeoffs between 1s, 5s, and 30s debounce windows for vault auto-commits?

> **Group:** Should git commit messages be generic ("vault update") or descriptive ("Add note: Cognitive Load")? What would you need to implement to generate descriptive messages?
