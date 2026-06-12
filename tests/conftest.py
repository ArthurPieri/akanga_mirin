"""Root test conftest — AKANGA_SRC resolver and shared fixtures."""
import os
import re
import sys
from pathlib import Path
import pytest

MINIMAL_VAULT_CONFIG = {
    "owner": "Test User",
    "default_workspace": {"name": "Nhamandu", "id": "aaaaaaaa-0000-0000-0000-000000000001"},
    "workspaces": [{"name": "Nhamandu", "id": "aaaaaaaa-0000-0000-0000-000000000001"}],
    "relations": [],
}


def pytest_configure(config):
    """Insert AKANGA_SRC into sys.path before collection begins."""
    src = os.environ.get("AKANGA_SRC")
    if src:
        resolved = str(Path(src).resolve())
        if resolved in sys.path:
            sys.path.remove(resolved)
        sys.path.insert(0, resolved)


def _resolve_akanga_src(phase: int) -> Path:
    env_src = os.environ.get("AKANGA_SRC")
    if not env_src:
        pytest.fail(
            f"\n\nAKANGA_SRC is not set!\n"
            f"Run: AKANGA_SRC=./src make test PHASE={phase}\n"
            f"Or:  AKANGA_SRC=/path/to/your/src pytest tests/phase_{phase:02d}/\n"
        )
    src = Path(env_src).resolve()
    if not src.exists():
        pytest.fail(f"AKANGA_SRC={env_src!r} does not exist. Create your src/ directory first.")
    # Invalidate any previously-imported akanga modules so learner code takes precedence
    for key in list(sys.modules.keys()):
        if "akanga" in key:
            del sys.modules[key]
    if str(src) in sys.path:
        sys.path.remove(str(src))
    sys.path.insert(0, str(src))
    return src


@pytest.fixture(scope="session", autouse=True)
def _akanga_src_guard(request) -> Path | None:
    """Fail fast with guidance when AKANGA_SRC is unset or missing, and purge
    previously-imported akanga modules so learner code takes precedence.

    NOTE this fixture does NOT make sys.path safe for import-time work: pytest
    imports test modules during COLLECTION, before any fixture runs. The
    sys.path insertion that collection relies on happens in pytest_configure
    above. Loader calls (`_load_db()` etc.) must therefore live inside
    fixtures or tests, never at module top level — at top level an import
    failure surfaces as a raw collection error (exit code 2) and skips this
    guard's diagnostics entirely (adversarial-analysis-v5 #2).

    The phase number in the error message is derived from the first collected
    test's path; in multi-phase sessions (`make test-mine`) it names the first
    suite, which is hint enough. Sessions containing no phase tests at all
    (e.g. tests/test_scripts_markers.py, which imports no learner code) skip
    the guard entirely — they have no use for AKANGA_SRC.
    """
    for item in request.session.items:
        m = re.search(r"phase_(\d+)", str(getattr(item, "nodeid", "")))
        if m:
            return _resolve_akanga_src(int(m.group(1)))
    return None
