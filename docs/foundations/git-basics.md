# Git Basics

A practical reference for understanding git internals and how they map to
GitPython — the library akanga uses in `gitmgr.py`.

---

## The three zones

Every git repository has three distinct zones where your work can live.

**Working tree** — the files you actually see on disk. When you edit `parser.py`,
the change lives here first. Git knows about it but hasn't recorded anything yet.

**Staging area (index)** — a snapshot of what the *next* commit will contain.
`git add` copies the current state of a file from the working tree into the index.
You can stage some files and leave others unstaged.

**History (object store)** — the permanent, append-only log of commits. Once a
commit is created, git doesn't change it. Every commit references a snapshot of
the entire project tree at that moment.

```
working tree  →  git add  →  staging area  →  git commit  →  history
```

---

## Core commands

### git init

Creates a new repository. Adds a `.git/` directory containing the object store,
config, and refs. You almost never need to call this manually — `gitmgr.py` does
it when `git_sync=True` and no repo already exists.

```bash
git init my-vault
```

### git status

Shows which files are modified, staged, or untracked. The most useful command
when something is wrong.

```bash
git status
# On branch master
# Changes not staged for commit:
#   modified: nodes/my-note.md
# Untracked files:
#   nodes/new-node.md
```

### git add

Moves changes from the working tree into the staging area.

```bash
git add nodes/my-note.md       # stage one file
git add nodes/                  # stage everything in a directory
git add -A                      # stage all tracked + untracked changes
```

### git commit

Records whatever is in the staging area as a permanent snapshot.

```bash
git commit -m "add my-note: document the indexer design"
```

Every commit gets a **SHA** — a 40-character hex digest like
`839f26b3a1c2d4e5...`. Git derives the SHA by hashing the commit's contents
(tree snapshot, author, timestamp, parent SHA). This means two identical commits
always produce the same SHA, and any change produces a different one. You
typically refer to commits by their first 7 characters.

### git log

Shows the commit history, newest first.

```bash
git log --oneline
# 839f26b chore: add SQLite WAL/SHM and .coverage to gitignore
# 6532d84 feat: add akanga.nvim plugin; fix graph view and Ctrl+S in TUI
# 4cfb9dd feat(tui): add keyboard shortcut cheatsheet (? key)
```

### git diff

Shows what changed. Without arguments, diffs the working tree against the
staging area. With `--staged`, diffs the staging area against the last commit.

```bash
git diff                  # unstaged changes
git diff --staged         # staged but not yet committed
git diff HEAD             # all uncommitted changes vs last commit
git diff 839f26b 6532d84  # diff between two commits
```

---

## HEAD

`HEAD` is a pointer to the current position in history. Usually it points to
a branch (e.g., `refs/heads/master`), and the branch points to a commit.

```
HEAD -> master -> 839f26b (latest commit)
```

When you commit, git advances `master` to the new commit. `HEAD` moves with it
because it's pointing at `master`, not directly at a commit.

**Detached HEAD** — when `HEAD` points directly at a commit SHA instead of a
branch. This happens after `git checkout <sha>`. You can look around freely, but
any commits you make won't belong to a branch and will be "lost" when you
checkout something else. Akanga treats this as non-fatal: `gitmgr.py` catches the
`InvalidGitRepositoryError` / detached state and logs a warning rather than
crashing the whole app. Git errors should never take down a running knowledge
graph server.

---

## GitPython: git concepts as Python objects

GitPython wraps the git object model in a Python API. The key objects:

| Git concept | GitPython object |
|---|---|
| Repository | `git.Repo` |
| Commit | `repo.head.commit` |
| Index (staging area) | `repo.index` |
| Remote | `repo.remote('origin')` |
| Working tree path | `repo.working_tree_dir` |

### Opening or creating a repo

```python
import git

# Open an existing repo (raises InvalidGitRepositoryError if not a repo)
repo = git.Repo("/path/to/vault")

# Create a new repo
repo = git.Repo.init("/path/to/vault")
```

### Checking status

```python
# True when there are uncommitted changes (staged or unstaged)
repo.is_dirty(untracked_files=True)

# List of changed files (diff against HEAD)
diff = repo.index.diff(None)           # unstaged vs index
staged = repo.index.diff("HEAD")       # staged vs HEAD
untracked = repo.untracked_files       # new files git doesn't track yet
```

### Staging and committing

```python
# Stage specific files
repo.index.add(["nodes/my-note.md", "nodes/other.md"])

# Stage everything (like git add -A)
repo.git.add(A=True)

# Commit
repo.index.commit("auto: sync vault changes")
```

---

## The auto-commit pattern in akanga

`gitmgr.py` implements a **debounced auto-commit**: when files change in the
vault, the watcher fires events, but instead of committing immediately on every
save, it waits 5 seconds and then commits everything that changed in that window.
This avoids creating one commit per keystroke while still capturing all changes.

The core GitPython snippet from Phase 7:

```python
import git
from pathlib import Path

class GitManager:
    def __init__(self, vault_path: str, git_sync: bool = False):
        self.vault_path = vault_path
        self.repo = None
        self._setup(git_sync)

    def _setup(self, git_sync: bool):
        try:
            self.repo = git.Repo(self.vault_path, search_parent_directories=True)
        except git.InvalidGitRepositoryError:
            if git_sync:
                self.repo = git.Repo.init(self.vault_path)
            # else: no repo, git features disabled — non-fatal

    def commit_changes(self, message: str = "auto: vault sync") -> bool:
        if self.repo is None:
            return False
        try:
            if not self.repo.is_dirty(untracked_files=True):
                return False   # nothing to commit
            self.repo.git.add(A=True)
            self.repo.index.commit(message)
            return True
        except Exception as exc:
            # Git errors are never fatal
            logger.warning("git commit failed: %s", exc)
            return False
```

Key design decisions visible here:
- `search_parent_directories=True` — the vault may be a subdirectory inside a
  larger repo.
- Every git call is wrapped in `try/except`. A broken git repo must not crash the
  server.
- `is_dirty(untracked_files=True)` — we want to capture new files, not just
  edits.

---

## In this codebase

- `src/akanga_core/gitmgr.py` — the GitPython wrapper described above.
- **Phase 7** of the learning path teaches git internals by reading and extending
  `gitmgr.py`. You'll add a `push` method, inspect commit history via the API,
  and wire debounce timing to a config value.
- The `POST /api/v1/git/push` endpoint in `server.py` calls `gitmgr.push()`.
- Git is entirely optional: passing `--git-init` to the CLI enables it; omitting
  it means `self.repo` stays `None` and all git methods return early.
