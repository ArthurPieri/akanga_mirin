# JSON-RPC Basics

A practical reference for the JSON-RPC 2.0 protocol and how it underlies MCP
(Model Context Protocol) — the technology behind Phase 8 of the akanga learning
path.

---

## What JSON-RPC 2.0 is

JSON-RPC is a protocol for calling functions on a remote process. The caller
sends a JSON object describing which function to call and what arguments to pass.
The callee (server) runs the function and returns a JSON object with the result.

It is intentionally minimal: no special binary encoding, no IDL compiler, no
generated stubs. Any process that can read and write JSON can speak JSON-RPC.

The "2.0" in the name distinguishes it from the older 1.x spec. Version 2.0 is
what MCP uses.

---

## Message formats

### Request

The caller sends this to invoke a function:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "get_node",
    "arguments": {
      "node_id": "3f8a1b2c-4d5e-6789-abcd-ef0123456789"
    }
  },
  "id": 1
}
```

Fields:
- `"jsonrpc": "2.0"` — always present; identifies the protocol version.
- `"method"` — the name of the function to call (a string).
- `"params"` — the arguments. Can be an object (named params) or an array
  (positional params). Named params are almost always preferred.
- `"id"` — a request identifier. The server copies this into the response so the
  caller can match responses to requests. Can be a number, string, or null.

### Response (success)

```json
{
  "jsonrpc": "2.0",
  "result": {
    "id": "3f8a1b2c-4d5e-6789-abcd-ef0123456789",
    "title": "My Node",
    "type": "note"
  },
  "id": 1
}
```

Fields:
- `"result"` — whatever the function returned. Can be any JSON value.
- `"id"` — matches the request's `id`.
- Never contains both `"result"` and `"error"`.

### Response (error)

When something goes wrong, the server returns an error object instead of a result:

```json
{
  "jsonrpc": "2.0",
  "error": {
    "code": -32602,
    "message": "Invalid params",
    "data": "node_id must be a UUID string"
  },
  "id": 1
}
```

Standard error codes:

| Code | Name | Meaning |
|------|------|---------|
| -32700 | Parse error | Invalid JSON was received |
| -32600 | Invalid Request | The JSON is not a valid Request object |
| -32601 | Method not found | The method does not exist |
| -32602 | Invalid params | Invalid method parameters |
| -32603 | Internal error | Internal server error |
| -32000 to -32099 | Server error | Application-defined server errors |

### Notification (fire-and-forget)

A request without an `id` field is a **notification**. The server must not send
a response. Use it for events you don't need confirmation for:

```json
{
  "jsonrpc": "2.0",
  "method": "notifications/resources/updated",
  "params": {
    "uri": "akanga://nodes/3f8a1b2c"
  }
}
```

No `"id"` field = notification = no response expected.

---

## Transport: stdio vs HTTP

JSON-RPC says nothing about how messages travel. The spec is transport-agnostic.
In practice, two transports dominate:

### stdio

The client spawns the server as a **subprocess**. The server reads JSON-RPC
requests from `stdin` and writes responses to `stdout`. One message per line
(newline-delimited JSON).

```
┌─────────────────────────────────────────────────────┐
│  Claude Desktop (client)                            │
│                                                     │
│  spawns subprocess: python -m akanga_mcp            │
│  writes to subprocess stdin: {"jsonrpc":"2.0",...}  │
│  reads from subprocess stdout: {"jsonrpc":"2.0",...}│
└─────────────────────────────────────────────────────┘
         |  stdin / stdout  |
┌─────────────────────────────────────────────────────┐
│  akanga MCP server (subprocess)                     │
│                                                     │
│  reads from sys.stdin                               │
│  writes to sys.stdout                               │
└─────────────────────────────────────────────────────┘
```

**Why stdio for MCP?** Claude Desktop spawns MCP servers on startup. Stdio is the
simplest possible transport:
- No port conflicts (no network socket needed)
- No authentication required (only the parent process can write to stdin)
- Works identically on macOS, Linux, and Windows
- The subprocess dies when Claude Desktop exits — no orphaned processes

### HTTP

The server listens on a port; the client POSTs JSON-RPC requests to an endpoint.
Better for long-running shared services but adds network overhead and port
management. MCP also supports HTTP+SSE transport, but stdio is the default for
local use.

---

## MCP: JSON-RPC 2.0 applied to AI tooling

MCP (Model Context Protocol) is a specification built on top of JSON-RPC 2.0.
It defines a standard way for LLMs to call external tools, read resources, and
receive structured outputs.

### How it maps

| JSON-RPC concept | MCP concept |
|---|---|
| Method call | Tool invocation |
| `method` field | Tool name (`tools/call` method with `name` param) |
| `params` | Tool arguments |
| `result` | Tool return value (text, JSON, image, etc.) |
| Notification | Server-sent event (resource updated, etc.) |

### MCP methods (a subset)

```
initialize          — handshake, exchange capabilities
tools/list          — list available tools
tools/call          — invoke a tool
resources/list      — list available resources
resources/read      — read a resource
prompts/list        — list available prompts
prompts/get         — get a prompt template
```

The LLM (Claude) acts as the **client**. Your MCP server acts as the **server**.
Claude sends `tools/call` requests; your server runs the function and returns the
result.

---

## FastMCP: writing MCP servers without boilerplate

FastMCP is a Python library that hides the JSON-RPC encoding/decoding. You write
plain Python functions decorated with `@mcp.tool()`. FastMCP handles:

- Reading newline-delimited JSON from stdin
- Parsing the `jsonrpc` envelope
- Routing `tools/call` to the right function
- Serializing the return value into a `result` response
- Writing the response to stdout

### A minimal MCP server

```python
from fastmcp import FastMCP

mcp = FastMCP("akanga")

@mcp.tool()
def get_node(node_id: str) -> dict:
    """Retrieve a node from the akanga knowledge graph by UUID."""
    node = db.get_node(node_id)
    if node is None:
        raise ValueError(f"Node {node_id} not found")
    return {
        "id": node.id,
        "title": node.title,
        "type": node.type,
        "tags": node.tags,
        "content": node.content,
    }

@mcp.tool()
def search_nodes(query: str, limit: int = 10) -> list[dict]:
    """Full-text search over the akanga vault."""
    nodes = db.search_fts(query, limit=limit)
    return [{"id": n.id, "title": n.title, "type": n.type} for n in nodes]

if __name__ == "__main__":
    mcp.run()   # reads from stdin, writes to stdout
```

When Claude calls the `get_node` tool, FastMCP receives this from stdin:

```json
{"jsonrpc":"2.0","method":"tools/call","params":{"name":"get_node","arguments":{"node_id":"3f8a..."}},"id":7}
```

FastMCP calls `get_node(node_id="3f8a...")` and writes this to stdout:

```json
{"jsonrpc":"2.0","result":{"content":[{"type":"text","text":"{\"id\":\"3f8a...\",\"title\":\"My Node\",...}"}]},"id":7}
```

Your function never sees the envelope. You write Python; FastMCP handles the
protocol.

### Type hints become the schema

FastMCP inspects type hints to build the tool's JSON Schema — the description of
what parameters the tool accepts. Claude uses this schema to know how to call the
tool correctly:

```python
@mcp.tool()
def create_node(
    title: str,
    type: str = "note",
    tags: list[str] | None = None,
    content: str = "",
) -> dict:
    """Create a new node in the vault."""
    ...
```

Claude sees this as a tool that requires `title` (string) and optionally accepts
`type`, `tags`, and `content`. The docstring becomes the tool description.

---

## What happens end-to-end

1. You add akanga's MCP server to Claude Desktop's config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "akanga": {
      "command": "uv",
      "args": ["run", "python", "-m", "akanga_mcp"],
      "env": {
        "AKANGA_VAULT": "/Users/yourname/vault",
        "AKANGA_DB": "/Users/yourname/.akanga.db"
      }
    }
  }
}
```

2. Claude Desktop spawns `python -m akanga_mcp` as a subprocess on startup.

3. The subprocess sends an `initialize` response advertising its tools.

4. When you ask Claude "what are my active nodes?", Claude decides to call the
   `search_nodes` tool with `type="active"`.

5. Claude sends a JSON-RPC `tools/call` request to the subprocess via stdin.

6. FastMCP routes it to your `search_nodes` function.

7. Your function queries the SQLite database and returns a list.

8. FastMCP serializes the list and writes the JSON-RPC response to stdout.

9. Claude reads the response and incorporates the data into its reply to you.

---

## In your implementation (Phase 8)

- **Phase 8** of the learning path is where you build the MCP server (`akanga_mcp` in your implementation).
- The server uses FastMCP. You'll implement tools for `get_node`, `search_nodes`,
  `create_node`, `get_neighbors`, and `get_backlinks`.
- The protocol under the hood is JSON-RPC 2.0 over stdio.
- You can test the server manually by piping JSON into it:

```bash
echo '{"jsonrpc":"2.0","method":"tools/list","id":1}' | uv run python -m akanga_mcp
```

- The phase doc walks through reading the FastMCP source to see the
  envelope handling that you don't have to write yourself.
