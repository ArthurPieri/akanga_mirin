"""Phase 7 — Non-fatal GitPython wrapper pattern.

Run: python examples/phase_07_git_manager.py

Shows how to wrap GitPython so git errors never crash the application.
A user without git gets a warning, not an exception.
"""
import logging
import tempfile
import os
import shutil
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def safe_git_commit(repo_path: Path, message: str) -> str | None:
    try:
        from git import Repo, InvalidGitRepositoryError
        try:
            repo = Repo(str(repo_path))
        except InvalidGitRepositoryError:
            logger.warning("Not a git repo — skipping commit (git is optional)")
            return None
        if not repo.is_dirty(untracked_files=True):
            logger.info("Nothing to commit")
            return None
        repo.git.add("-A")
        commit = repo.index.commit(message)
        logger.info("Committed: %s — %s", commit.hexsha[:8], message)
        return commit.hexsha
    except Exception as e:
        logger.error("Git error (non-fatal): %s", e)
        return None


# Demo with a real temp repo
if not shutil.which("git"):
    print("git is not installed or not in PATH. Skipping git demo.")
    sys.exit(0)

with tempfile.TemporaryDirectory() as tmp:
    import subprocess
    subprocess.run(["git", "init"], cwd=tmp, capture_output=True)
    subprocess.run(["git", "config", "user.email", "demo@demo.com"], cwd=tmp)
    subprocess.run(["git", "config", "user.name", "Demo"], cwd=tmp)
    (Path(tmp) / "note.md").write_text("# Hello\nNew note.")
    sha = safe_git_commit(Path(tmp), "Add note: Hello")
    print(f"Commit SHA: {sha[:8] if sha else 'none'}")
    sha2 = safe_git_commit(Path(tmp), "Should be skipped — nothing changed")
    print(f"Second commit: {sha2!r} (None = nothing to commit)")
