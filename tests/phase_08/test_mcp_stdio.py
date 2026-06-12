"""Phase 08 — MCP stdio round-trip smoke tests (adversarial-analysis-v3 #12, v4 #2).

Round 3 found that fastmcp's PROTOCOL path never executes anywhere: every
phase-8 test calls the tool functions directly, so an MCP/fastmcp break (a
major-version bump, a transport regression, a broken ``build_server``) ships
green. Round 4 found the entry point itself was broken: ``make mcp`` passes
``--vault``/``--db`` argv that ``__main__`` never parsed, so the server came
up with ``db = None`` and answered every tool with empty results and
``isError: false`` — healthy-looking, knows nothing, forever.

These tests spawn the real server process and speak JSON-RPC over stdio.

Entry-point contract (v4 #2 fix path):
    - ``python -m akanga_mcp.server`` runs ``mcp.run()`` with the DEFAULT
      stdio transport — SEC-04's strongest posture (no network socket at all).
    - ``__main__`` accepts the vault + db via AKANGA_VAULT_PATH/AKANGA_DB_PATH
      env vars OR ``--vault``/``--db`` argv (``make mcp`` passes the latter).
      Each launch mode is exercised HERE in isolation — never both at once,
      so an env-only or argv-only implementation cannot pass by accident.
    - Startup indexes the vault (``full_scan_and_index`` — hash-first, cheap)
      and logs "serving N indexed nodes": a node that exists on disk before
      launch must be findable through ``tools/call`` immediately.
    - With NO vault configuration at all, ``__main__`` exits 2 LOUDLY instead
      of serving an eternally empty graph.

Gating:
    - Skipped unless AKANGA_SLOW_TESTS is set (subprocess spawns + up to a
      20s hard budget per test — keep it out of the tight learner loop).
    - Skipped when fastmcp is not installed (the tool functions are usable
      without the transport; these tests ARE the transport).
    Marked ``slow`` for greppability; the marker is intentionally not yet
    registered in pyproject (config changes are out of this suite's scope).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

# Hard ceiling for a whole round-trip; the process is ALWAYS terminated.
HARD_TIMEOUT_S = 20.0
# Budget for the unconfigured server to notice it has no vault and exit.
EXIT_BUDGET_S = 10.0

EXPECTED_TOOLS = {
    "search_nodes",
    "get_node",
    "list_relation_types",
    "get_context",
    "create_node",
}

# One node written to disk BEFORE the server starts — the startup-indexing probe.
SEED_NODE_ID = "feed5eed-0800-0000-0000-000000000001"
SEED_NODE_TITLE = "Stdio Seeded Node"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("AKANGA_SLOW_TESTS"),
        reason="stdio MCP smoke tests are slow — set AKANGA_SLOW_TESTS=1 to run them",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("fastmcp") is None,
        reason="fastmcp is not installed — the MCP transport cannot run",
    ),
]


# ---------------------------------------------------------------------------
# Process + protocol helpers
# ---------------------------------------------------------------------------

def _resolve_src() -> str:
    src = os.environ.get("AKANGA_SRC")
    assert src, "AKANGA_SRC must be set (the conftest enforces this)."
    return str(Path(src).resolve())


def _seed_node(vault: Path) -> None:
    """Write one well-formed node file into *vault* before the server boots."""
    (vault / "seeded.md").write_text(
        "---\n"
        f"id: {SEED_NODE_ID}\n"
        f"title: {SEED_NODE_TITLE}\n"
        "type: note\n"
        "tags: [seeded]\n"
        "---\n\n"
        "A node that exists on disk before the MCP server starts.\n",
        encoding="utf-8",
    )


def _base_env(src: str) -> dict[str, str]:
    """Subprocess env with PYTHONPATH set and ALL akanga config stripped.

    Stripping AKANGA_VAULT_PATH/AKANGA_DB_PATH matters: each test re-adds
    exactly the configuration channel it is exercising, so leakage from the
    invoking shell can never make a broken entry point look configured.
    """
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("AKANGA_VAULT_PATH", "AKANGA_DB_PATH")
    }
    env["PYTHONPATH"] = src + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONUNBUFFERED"] = "1"
    return env


def _spawn(
    cmd: list[str], cwd: str, env: dict[str, str]
) -> tuple[subprocess.Popen, list[str], list[str]]:
    """Start the server process with stdout/stderr drained by daemon threads."""
    proc = subprocess.Popen(  # noqa: S603 — spawning the learner's own server
        cmd,
        cwd=cwd,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        bufsize=1,
    )
    stdout_lines: list[str] = []
    stderr_lines: list[str] = []
    threading.Thread(target=_pump, args=(proc.stdout, stdout_lines), daemon=True).start()
    threading.Thread(target=_pump, args=(proc.stderr, stderr_lines), daemon=True).start()
    return proc, stdout_lines, stderr_lines


def _teardown(proc: subprocess.Popen) -> None:
    """ALWAYS tear the server down — even on assertion failure."""
    try:
        if proc.stdin and not proc.stdin.closed:
            proc.stdin.close()
    except OSError:
        pass
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait(timeout=5)


def _pump(stream, sink: list[str]) -> None:
    """Drain *stream* line-by-line into *sink* (daemon-thread target)."""
    try:
        for line in stream:
            sink.append(line)
    except ValueError:
        pass  # stream closed under us during teardown — fine


def _send(proc: subprocess.Popen, message: dict) -> None:
    """Write one newline-delimited JSON-RPC message to the server's stdin."""
    proc.stdin.write(json.dumps(message) + "\n")
    proc.stdin.flush()


def _find_response(lines: list[str], request_id: int) -> dict | None:
    """Scan captured stdout lines for the JSON-RPC response to *request_id*."""
    for line in list(lines):
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue  # banners / non-protocol noise on stdout
        if isinstance(msg, dict) and msg.get("id") == request_id:
            return msg
    return None


def _wait_for_response(
    proc: subprocess.Popen,
    lines: list[str],
    request_id: int,
    deadline: float,
) -> dict | None:
    """Poll for the response to *request_id* until *deadline* (monotonic)."""
    while time.monotonic() < deadline:
        msg = _find_response(lines, request_id)
        if msg is not None:
            return msg
        if proc.poll() is not None:
            return _find_response(lines, request_id)  # last chance: exited
        time.sleep(0.05)
    return _find_response(lines, request_id)


# ---------------------------------------------------------------------------
# The smoke: handshake + tools/list + tools/call, per configuration channel
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("config_via", ["env", "argv"])
def test_mcp_stdio_initialize_and_tools_list(tmp_path: Path, config_via: str) -> None:
    """initialize → tools/list → tools/call over real stdio, one config channel at a time.

    ``env``  — AKANGA_VAULT_PATH/AKANGA_DB_PATH only; no argv flags.
    ``argv`` — ``--vault``/``--db`` argv only; env vars stripped. This is
               exactly how ``make mcp`` launches the server (v4 #2): an
               env-only ``__main__`` silently ignores the flags, keeps
               ``db = None``, and serves an eternally empty graph.

    Both channels must (a) advertise all five tools and (b) find a node that
    was on disk BEFORE startup — proving the entry point indexed the vault.
    """
    src = _resolve_src()

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "graph.db"
    _seed_node(vault)

    env = _base_env(src)
    cmd = [sys.executable, "-m", "akanga_mcp.server"]
    if config_via == "env":
        env["AKANGA_VAULT_PATH"] = str(vault)
        env["AKANGA_DB_PATH"] = str(db_path)
    else:
        cmd += ["--vault", str(vault), "--db", str(db_path)]

    proc, stdout_lines, stderr_lines = _spawn(cmd, str(tmp_path), env)

    deadline = time.monotonic() + HARD_TIMEOUT_S
    try:
        _send(proc, {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "akanga-stdio-smoke", "version": "0.0.0"},
            },
        })

        init_resp = _wait_for_response(proc, stdout_lines, 1, deadline)
        stderr_tail = "".join(stderr_lines[-20:])
        assert init_resp is not None, (
            f"The MCP server never answered `initialize` over stdio "
            f"(config via {config_via}).\n"
            "The entry-point contract: `python -m akanga_mcp.server` runs "
            "mcp.run() with the DEFAULT stdio transport (SEC-04: no network "
            "socket at all) after initializing from AKANGA_VAULT_PATH/"
            "AKANGA_DB_PATH env vars OR --vault/--db argv (`make mcp` passes "
            "the flags). An http-only __main__, an argv parser that chokes on "
            "the flags, or a server that crashes on startup fails this — and "
            "would fail every real MCP client the same way.\n"
            f"Process alive: {proc.poll() is None}; stderr tail:\n{stderr_tail}"
        )
        assert "error" not in init_resp, (
            f"`initialize` returned a JSON-RPC error (config via {config_via}): "
            f"{init_resp.get('error')!r}\n"
            f"stderr tail:\n{stderr_tail}"
        )
        assert "result" in init_resp, (
            f"`initialize` response has no result: {init_resp!r}"
        )

        # Per the MCP handshake, acknowledge before issuing requests.
        _send(proc, {"jsonrpc": "2.0", "method": "notifications/initialized"})

        _send(proc, {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})

        tools_resp = _wait_for_response(proc, stdout_lines, 2, deadline)
        stderr_tail = "".join(stderr_lines[-20:])
        assert tools_resp is not None, (
            "The MCP server answered `initialize` but never answered "
            "`tools/list` within the time budget.\n"
            f"stderr tail:\n{stderr_tail}"
        )
        assert "error" not in tools_resp, (
            f"`tools/list` returned a JSON-RPC error: {tools_resp.get('error')!r}"
        )

        tools = tools_resp.get("result", {}).get("tools", [])
        names = {t.get("name") for t in tools if isinstance(t, dict)}
        missing = EXPECTED_TOOLS - names
        assert not missing, (
            f"tools/list is missing {sorted(missing)!r} — it advertised "
            f"{sorted(names)!r}.\n"
            "build_server() must register all five tool functions "
            "(search_nodes, get_node, list_relation_types, get_context, "
            "create_node) on the FastMCP app. A tool that unit tests call "
            "directly but the server never registers is invisible to every "
            "MCP client."
        )

        # ---- Startup indexing (v4 #2): the seeded node must be findable ----
        _send(proc, {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "search_nodes", "arguments": {"query": "Seeded"}},
        })

        call_resp = _wait_for_response(proc, stdout_lines, 3, deadline)
        stderr_tail = "".join(stderr_lines[-20:])
        assert call_resp is not None, (
            "The MCP server answered `tools/list` but never answered the "
            "`tools/call` for search_nodes within the time budget.\n"
            f"stderr tail:\n{stderr_tail}"
        )
        assert "error" not in call_resp, (
            f"`tools/call` search_nodes returned a JSON-RPC error: "
            f"{call_resp.get('error')!r}\nstderr tail:\n{stderr_tail}"
        )
        result = call_resp.get("result", {})
        assert not result.get("isError"), (
            f"`tools/call` search_nodes reported isError: {result!r}\n"
            f"stderr tail:\n{stderr_tail}"
        )

        payload = json.dumps(result)
        assert SEED_NODE_ID in payload, (
            f"search_nodes('Seeded') did not return the node that was on disk "
            f"BEFORE the server started (config via {config_via}).\n"
            f"tools/call result: {payload}\n"
            "The startup path (__main__ → init_server) must full_scan_and_index "
            "the vault before serving — the scan is hash-first idempotent, so "
            "it is cheap, and logging 'serving N indexed nodes' makes a "
            "misconfigured vault path loud. A server that opens an empty .db "
            "over a full vault answers every tool with empty results and "
            "isError:false — healthy-looking, knows nothing, forever "
            "(adversarial-analysis-v4 #2)."
        )
    finally:
        _teardown(proc)


# ---------------------------------------------------------------------------
# The loud-fail contract: no vault config at all → exit 2, never serve
# ---------------------------------------------------------------------------

def test_mcp_stdio_unconfigured_exits_loudly(tmp_path: Path) -> None:
    """With NO vault configuration the server must exit nonzero quickly.

    The v4 #2 failure mode: ``__main__`` skipped init_server when the env
    vars were missing and started the transport anyway — db stayed None and
    every tool answered empty with isError:false, with no startup warning.
    The contract: no env vars + no argv = exit status 2 with a message naming
    the missing configuration; the transport must never start.
    """
    src = _resolve_src()
    env = _base_env(src)  # AKANGA_VAULT_PATH/AKANGA_DB_PATH stripped, no argv

    proc, stdout_lines, stderr_lines = _spawn(
        [sys.executable, "-m", "akanga_mcp.server"], str(tmp_path), env
    )
    try:
        deadline = time.monotonic() + EXIT_BUDGET_S
        while time.monotonic() < deadline and proc.poll() is None:
            time.sleep(0.1)

        returncode = proc.poll()
        stderr_tail = "".join(stderr_lines[-20:])
        assert returncode is not None, (
            f"The server is still running {EXIT_BUDGET_S:.0f}s after being "
            "launched with NO vault configuration (no AKANGA_VAULT_PATH/"
            "AKANGA_DB_PATH, no --vault/--db).\n"
            "__main__ must fail LOUDLY here: print what is missing to stderr "
            "and sys.exit(2). Starting the transport with db=None produces "
            "the v4 #2 zombie — a healthy-looking MCP server whose every tool "
            "returns empty with isError:false, forever.\n"
            f"stderr tail:\n{stderr_tail}"
        )
        assert returncode != 0, (
            f"The unconfigured server exited with status 0.\n"
            f"stderr tail:\n{stderr_tail}\n"
            "Misconfiguration must be a loud failure (exit status 2, message "
            "on stderr) — exit 0 lets `make mcp` and MCP clients believe the "
            "server came up fine."
        )
    finally:
        _teardown(proc)
