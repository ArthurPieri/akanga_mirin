"""Phase 08 test suite — MCP server tool functions.

Tests for akanga_mcp/server.py. The MCP server uses FastMCP and must export
the following tool functions (callable directly, not through the MCP protocol):

    search_nodes(query: str) -> list[dict] | dict
    get_node(node_id: str) -> dict | None
    list_relation_types() -> list[dict]
    get_context(node_id: str) -> str | dict
    create_node(title: str, type: str, content: str) -> dict

Security requirements under test:
    SEC-04: Server host must be "127.0.0.1" (never "0.0.0.0")
    SEC-06: FTS search must not crash on FTS5 operator injection

Testing approach: we call the underlying Python tool functions directly
rather than spinning up a live HTTP/stdio MCP server. This keeps tests fast
and dependency-free (no running process needed).

All imports happen inside test functions or fixtures so the AKANGA_SRC
sys.path insertion from conftest runs first.
"""
from __future__ import annotations

import ast
import inspect
import uuid
from pathlib import Path
from textwrap import dedent

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_mcp_server():
    """Import the learner's MCP server module.

    Tries akanga_mcp.server first (package layout), then mcp_server (flat).
    Returns the module object.
    """
    try:
        import akanga_mcp.server as _s  # noqa: PLC0415
        return _s
    except ImportError:
        pass

    try:
        import mcp_server as _s  # noqa: PLC0415
        return _s
    except ImportError:
        pass

    pytest.fail(
        "Could not import the MCP server module from AKANGA_SRC.\n"
        "Expected one of:\n"
        "  $AKANGA_SRC/akanga_mcp/server.py\n"
        "  $AKANGA_SRC/mcp_server.py\n"
        "Make sure your file exists and has no syntax errors."
    )


def _get_tool(server_mod, name: str):
    """Return a callable tool function by name, unwrapping FastMCP decorators if needed."""
    obj = getattr(server_mod, name, None)
    if obj is None:
        pytest.fail(
            f"MCP server module has no '{name}' function. "
            f"Implement it and decorate with @mcp.tool()."
        )
    # FastMCP may wrap the function; try to get the underlying callable
    if callable(obj):
        return obj
    pytest.fail(
        f"'{name}' in the MCP server module is not callable. "
        f"Got {type(obj).__name__!r}."
    )


def _bootstrap_db(server_mod, vault: Path, db_path: Path,
                  nodes: list[dict], edges: list[tuple]) -> None:
    """Inject a populated database into the server module's global state.

    Tries server_mod.init_server(vault, db_path) first; falls back to
    setting server_mod.db directly.
    """
    # Dual-layout import: flat 'db' first, then 'akanga_core.db' (package layout)
    try:
        from db import GraphDatabase  # noqa: PLC0415
    except ModuleNotFoundError:
        try:
            from akanga_core.db import GraphDatabase  # noqa: PLC0415
        except ModuleNotFoundError:
            pytest.fail("Cannot import GraphDatabase from 'db' or 'akanga_core.db'")

    db = GraphDatabase(str(db_path))
    for node in nodes:
        fpath = vault / node["fname"]
        fpath.write_text(node["content"], encoding="utf-8")
        db.upsert_node({k: v for k, v in node.items() if k != "fname" and k != "content"})
    for src_id, tgt_id, relation, relation_id in edges:
        # upsert_edge is positional: (source_id, target_id, relation, relation_id)
        db.upsert_edge(src_id, tgt_id, relation, relation_id)

    # Try the official init path first
    init_server = getattr(server_mod, "init_server", None)
    if init_server is not None:
        try:
            init_server(vault, db_path)
            return
        except Exception:
            pass  # fall through to direct injection

    # Direct injection fallback
    if hasattr(server_mod, "db"):
        server_mod.db = db
    else:
        pytest.fail(
            "Could not inject database into MCP server module. "
            "Implement init_server(vault, db_path) or expose a 'db' module global."
        )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_ID_COGNITION = str(uuid.UUID("aaaaaaaa-0800-0000-0000-000000000001"))
_ID_ATTENTION = str(uuid.UUID("bbbbbbbb-0800-0000-0000-000000000002"))
_ID_MEMORY    = str(uuid.UUID("cccccccc-0800-0000-0000-000000000003"))
_ID_BOOLEAN   = str(uuid.UUID("dddddddd-0800-0000-0000-000000000006"))


@pytest.fixture()
def mcp_env(tmp_path: Path):
    """Server module with a pre-populated database injected.

    Returns (server_module, vault_path, db_path, id_cognition, id_attention, id_memory).
    """
    server_mod = _load_mcp_server()
    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "mcp_test.db"

    nodes = [
        {
            "id": _ID_COGNITION,
            "title": "Cognition",
            "type": "note",
            "tags": [],
            "path": str(vault / "cognition.md"),
            "content_hash": "h_cog",
            "fname": "cognition.md",
            "content": dedent(f"""\
                ---
                id: {_ID_COGNITION}
                title: Cognition
                type: note
                tags: [cognition]
                ---

                Cognition is the mental process of acquiring knowledge.
                """),
        },
        {
            "id": _ID_ATTENTION,
            "title": "Attention",
            "type": "note",
            "tags": [],
            "path": str(vault / "attention.md"),
            "content_hash": "h_att",
            "fname": "attention.md",
            "content": dedent(f"""\
                ---
                id: {_ID_ATTENTION}
                title: Attention
                type: note
                tags: [attention]
                ---

                Attention is selective concentration on information.
                """),
        },
        {
            "id": _ID_MEMORY,
            "title": "Memory",
            "type": "note",
            "tags": [],
            "path": str(vault / "memory.md"),
            "content_hash": "h_mem",
            "fname": "memory.md",
            "content": dedent(f"""\
                ---
                id: {_ID_MEMORY}
                title: Memory
                type: note
                tags: [memory]
                ---

                Memory is the faculty by which information is encoded and stored.
                """),
        },
        {
            "id": _ID_BOOLEAN,
            "title": "Boolean OR Logic",
            "type": "note",
            "tags": [],
            "path": str(vault / "boolean-or-logic.md"),
            "content_hash": "h_bool",
            "fname": "boolean-or-logic.md",
            "content": dedent(f"""\
                ---
                id: {_ID_BOOLEAN}
                title: Boolean OR Logic
                type: note
                tags: [logic]
                ---

                A node whose title contains an FTS5 operator, for SEC-06 tests.
                """),
        },
    ]
    edges = [
        # (source_id, target_id, relation, relation_id) — relation_id from
        # the registry in docs/foundations/relation-vocabulary.md
        (_ID_COGNITION, _ID_ATTENTION, "supports",      "EP-001"),
        (_ID_COGNITION, _ID_MEMORY,    "is_related_to", "CC-007"),
    ]

    _bootstrap_db(server_mod, vault, db_path, nodes, edges)

    class Env:
        mod           = server_mod
        vault_path    = vault
        id_cognition  = _ID_COGNITION
        id_attention  = _ID_ATTENTION
        id_memory     = _ID_MEMORY
        id_boolean    = _ID_BOOLEAN

    return Env()


# ---------------------------------------------------------------------------
# Tool function tests
# ---------------------------------------------------------------------------

class TestSearchNodes:
    def test_search_nodes_returns_results(self, mcp_env) -> None:
        """search_nodes('cognition') must return a non-empty list of matching nodes."""
        search_nodes = _get_tool(mcp_env.mod, "search_nodes")
        result = search_nodes("cognition")

        # Result may be a list directly or wrapped in {"nodes": [...]}
        nodes = result if isinstance(result, list) else result.get("nodes", result)
        assert isinstance(nodes, list), (
            f"search_nodes must return a list (or dict with 'nodes' key), "
            f"got {type(result).__name__!r}."
        )
        assert len(nodes) > 0, (
            "search_nodes('cognition') must return at least one result. "
            "The Cognition node was indexed with tag 'cognition'."
        )

    def test_search_nodes_empty_query_returns_all_or_empty(
        self, mcp_env
    ) -> None:
        """search_nodes('') must not crash — consistent behavior (all or empty)."""
        search_nodes = _get_tool(mcp_env.mod, "search_nodes")
        try:
            result = search_nodes("")
            nodes = result if isinstance(result, list) else result.get("nodes", result)
            assert isinstance(nodes, list), (
                f"search_nodes('') must return a list, got {type(result).__name__!r}."
            )
        except Exception as exc:
            pytest.fail(
                f"search_nodes('') must not crash, but raised "
                f"{type(exc).__name__}: {exc}"
            )

    def test_search_nodes_fts_injection_safe(self, mcp_env) -> None:
        """search_nodes with FTS5 operator injection must not crash.

        SEC-06: FTS5 operators like '* OR title:*' must be treated as literal
        text, not as FTS5 syntax. The result must be an empty list or valid
        results — never an unhandled exception.
        """
        search_nodes = _get_tool(mcp_env.mod, "search_nodes")
        try:
            result = search_nodes("* OR title:*")
            nodes = result if isinstance(result, list) else result.get("nodes", result)
            assert isinstance(nodes, list), (
                "search_nodes FTS injection query must return a list, "
                f"got {type(result).__name__!r}."
            )
        except Exception as exc:
            pytest.fail(
                "search_nodes('* OR title:*') must not crash (SEC-06). "
                "Wrap user terms in double-quotes before passing to FTS5. "
                f"Got {type(exc).__name__}: {exc}"
            )

    def test_search_nodes_operator_treated_as_literal(self, mcp_env) -> None:
        """SEC-06 semantic check: searching 'OR' must match the literal title.

        The fixture indexes a node titled 'Boolean OR Logic'. An implementation
        that swallows the FTS5 error (try/except: return []) passes the
        no-crash test but fails this one — the quoting mitigation must treat
        the operator as a searchable literal term.
        """
        search_nodes = _get_tool(mcp_env.mod, "search_nodes")
        result = search_nodes("OR")
        nodes = result if isinstance(result, list) else result.get("nodes", result)

        assert any(
            n.get("id") == mcp_env.id_boolean or "Boolean OR Logic" in str(n.get("title", ""))
            for n in nodes
        ), (
            "search_nodes('OR') must return the node titled 'Boolean OR Logic'. "
            "Double-quote each user term before FTS5 MATCH so operators are "
            "treated as literal text — returning [] by swallowing the FTS5 "
            f"error is NOT a fix. Got: {nodes!r}"
        )

    def test_search_nodes_embedded_double_quote_safe(self, mcp_env) -> None:
        """SEC-06: a query containing a double quote must not raise.

        Naive quoting ('\"' + term + '\"') breaks when the term itself contains
        a quote — strip embedded quotes before wrapping (the reference
        implementation needed exactly this handling).
        """
        search_nodes = _get_tool(mcp_env.mod, "search_nodes")
        try:
            result = search_nodes('cogn"ition')
            nodes = result if isinstance(result, list) else result.get("nodes", result)
            assert isinstance(nodes, list), (
                "search_nodes on a quoted term must return a list, "
                f"got {type(result).__name__!r}."
            )
        except Exception as exc:
            pytest.fail(
                "search_nodes('cogn\"ition') must not crash (SEC-06). "
                "Strip embedded double quotes from each term before wrapping: "
                f"term.replace('\"', ''). Got {type(exc).__name__}: {exc}"
            )


class TestGetNode:
    def test_get_node_returns_dict(self, mcp_env) -> None:
        """get_node(valid_id) must return a dict with at least 'id' and 'title'."""
        get_node = _get_tool(mcp_env.mod, "get_node")
        result = get_node(mcp_env.id_cognition)

        assert isinstance(result, dict), (
            f"get_node must return a dict, got {type(result).__name__!r}."
        )
        for key in ("id", "title"):
            assert key in result, (
                f"get_node result must have '{key}' key. Got keys: {list(result.keys())}"
            )

    def test_get_node_not_found(self, mcp_env) -> None:
        """get_node with a nonexistent ID must return None or a dict with 'error' key.

        The learner may choose either behavior — both are acceptable per spec.
        What is NOT acceptable: raising an unhandled exception.
        """
        get_node = _get_tool(mcp_env.mod, "get_node")
        nonexistent = str(uuid.UUID("00000000-dead-beef-0000-000000000000"))

        try:
            result = get_node(nonexistent)
            assert result is None or (
                isinstance(result, dict) and ("error" in result or not result)
            ), (
                f"get_node for nonexistent ID must return None or {{'error': ...}}, "
                f"got {result!r}."
            )
        except Exception as exc:
            pytest.fail(
                f"get_node for nonexistent ID must not raise, "
                f"got {type(exc).__name__}: {exc}"
            )


class TestListRelationTypes:
    def test_list_relation_types_returns_71(self, mcp_env) -> None:
        """list_relation_types() must return all 71 built-in relation types.

        The 71 types span 11 prefix categories: EP, HT, SC, CT, AP, DR, CC,
        EV, PA, SO, TC. The registry is docs/foundations/relation-vocabulary.md.
        Custom (learner-defined) types may append beyond 71 — but a partial
        built-in list is a bug, not an implementation choice.
        """
        list_relation_types = _get_tool(mcp_env.mod, "list_relation_types")
        result = list_relation_types()

        assert isinstance(result, list), (
            f"list_relation_types must return a list, "
            f"got {type(result).__name__!r}."
        )
        assert len(result) >= 71, (
            f"list_relation_types must return all 71 built-in relation types, "
            f"got {len(result)}.\n"
            "Load the full registry (docs/foundations/relation-vocabulary.md — "
            "the Phase 1 relation registry) — do not hardcode a sample subset."
        )
        # Each item must be a dict with an 'id' or 'name' key
        for item in result[:5]:  # spot-check first 5
            assert isinstance(item, dict), (
                f"Each relation type must be a dict, got {type(item).__name__!r}: {item!r}"
            )
            assert "id" in item or "name" in item, (
                f"Each relation type dict must have 'id' or 'name', got: {item!r}"
            )


class TestGetContext:
    def test_get_context_returns_string(self, mcp_env) -> None:
        """get_context(valid_id) must return a non-empty string containing the node title."""
        get_context = _get_tool(mcp_env.mod, "get_context")
        result = get_context(mcp_env.id_cognition)

        # Result may be a string directly or wrapped in {"context": "..."}
        if isinstance(result, dict):
            ctx_str = result.get("context", "")
        else:
            ctx_str = result

        assert isinstance(ctx_str, str), (
            f"get_context must return a string (or dict with 'context' key), "
            f"got {type(result).__name__!r}."
        )
        assert "Cognition" in ctx_str, (
            "get_context for the Cognition node must include 'Cognition' in output. "
            f"Got: {ctx_str[:300]!r}"
        )


class TestCreateNode:
    def test_create_node_via_mcp(self, mcp_env) -> None:
        """create_node must return a dict containing an 'id' key.

        The created node must also be written to disk as a .md file.
        """
        create_node = _get_tool(mcp_env.mod, "create_node")

        try:
            result = create_node(title="MCP Test Node", type="note", content="Test body.")
        except TypeError:
            # Alternate signature: create_node(title, node_type, body, tags)
            result = create_node(
                title="MCP Test Node", node_type="note",
                body="Test body.", tags=[]
            )

        assert isinstance(result, dict), (
            f"create_node must return a dict, got {type(result).__name__!r}."
        )
        assert "id" in result, (
            f"create_node result must have an 'id' key, got: {list(result.keys())}"
        )
        node_id = result["id"]
        assert node_id, "create_node must return a non-empty id."

        # The .md file should exist somewhere in the vault
        md_files = list(mcp_env.vault_path.rglob("*.md"))
        titles_in_files = [
            f.name for f in md_files
            if "MCP Test Node" in f.read_text(encoding="utf-8")
        ]
        assert titles_in_files, (
            "create_node must write a .md file to the vault containing the node title. "
            f"Vault .md files: {[f.name for f in md_files]}"
        )


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------

def _find_wildcard_host_bindings(source: str) -> list[int]:
    """Return line numbers where '0.0.0.0' is used as a VALUE in code.

    AST-based so that comments, docstrings, and NotImplementedError messages
    that merely *mention* '0.0.0.0' (the skeleton's own security warnings do,
    three times) never trigger a false positive. Flags the string literal only
    when it appears as:
      - the right-hand side of an assignment (host = "0.0.0.0")
      - a function-parameter default (def run(host="0.0.0.0"))
      - a keyword-argument value (mcp.run(host="0.0.0.0"),
        parser.add_argument("--host", default="0.0.0.0"))
    """

    def _contains_wildcard(node: ast.AST) -> bool:
        return any(
            isinstance(sub, ast.Constant) and sub.value == "0.0.0.0"
            for sub in ast.walk(node)
        )

    offenders: list[int] = []
    for node in ast.walk(ast.parse(source)):
        suspects: list[ast.AST] = []
        if isinstance(node, (ast.Assign, ast.AugAssign)) and node.value is not None:
            suspects.append(node.value)
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            suspects.append(node.value)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            args = node.args
            suspects.extend(d for d in args.defaults if d is not None)
            suspects.extend(d for d in args.kw_defaults if d is not None)
        elif isinstance(node, ast.keyword):
            suspects.append(node.value)

        for suspect in suspects:
            if _contains_wildcard(suspect):
                offenders.append(getattr(suspect, "lineno", getattr(node, "lineno", 0)))
    return sorted(set(offenders))


class TestMcpSecurity:
    def test_mcp_server_binds_localhost(self, mcp_env) -> None:
        """SEC-04: The MCP server must bind to 127.0.0.1, never 0.0.0.0.

        We parse the server module's AST rather than substring-scanning the
        source — the skeleton's own comments and error messages legitimately
        mention '0.0.0.0' while warning against it, and a learner must not
        fail SEC-04 for keeping those warnings.
        """
        server_mod = mcp_env.mod
        source_file = inspect.getfile(server_mod)

        try:
            source = Path(source_file).read_text(encoding="utf-8")
        except (OSError, TypeError):
            pytest.skip(
                "Cannot read server module source file to verify host binding."
            )

        offenders = _find_wildcard_host_bindings(source)
        assert not offenders, (
            f"SEC-04: '0.0.0.0' is used as a value in the MCP server source "
            f"(line(s) {offenders}).\n"
            "Use host='127.0.0.1' (localhost only) — binding to all interfaces "
            "exposes the server (and your private vault) to the network.\n"
            "Comments and warning messages mentioning 0.0.0.0 are fine; "
            "assigning or defaulting to it is not."
        )

        # And it should mention 127.0.0.1 (the expected safe default)
        # This is a soft check — the host may be passed via CLI arg
        has_localhost = "127.0.0.1" in source or "localhost" in source
        if not has_localhost:
            # Emit a warning-style assert rather than fail — host may come from config
            import warnings
            warnings.warn(
                "SEC-04: Could not find '127.0.0.1' or 'localhost' in MCP server "
                "source. Verify that the server binds to localhost by default.",
                stacklevel=1,
            )
