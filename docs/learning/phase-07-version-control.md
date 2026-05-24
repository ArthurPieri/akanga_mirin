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
- [ ] I've completed Phases 0, 1A, 1B, 2, 3, 4, 5, and 6

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

**`gitmgr.py`** — `GitManager`:

```python
class GitManager:
    def __init__(self, repo_path: str | Path) -> None:
        """Open an existing git repository at repo_path.
        Sets self.repo = None (with a warning log) if path is not a git repo."""

    def is_dirty(self) -> bool:
        """Return True if there are any uncommitted changes (including untracked files).
        Returns False if self.repo is None or on any exception."""

    def active_branch(self) -> str:
        """Return the name of the currently checked-out branch.
        Returns empty string if self.repo is None or on any exception."""

    def status(self) -> str:
        """Return git status output as a human-readable string.
        Returns empty string if self.repo is None or on any exception."""

    def commit(self, message: str) -> str | None:
        """Stage all changes (git add -A) and create a commit.
        Returns the commit SHA string, or None on failure or when nothing to commit.
        Non-fatal — never raises."""

    def push(self, remote_name: str = "origin") -> None:
        """Push the current branch to the named remote.
        Non-fatal — logs and returns on failure, never raises."""

    @staticmethod
    def init_repo(path: str | Path) -> "GitManager":
        """Initialize a new git repository at path and return a GitManager for it."""

    @staticmethod
    def is_git_repo(path: str | Path) -> bool:
        """Return True if path contains a valid git repository."""
```

All git operations are non-fatal by design: every method wraps its GitPython calls in
`try/except` and logs failures at WARNING level rather than re-raising. A user without
git installed (or whose repo is in a broken state) must still be able to use Akanga.

---

## Common Pitfalls

**Not checking is_dirty before committing:** `repo.index.commit(message)` on a clean repo creates an empty commit. Always check `is_dirty()` first.

**Using os.path instead of GitPython:** `git.status()` via GitPython returns structured output; `os.system("git status")` returns a raw string that's harder to parse. Use the library.

**Forgetting git user config in CI:** Git commits fail without `user.email` and `user.name`. In tests, configure these explicitly with `repo.config_writer().set_value("user", "email", "test@test.com").release()`.

**Re-raising git exceptions:** Git is optional. A user without git should still be able to use Akanga. Wrap all GitPython calls in `try/except` and log errors rather than raising.

---

## Deliverable

The complete test suite is in `tests/phase_07/test_git.py`. It covers:
`is_git_repo`, `init_repo`, `active_branch`, `is_dirty`, `commit`, `status`, and `push`.

Key behaviors the tests verify:

- `is_git_repo` returns `True` for a `.git`-containing directory and `False` otherwise
- `init_repo` creates a `.git` directory and returns a `GitManager` instance
- `active_branch` returns a non-empty string (typically `"main"` or `"master"`)
- `is_dirty` returns `False` on a clean repo and `True` after staging changes
- `commit` records the given message in `git log` and returns a SHA string or `None`
- `status` returns a non-empty string without crashing
- All methods are non-fatal on a broken or non-git directory — errors are caught and logged

Plus 9 vault nodes with typed edges.

---

## Reflect

> **Solo:** The auto-commit debounce is 5 seconds. What are the tradeoffs between 1s, 5s, and 30s debounce windows for vault auto-commits?

> **Group:** Should git commit messages be generic ("vault update") or descriptive ("Add note: Cognitive Load")? What would you need to implement to generate descriptive messages?
