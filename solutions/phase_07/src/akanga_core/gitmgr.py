"""GitManager — optional git integration for vault version control (Phase 07).

Git is OPTIONAL and non-fatal: every method catches exceptions, logs
them, and returns a safe default (``None``, ``False``, ``""``) rather
than crashing. This is by design — a user without git installed, or
whose vault is not a repository, must still be able to use Akanga; they
just won't have version history. Vault usability must never depend on
git.

Keeping GitManager as a thin GitPython wrapper means the rest of Akanga
never imports ``git`` directly — easy to swap or stub in tests, and the
"open repo / not a repo" decision happens exactly once, in ``__init__``.

Usage::

    if GitManager.is_git_repo(vault):
        gm = GitManager(vault)
    else:
        gm = GitManager.init_repo(vault)
    gm.commit("auto: vault changed")   # no-op (None) when the tree is clean
    gm.push()                          # logged WARNING, never raises
"""
from __future__ import annotations

import logging
from pathlib import Path

from git import InvalidGitRepositoryError, NoSuchPathError, Repo

logger = logging.getLogger(__name__)


class GitManager:
    """Thin, non-fatal wrapper around a GitPython ``Repo`` for one vault."""

    def __init__(self, repo_path: str | Path) -> None:
        """Open an existing git repository at *repo_path*.

        When the directory is not a git repository (or does not exist),
        ``self.repo`` is set to ``None`` and a WARNING is logged — every
        method then degrades to its safe default instead of raising. The
        decision is made once here so callers never need a try/except.
        """
        self.repo_path = Path(repo_path)
        try:
            self.repo: Repo | None = Repo(str(repo_path))
        except (InvalidGitRepositoryError, NoSuchPathError):
            self.repo = None
            logger.warning("Not a git repo: %s", repo_path)

    def is_dirty(self) -> bool:
        """Return True when uncommitted changes (including untracked files) exist.

        Used by ``commit()`` to avoid creating empty commits, which
        clutter the log and waste space. ``untracked_files=True`` matters:
        a brand-new note is untracked, not modified, and must still count
        as "dirty" or auto-commit would silently skip every new file.
        """
        if self.repo is None:
            return False
        try:
            return self.repo.is_dirty(untracked_files=True)
        except Exception:  # noqa: BLE001 — git is optional, never fatal
            logger.exception("is_dirty failed for %s", self.repo_path)
            return False

    def active_branch(self) -> str:
        """Return the name of the currently checked-out branch.

        Shown in the git status API response so clients can display which
        branch the vault is on. Detached HEAD (no active branch) is one
        of the cases the broad except covers — it raises ``TypeError`` in
        GitPython, and an empty string is the honest answer.
        """
        if self.repo is None:
            return ""
        try:
            return str(self.repo.active_branch)
        except Exception:  # noqa: BLE001 — detached HEAD, fresh repo, etc.
            logger.exception("active_branch failed for %s", self.repo_path)
            return ""

    def status(self) -> str:
        """Return ``git status`` output as a human-readable string.

        Exposed via the API so users can inspect the vault's git state
        without running git themselves. Empty string when git is
        unavailable — callers treat "" as "nothing to show".
        """
        if self.repo is None:
            return ""
        try:
            return self.repo.git.status()
        except Exception:  # noqa: BLE001 — git is optional, never fatal
            logger.exception("status failed for %s", self.repo_path)
            return ""

    def commit(self, message: str) -> str | None:
        """Stage ALL changes and commit; return the commit SHA (or None).

        Idempotent on a clean tree: when there is nothing to commit the
        method returns ``None`` WITHOUT creating an empty commit — the
        auto-commit-on-change path can therefore call this freely.

        ``git add -A`` stages modifications, deletions, and new files in
        one pass; ``index.commit`` re-reads the on-disk index, so files
        staged externally (e.g. by the user running ``git add``) are
        committed too. Non-fatal: any failure is logged and ``None`` is
        returned — NEVER raised.
        """
        if self.repo is None:
            return None
        try:
            if not self.is_dirty():
                return None  # clean tree — nothing to commit, skip cleanly
            self.repo.git.add("-A")
            commit = self.repo.index.commit(message)
            logger.info("Committed %s: %s", commit.hexsha[:7], message)
            return str(commit.hexsha)
        except Exception:  # noqa: BLE001 — git is optional, never fatal
            logger.exception("commit failed for %s", self.repo_path)
            return None

    def push(self, remote_name: str = "origin") -> bool:
        """Push the current branch to *remote_name*; non-fatal by contract.

        Optional remote backup (private GitHub repo, self-hosted Gitea).
        A missing remote is the NORMAL case for a fresh vault — it is
        logged at WARNING level and ``False`` is returned; no exception
        ever escapes to the caller.
        """
        if self.repo is None:
            return False
        try:
            self.repo.remote(remote_name).push()
            return True
        except Exception:  # noqa: BLE001 — "no remote" is an expected condition
            logger.warning(
                "push to %r failed for %s (is the remote configured?)",
                remote_name,
                self.repo_path,
                exc_info=True,
            )
            return False

    @staticmethod
    def init_repo(path: str | Path) -> "GitManager":
        """Initialise a new git repository at *path* and return its manager.

        Called on first startup when ``--git-init`` is passed and no repo
        exists yet — creates the ``.git`` directory inside the vault.
        """
        Repo.init(str(path))
        logger.info("Initialized git repo at %s", path)
        return GitManager(path)

    @staticmethod
    def is_git_repo(path: str | Path) -> bool:
        """Return True when *path* contains a valid git repository.

        Used at startup to decide whether to open an existing repo or
        skip git integration entirely.
        """
        try:
            Repo(str(path))
        except (InvalidGitRepositoryError, NoSuchPathError):
            return False
        return True
