"""Phase 07 conftest — resolves AKANGA_SRC and provides git fixtures."""
import subprocess
from pathlib import Path

import pytest

from tests._helpers import load_attr



@pytest.fixture()
def tmp_git_repo(tmp_path: Path) -> Path:
    """A temporary directory with a git repository initialized in it.

    Also configures git user.email and user.name so commits work in CI
    environments where the global git config may be absent.
    """
    # Initialize the repo via subprocess so no akanga import is needed
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True,
                   capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(tmp_path), check=True, capture_output=True,
    )
    return tmp_path


def _load_git_manager():
    """Import GitManager, trying flat layout then package layout."""
    return load_attr(
        ("gitmgr", "GitManager"),
        ("akanga_core.gitmgr", "GitManager"),
        hint="GitManager (gitmgr.py or akanga_core/gitmgr.py)",
    )


@pytest.fixture()
def git_manager(tmp_git_repo: Path):
    """A GitManager instance pointing at a freshly initialized git repo.

    Loaded inside the fixture so the AKANGA_SRC sys.path insertion runs
    first (guaranteed by the session-scoped _akanga_src_guard fixture in the
    root conftest).
    """
    return _load_git_manager()(str(tmp_git_repo))
