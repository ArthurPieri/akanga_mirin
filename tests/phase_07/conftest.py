"""Phase 07 conftest — resolves AKANGA_SRC and provides git fixtures."""
import subprocess
from pathlib import Path

import pytest

from tests.conftest import _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(7)


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


@pytest.fixture()
def git_manager(tmp_git_repo: Path):
    """A GitManager instance pointing at a freshly initialized git repo.

    Imported inside the fixture so the AKANGA_SRC sys.path insertion runs
    first (guaranteed by the session-scoped _setup_akanga_src fixture).
    """
    try:
        from gitmgr import GitManager
    except ImportError:
        from akanga_core.gitmgr import GitManager

    return GitManager(str(tmp_git_repo))
