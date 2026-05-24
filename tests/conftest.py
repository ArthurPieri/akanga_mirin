"""Root test conftest — AKANGA_SRC resolver and shared fixtures."""
import os
import sys
from pathlib import Path
import pytest

MINIMAL_VAULT_CONFIG = {
    "owner": "Test User",
    "default_workspace": {"name": "Nhamandu", "id": "aaaaaaaa-0000-0000-0000-000000000001"},
    "workspaces": [{"name": "Nhamandu", "id": "aaaaaaaa-0000-0000-0000-000000000001"}],
    "relations": [],
}


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
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    return src
