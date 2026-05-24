# Phase 7 — Version Control as a Feature

**Core concept:** The vault is a directory of Markdown files that change over time.
That is exactly what git was built for. The insight is treating git not as optional
developer infrastructure but as a first-class user feature: every node you write,
edit, or delete is tracked automatically. Your knowledge graph has a complete,
navigable history from day one — without you thinking about it.

**What makes this non-obvious:** The hard part is not the git operations themselves
(those are one-liners with GitPython). The hard part is making git truly optional —
a user without git installed, or with a broken repo, must still be able to use the
tool. Every git operation must be wrapped so it never raises, never blocks, and never
takes down the application when it fails.

---

## Learning Objectives

By the end of this phase, you will be able to:
- Implement a GitPython wrapper with non-fatal error handling
- Understand why git errors must be swallowed (git is optional, not required)
- Write non-fatal wrapper methods that catch all git exceptions, log them, and return safe defaults so vault use is never interrupted by git failures
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

Key classes and operations:
- `Repo(path)` opens an existing repo; raises `InvalidGitRepositoryError` if path is not a repo
- `Repo.init(path)` creates a new repo
- `repo.is_dirty(untracked_files=True)` checks whether there are uncommitted changes
- `str(repo.active_branch)` returns the current branch name
- `repo.git.status()` returns the status output as a string
- `repo.index.commit(message)` stages all tracked changes and creates a commit
- `repo.remote(name).push()` pushes to the named remote

Install: `pip install gitpython` / `uv add gitpython`.

> Akanga node: `GitPython`

→ Foundation doc: `docs/foundations/git-basics.md`

### Git Commit Model

Every change in the vault — creating a node, editing one, deleting one — is tracked
as a git commit: what changed, when, why. Git provides the version history that makes
the knowledge graph auditable and recoverable. You can `git log` to see editing
sessions, `git diff` a specific note to see how your understanding of a topic evolved,
or `git restore` a node you deleted by accident.

This is why Akanga treats git as a user feature rather than developer infrastructure:
the vault's git history is the undo system, the audit trail, and the backup — all
without the user ever running a git command.

> Akanga node: `Git Commit Model`

### Non-Fatal Git Integration

Git is optional in Akanga. A user without git installed, or with a broken repo,
should still be able to use the tool. All git operations wrap their bodies in
`try/except Exception` and log failures rather than raising. This is the "non-fatal"
contract.

Git can fail for many reasons: no remote configured, network timeout, no commits yet
(empty repo cannot push), detached HEAD, filesystem permission issues. None of these
should crash or degrade Akanga's core functionality. Failures are logged at WARNING
level. The EventBus never receives a git error.

> Akanga node: `Non-Fatal Git Errors`

### Idempotent Commit

Committing when nothing has changed creates an empty commit that clutters the git log
and confuses reviewers. `is_dirty(untracked_files=True)` guards the commit operation:
if the working tree is clean, skip. This makes `commit()` safe to call repeatedly —
it is a no-op (returning `None`) when there is nothing to record.

The `untracked_files=True` argument is required. Without it, `repo.is_dirty()` returns
`False` for newly created files (which are untracked), so a first commit after adding
nodes to a fresh vault would be silently skipped.

> Akanga node: `Idempotent Commit`

### .gitignore as Contract

The `.gitignore` written on `--git-init` is a declaration of Akanga's architecture:
what is vault (tracked) vs what is derived/internal (untracked). Tracked: all `.md`
files, `akanga.yaml`. Untracked: `.akanga.db` (derived index — expendable), `.akanga.db-wal`,
`.venv/`, `__pycache__/`. The file documents the source-of-truth boundary as clearly
as any README.

> Akanga node: `.gitignore as Contract`

---

## Vault Nodes to Create

| Node | Type | Key Edges |
|---|---|---|
| `Git Commit Model` | note | `enables` → `Version History`; `is_applied_in` → `Akanga Vault` |
| `GitPython` | reference | `implements` → `Git Integration`; `is_applied_in` → `Akanga GitManager` |
| `Non-Fatal Error Handling` | note | `is_applied_in` → `Akanga GitManager`; `contrasts_with` → `Fail-Fast Pattern` |
| `Idempotent Commit` | note | `prevents` → `Empty Commit`; `uses` → `is_dirty Check` |
| `.gitignore as Contract` | note | `excludes` → `*.db`; `excludes` → `*.db-wal`; `enables` → `Clean Vault History` |

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

**Omitting `untracked_files=True` in `is_dirty()`:** `repo.is_dirty()` alone returns `False` for newly created files (untracked). The skeleton explicitly requires `is_dirty(untracked_files=True)` to catch nodes added to the vault before the first commit. Omitting the flag means a fresh vault with new nodes will appear clean and silently skip the commit.

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

Plus 5 vault nodes with typed edges.

---

## Reflect

> **Solo:** Your `commit()` method catches all exceptions and returns `None` on failure. What information is silently lost when an exception is swallowed? Where would you look to find out whether a failure occurred?

> **Group:** The `GitManager` wraps `git add -A` before every commit — it stages ALL changes. Is that the right behavior for a personal knowledge graph vault? What changes would you never want staged, and how would `.gitignore` help? Walk through two edge cases together.
