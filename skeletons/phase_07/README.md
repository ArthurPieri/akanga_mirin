# Phase 7 — Version Control (GitManager)

Add optional, non-fatal git integration so the vault keeps a version history
of every change automatically.

`gitmgr.py` is the only skeleton file — all prior-phase modules must be
copied from your Phase 06 solution.

## What you will build

| Method | Behaviour |
|---|---|
| `__init__(repo_path)` | Open existing repo; `self.repo = None` if not a repo |
| `is_dirty()` | True if uncommitted / untracked changes exist |
| `active_branch()` | Name of checked-out branch |
| `status()` | `git status` output as string |
| `commit(message)` | Stage all + commit; return SHA or `""` |
| `push(remote_name)` | Push to remote; non-fatal |
| `init_repo(path)` _(static)_ | `git init` then return GitManager |
| `is_git_repo(path)` _(static)_ | True if `.git` present |

## The non-fatal contract

Every method **catches all exceptions** and returns a safe default
(`False`, `""`, `None`). A user without `git` installed — or whose vault
is not a repo — must still be able to run Akanga normally. Never let a
git error propagate to the caller.

```python
try:
    return self.repo.git.status()
except Exception as e:
    logger.exception("status failed: %s", e)
    return ""
```

## Integration with AkangaApp

In Phase 07 you will also wire GitManager into `app.py`:

```python
# In AkangaApp.start_all():
if self.git_sync:
    if GitManager.is_git_repo(self.vault):
        self._git = GitManager(self.vault)
    else:
        self._git = GitManager.init_repo(self.vault)

# Subscribe to node_updated events:
self.eventbus.subscribe("node_updated", self._on_node_updated)

async def _on_node_updated(self, topic, payload):
    if self._git:
        self._git.commit(f"auto: {payload.get('path', 'unknown')}")
```

## Running the tests

```bash
# From this directory
PYTHONPATH=src pytest -v
# Or via the repo Makefile
make test PHASE=7
```
