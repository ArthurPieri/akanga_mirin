"""Phase 07 test suite — Version Control (GitPython).

Tests for gitmgr.py. Learner code must export a GitManager class with:

    GitManager(repo_path: str | Path)
    GitManager.status() -> str
    GitManager.is_dirty() -> bool
    GitManager.active_branch() -> str
    GitManager.commit(message: str) -> str | None   # returns SHA or None
    GitManager.push(remote_name: str = "origin") -> None
    GitManager.init_repo(path: str | Path) -> GitManager  (staticmethod)
    GitManager.is_git_repo(path: str | Path) -> bool      (staticmethod)

All git operations must be non-fatal — errors are logged but never re-raised.

All imports happen inside test functions or fixtures so that the AKANGA_SRC
sys.path insertion from conftest runs before any learner module is loaded.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from tests._helpers import load_attr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_git_manager():
    """Import GitManager, trying flat layout then package layout."""
    return load_attr(
        ("gitmgr", "GitManager"),
        ("akanga_core.gitmgr", "GitManager"),
        hint="GitManager (gitmgr.py or akanga_core/gitmgr.py)",
    )


def _make_initial_commit(repo_path: Path) -> None:
    """Write a file and create an initial commit so the repo has a HEAD."""
    readme = repo_path / "README.md"
    readme.write_text("# Test Vault\n", encoding="utf-8")
    subprocess.run(["git", "add", "README.md"], cwd=str(repo_path), check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "init"],
        cwd=str(repo_path), check=True, capture_output=True,
    )


# ---------------------------------------------------------------------------
# Static-method tests (no GitManager instance needed)
# ---------------------------------------------------------------------------

class TestIsGitRepo:
    def test_is_git_repo_true(self, tmp_git_repo: Path) -> None:
        """A freshly initialized git repo must be recognised as a git repo."""
        GitManager = _load_git_manager()
        assert GitManager.is_git_repo(str(tmp_git_repo)) is True, (
            "is_git_repo must return True for a directory with a .git folder."
        )

    def test_is_git_repo_false(self, tmp_path: Path) -> None:
        """A plain directory without .git must NOT be recognised as a git repo."""
        plain_dir = tmp_path / "no_git"
        plain_dir.mkdir()
        GitManager = _load_git_manager()
        assert GitManager.is_git_repo(str(plain_dir)) is False, (
            "is_git_repo must return False for a directory without .git."
        )


class TestInitRepo:
    def test_init_repo_creates_git_dir(self, tmp_path: Path) -> None:
        """init_repo(path) must create a .git directory at the given path."""
        GitManager = _load_git_manager()
        target = tmp_path / "new_vault"
        target.mkdir()
        GitManager.init_repo(str(target))
        assert (target / ".git").is_dir(), (
            "init_repo must create a .git directory inside the target path."
        )

    def test_init_repo_returns_git_manager(self, tmp_path: Path) -> None:
        """init_repo must return a GitManager instance."""
        GitManager = _load_git_manager()
        target = tmp_path / "new_vault2"
        target.mkdir()
        result = GitManager.init_repo(str(target))
        assert isinstance(result, GitManager), (
            "init_repo must return a GitManager instance, "
            f"got {type(result).__name__!r}."
        )


# ---------------------------------------------------------------------------
# Instance-method tests
# ---------------------------------------------------------------------------

class TestActiveBranch:
    def test_active_branch_returns_string(self, tmp_git_repo: Path) -> None:
        """active_branch() must return a non-empty string (usually 'main' or 'master')."""
        GitManager = _load_git_manager()
        # Need at least one commit for git to know the branch name
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))
        branch = gm.active_branch()
        assert isinstance(branch, str) and branch, (
            f"active_branch() must return a non-empty string, got {branch!r}."
        )


class TestIsDirty:
    def test_is_dirty_false_on_clean_repo(self, tmp_git_repo: Path) -> None:
        """Repo with an initial commit and no pending changes must be clean."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))
        assert gm.is_dirty() is False, (
            "is_dirty() must return False immediately after a clean commit."
        )

    def test_is_dirty_true_with_staged_file(self, tmp_git_repo: Path) -> None:
        """Staging a new file must make is_dirty() return True."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))

        new_file = tmp_git_repo / "new-note.md"
        new_file.write_text("---\ntitle: New Note\ntype: note\n---\n\nBody.\n",
                             encoding="utf-8")
        subprocess.run(["git", "add", "new-note.md"], cwd=str(tmp_git_repo),
                       check=True, capture_output=True)

        assert gm.is_dirty() is True, (
            "is_dirty() must return True after staging a new file."
        )


class TestCommit:
    def test_commit_creates_commit(self, tmp_git_repo: Path) -> None:
        """commit() after staging a file must produce a commit in git log."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))

        note = tmp_git_repo / "note.md"
        note.write_text("---\ntitle: Note\ntype: note\n---\n\nContent.\n",
                         encoding="utf-8")
        subprocess.run(["git", "add", "note.md"], cwd=str(tmp_git_repo),
                       check=True, capture_output=True)

        gm.commit("test commit")

        # commit() may return a SHA string or None — both are acceptable per spec.
        # What matters is that a new commit exists in the log.
        log = subprocess.run(
            ["git", "log", "--oneline"],
            cwd=str(tmp_git_repo), capture_output=True, text=True,
        )
        assert "test commit" in log.stdout, (
            "After commit('test commit'), the message must appear in git log."
        )

    def test_commit_returns_sha_or_none(self, tmp_git_repo: Path) -> None:
        """commit() must return either a commit SHA string or None (not crash)."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))

        note = tmp_git_repo / "sha-test.md"
        note.write_text("---\ntitle: SHA Test\ntype: note\n---\n\nBody.\n",
                         encoding="utf-8")
        subprocess.run(["git", "add", "sha-test.md"], cwd=str(tmp_git_repo),
                       check=True, capture_output=True)

        result = gm.commit("sha test")
        if result is not None:
            assert isinstance(result, str) and len(result) >= 7, (
                f"If commit() returns a value, it must be a SHA string (>= 7 chars), "
                f"got {result!r}."
            )

    def test_commit_message_stored(self, tmp_git_repo: Path) -> None:
        """The exact commit message passed to commit() must appear in git log."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))

        note = tmp_git_repo / "msg-test.md"
        note.write_text("---\ntitle: Msg Test\ntype: note\n---\n\nBody.\n",
                         encoding="utf-8")
        subprocess.run(["git", "add", "msg-test.md"], cwd=str(tmp_git_repo),
                       check=True, capture_output=True)

        gm.commit("my unique message")

        log = subprocess.run(
            ["git", "log", "--pretty=%s"],
            cwd=str(tmp_git_repo), capture_output=True, text=True,
        )
        assert "my unique message" in log.stdout, (
            "The commit message 'my unique message' must appear in git log."
        )


class TestStatus:
    def test_status_returns_string(self, tmp_git_repo: Path) -> None:
        """status() must return a non-empty string without crashing."""
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))
        result = gm.status()
        assert isinstance(result, str), (
            f"status() must return a string, got {type(result).__name__!r}."
        )
        # status() output for a clean repo still contains useful text
        assert len(result) > 0, "status() must return a non-empty string."


# ---------------------------------------------------------------------------
# Error-path tests (required per CCR-9)
# ---------------------------------------------------------------------------

class TestErrorPaths:
    def test_git_errors_are_nonfatal(self, tmp_path: Path) -> None:
        """GitManager pointing at a non-repo directory must not crash on method calls.

        Per spec: git is optional and all errors are logged but never re-raised.
        Implementations may raise on __init__ or return None/False from methods.
        Either approach is acceptable as long as the test can be invoked without
        an unhandled exception escaping to the caller.
        """
        GitManager = _load_git_manager()
        non_repo = tmp_path / "not_a_git_repo"
        non_repo.mkdir()

        # Construction may raise — that's also acceptable. We only require that
        # if a GitManager is obtained, its methods don't raise unhandled errors.
        try:
            gm = GitManager(str(non_repo))
        except Exception:
            # Construction raising is acceptable — the class detected a bad path.
            return

        # If construction succeeded, method calls must not raise.
        try:
            result = gm.status()
            assert result is None or isinstance(result, str), (
                f"status() on non-repo must return None or str, got {result!r}."
            )
        except Exception:
            pytest.fail(
                "status() on a non-git-repo directory must not raise an unhandled "
                "exception. Catch GitCommandError and log it instead."
            )

        try:
            gm.is_dirty()
        except Exception:
            pytest.fail(
                "is_dirty() on a non-git-repo directory must not raise an unhandled "
                "exception. Catch GitCommandError and log it instead."
            )

    def test_push_without_remote_is_nonfatal(self, tmp_git_repo: Path) -> None:
        """push() when no remote is configured must not raise.

        Per spec: git errors (including 'no remote configured') are logged at
        WARNING level but never re-raised.  push() should return None or False.
        """
        GitManager = _load_git_manager()
        _make_initial_commit(tmp_git_repo)
        gm = GitManager(str(tmp_git_repo))

        try:
            gm.push()   # no "origin" remote configured
        except Exception as exc:
            pytest.fail(
                f"push() without a configured remote must not raise, "
                f"but got {type(exc).__name__}: {exc}"
            )
