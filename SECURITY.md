# Security Policy

## Scope

Akanga Mirin is a local-first, personal knowledge graph. It is designed to run on a single machine, not exposed to the internet. The threat model is a single trusted user on a single device.

The following are **in scope** for security reports:

- Path traversal vulnerabilities in the REST API or MCP server
- Prompt injection vulnerabilities in the Phase 8 Graph RAG pipeline
- FTS5 operator injection in the search layer
- Symlink escape bypassing vault root confinement (now covered by an automated test: `tests/phase_06/test_server.py::test_create_node_symlink_escape_blocked`)
- Insecure defaults that would expose the server to the local network without user consent
- Bypasses of the Phase 8 `private`-tag / private-workspace exclusion that leak private nodes into LLM context (see below)

The following are **out of scope by design** (deliberate scope decisions, not bugs):

- No authentication on the REST API — the server is localhost-only by default
- No authentication on the WebSocket endpoint — same rationale
- No rate limiting on the REST API — single-user, no external attack surface
- MCP HTTP transport binding — defaults to `127.0.0.1`, not `0.0.0.0`

**LLM client as data-egress channel.** Phase 8 deliberately sends vault content off-machine: every MCP tool result is forwarded by the client (Claude Desktop, Claude Code, any agent) to its configured model provider, and a single `get_context` call can ship up to 12,000 characters of note content. The `127.0.0.1` binding controls who can *reach* the server; it does not constrain this egress. Mitigations: nodes tagged `private` (or in a private workspace) are excluded from `search_nodes` and `build_context`, and the MCP server works unchanged against local models (Ollama, llama.cpp), in which case nothing leaves the machine. The egress itself is by design and out of scope; bypasses of the private-node exclusion are in scope.

## Reporting

To report a security vulnerability privately, email **claude@arthurpieri.com** with the subject line `[SECURITY] Akanga Mirin`.

Please include:
1. A description of the vulnerability and its potential impact
2. Steps to reproduce (minimal example preferred)
3. Which phase(s) are affected

Do not open a public GitHub issue for security vulnerabilities until a fix has been prepared.

## Response

You will receive an acknowledgment within 48 hours. For valid findings in scope, a fix will be prepared within 14 days and credited in the release notes unless you prefer to remain anonymous.
