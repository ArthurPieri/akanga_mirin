"""Phase 08 conftest — resolves AKANGA_SRC and provides RAG / MCP fixtures."""
import uuid
from pathlib import Path
from textwrap import dedent

import pytest

from tests.conftest import _resolve_akanga_src


# ---------------------------------------------------------------------------
# Dual-try import helper
# ---------------------------------------------------------------------------

def _load_db():
    """Import GraphDatabase from 'db' or 'akanga_core.db'."""
    try:
        from db import GraphDatabase  # noqa: PLC0415
        return GraphDatabase
    except ModuleNotFoundError:
        try:
            from akanga_core.db import GraphDatabase  # noqa: PLC0415
            return GraphDatabase
        except ModuleNotFoundError:
            pytest.fail("Cannot import GraphDatabase from 'db' or 'akanga_core.db'")


# Stable UUIDs used across all phase-08 fixtures
_ID_COGNITION = str(uuid.UUID("aaaaaaaa-0800-0000-0000-000000000001"))
_ID_ATTENTION = str(uuid.UUID("bbbbbbbb-0800-0000-0000-000000000002"))
_ID_MEMORY    = str(uuid.UUID("cccccccc-0800-0000-0000-000000000003"))
_ID_LEARNING  = str(uuid.UUID("dddddddd-0800-0000-0000-000000000004"))
_ID_ISOLATED  = str(uuid.UUID("eeeeeeee-0800-0000-0000-000000000005"))


@pytest.fixture(scope="session", autouse=True)
def _setup_akanga_src() -> Path:
    """Insert AKANGA_SRC into sys.path before any test module is imported."""
    return _resolve_akanga_src(8)


@pytest.fixture()
def tmp_vault_with_nodes(tmp_path: Path):
    """A temporary vault + GraphDatabase pre-loaded with 5 nodes and 3 edges.

    Nodes:
        Cognition  (id: _ID_COGNITION) — root node for RAG tests
        Attention  (id: _ID_ATTENTION)
        Memory     (id: _ID_MEMORY)
        Learning   (id: _ID_LEARNING)
        Isolated   (id: _ID_ISOLATED) — no edges, for isolation test

    Edges:
        Cognition  -supports->       Attention
        Cognition  -is_related_to->  Memory
        Cognition  -enables->        Learning
        Attention  -enables->        Learning

    Each node has a real .md file on disk so body-from-disk tests work.
    Returns a namespace object with attributes:
        .vault    — Path to the vault directory
        .db       — GraphDatabase instance
        .id_*     — node UUIDs as strings
    """
    GraphDatabase = _load_db()

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "test.db"
    db = GraphDatabase(str(db_path))

    # Write node files and upsert them into the DB
    nodes = [
        (
            _ID_COGNITION,
            "Cognition",
            "note",
            "cognition.md",
            dedent("""\
                ---
                id: {id}
                title: Cognition
                type: note
                tags: [cognition, mind]
                ---

                Cognition is the mental process of acquiring knowledge and understanding
                through thought, experience, and the senses. It encompasses attention,
                memory, judgment, evaluation, reasoning, and language.
                """).format(id=_ID_COGNITION),
        ),
        (
            _ID_ATTENTION,
            "Attention",
            "note",
            "attention.md",
            dedent("""\
                ---
                id: {id}
                title: Attention
                type: note
                tags: [attention, focus]
                ---

                Attention is the behavioural and cognitive process of selectively
                concentrating on a discrete aspect of information while ignoring other
                perceivable information.
                """).format(id=_ID_ATTENTION),
        ),
        (
            _ID_MEMORY,
            "Memory",
            "note",
            "memory.md",
            dedent("""\
                ---
                id: {id}
                title: Memory
                type: note
                tags: [memory, recall]
                ---

                Memory is the faculty of the mind by which information is encoded,
                stored, and retrieved. Memory is vital to experiences and relates to
                limbic systems.
                """).format(id=_ID_MEMORY),
        ),
        (
            _ID_LEARNING,
            "Learning",
            "note",
            "learning.md",
            dedent("""\
                ---
                id: {id}
                title: Learning
                type: note
                tags: [learning, education]
                ---

                Learning is the process of acquiring new understanding, knowledge,
                behaviors, skills, values, attitudes, and preferences.
                """).format(id=_ID_LEARNING),
        ),
        (
            _ID_ISOLATED,
            "Isolated",
            "note",
            "isolated.md",
            dedent("""\
                ---
                id: {id}
                title: Isolated
                type: note
                tags: []
                ---

                This node has no edges and is used for isolation tests.
                """).format(id=_ID_ISOLATED),
        ),
    ]

    for nid, title, ntype, fname, content in nodes:
        fpath = vault / fname
        fpath.write_text(content, encoding="utf-8")
        db.upsert_node({
            "id": nid,
            "title": title,
            "type": ntype,
            "tags": [],
            "path": str(fpath),
            "content": "",
            "content_hash": f"hash_{nid[:8]}",
        })

    # Wire up the edges
    db.upsert_edge(_ID_COGNITION, _ID_ATTENTION, relation="supports")
    db.upsert_edge(_ID_COGNITION, _ID_MEMORY,    relation="is_related_to")
    db.upsert_edge(_ID_COGNITION, _ID_LEARNING,  relation="enables")
    db.upsert_edge(_ID_ATTENTION, _ID_LEARNING,  relation="enables")

    # Expose as a namespace object so tests can access .vault, .db, .id_*
    class Ctx:
        pass

    ctx = Ctx()
    ctx.vault         = vault
    ctx.db            = db
    ctx.id_cognition  = _ID_COGNITION
    ctx.id_attention  = _ID_ATTENTION
    ctx.id_memory     = _ID_MEMORY
    ctx.id_learning   = _ID_LEARNING
    ctx.id_isolated   = _ID_ISOLATED

    yield ctx
    db.close()


@pytest.fixture()
def rag_context(tmp_vault_with_nodes):
    """Pre-built RAG context string for the Cognition root node."""
    GraphDatabase = _load_db()  # noqa: F841 — kept for layout compatibility

    ctx = tmp_vault_with_nodes

    # Import build_context — try flat layout then package layout
    try:
        from rag import build_context  # noqa: PLC0415
    except ImportError:
        from akanga_core.rag import build_context  # noqa: PLC0415

    # Retrieve the root node object from the DB so we can pass it to build_context
    root_node = ctx.db.get_node(ctx.id_cognition)
    if root_node is None:
        pytest.fail(
            "Cognition node not found in DB. Check that tmp_vault_with_nodes "
            "upserted nodes correctly."
        )

    return build_context(root_node, ctx.db, ctx.vault)
