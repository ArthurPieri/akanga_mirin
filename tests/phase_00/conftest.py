"""Phase 00 conftest — resolves AKANGA_SRC and provides shared fixtures."""
from pathlib import Path
from textwrap import dedent

import pytest
import yaml

from tests.conftest import MINIMAL_VAULT_CONFIG, _resolve_akanga_src


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(0)


@pytest.fixture()
def tmp_vault(tmp_path: Path) -> Path:
    """A temporary vault directory with a minimal akanga.yaml config file."""
    config_path = tmp_path / "akanga.yaml"
    config_path.write_text(yaml.dump(MINIMAL_VAULT_CONFIG), encoding="utf-8")
    return tmp_path


@pytest.fixture()
def sample_md_file(tmp_path: Path) -> Path:
    """A well-formed .md file with valid frontmatter for use in parse tests."""
    content = dedent("""\
        ---
        id: a3f7c2be-1234-5678-abcd-ef0123456789
        title: Test Node
        type: note
        tags:
          - test
          - example
        ---

        Body content here.
        """)
    node_file = tmp_path / "test-node.md"
    node_file.write_text(content, encoding="utf-8")
    return node_file
