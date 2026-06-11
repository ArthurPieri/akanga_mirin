"""Phase 08 — MCP stdio round-trip smoke test (adversarial-analysis-v3 #12).

Round 3 found that fastmcp's PROTOCOL path never executes anywhere: every
phase-8 test calls the tool functions directly, so an MCP/fastmcp break (a
major-version bump, a transport regression, a broken ``build_server``) ships
green. This is the one test that catches it: spawn the real server process,
speak JSON-RPC over stdio, and assert the five tools are advertised.

Transport contract (documented per the v3 fix path):
    The reference server (``solutions/phase_08/src/akanga_mcp/server.py``)
    defaults to STDIO transport — SEC-04's strongest posture (no network
    socket at all) — and reads AKANGA_VAULT_PATH / AKANGA_DB_PATH from the
    environment in ``__main__``. We set those env vars AND pass
    ``--vault``/``--db`` argv (harmless to the reference, honoured by
    argparse-style implementations). The skeleton's http-only ``__main__``
    predates this contract and is expected to converge on stdio-by-default
    (v3 findings #2/#12).

Gating:
    - Skipped unless AKANGA_SLOW_TESTS is set (subprocess spawn + up to a
      20s hard budget — keep it out of the tight learner loop).
    - Skipped when fastmcp is not installed (the tool functions are usable
      without the transport; this test IS the transport).
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

# Hard ceiling for the whole round-trip; the process is ALWAYS terminated.
HARD_TIMEOUT_S = 20.0

EXPECTED_TOOLS = {
    "search_nodes",
    "get_node",
    "list_relation_types",
    "get_context",
    "create_node",
}

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not os.environ.get("AKANGA_SLOW_TESTS"),
        reason="stdio MCP smoke test is slow — set AKANGA_SLOW_TESTS=1 to run it",
    ),
    pytest.mark.skipif(
        importlib.util.find_spec("fastmcp") is None,
        reason="fastmcp is not installed — the MCP transport cannot run",
    ),
]


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


def test_mcp_stdio_initialize_and_tools_list(tmp_path: Path) -> None:
    """initialize → initialized → tools/list over real stdio must list all 5 tools."""
    src = os.environ.get("AKANGA_SRC")
    assert src, "AKANGA_SRC must be set (the conftest enforces this)."
    src = str(Path(src).resolve())

    vault = tmp_path / "vault"
    vault.mkdir()
    db_path = tmp_path / "graph.db"

    env = dict(os.environ)
    env["PYTHONPATH"] = src + (
        os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else ""
    )
    env["PYTHONUNBUFFERED"] = "1"
    # Reference __main__ contract: env-var init, stdio transport by default.
    env["AKANGA_VAULT_PATH"] = str(vault)
    env["AKANGA_DB_PATH"] = str(db_path)

    cmd = [
        sys.executable,
        "-m",
        "akanga_mcp.server",
        # Honoured by argparse-style entry points; ignored by the reference.
        "--vault", str(vault),
        "--db", str(db_path),
    ]

    proc = subprocess.Popen(  # noqa: S603 — spawning the learner's own server
        cmd,
        cwd=str(tmp_path),
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
            "The MCP server never answered `initialize` over stdio.\n"
            "The reference contract: `python -m akanga_mcp.server` runs "
            "mcp.run() with the DEFAULT stdio transport (SEC-04: no network "
            "socket at all) after init from AKANGA_VAULT_PATH/AKANGA_DB_PATH. "
            "An http-only __main__ (or a server that crashes on startup) "
            "fails this — and would fail every real MCP client the same way.\n"
            f"Process alive: {proc.poll() is None}; stderr tail:\n{stderr_tail}"
        )
        assert "error" not in init_resp, (
            f"`initialize` returned a JSON-RPC error: {init_resp.get('error')!r}\n"
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
    finally:
        # ALWAYS tear the server down — even on assertion failure.
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
