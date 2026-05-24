# Running Akanga Unattended

Akanga is a personal, local tool. It has no cloud infrastructure, no Docker image,
and no required network access. The deployment options reflect that: this document
covers three ways to run the server persistently on your own machine, plus the
simplest option for day-to-day developer use.

Choose the approach that matches your workflow:

| Approach | Best for |
|---|---|
| tmux named session | Developers; easy to attach and inspect |
| macOS launchd | Auto-start on login; background service |
| Linux systemd (user) | Auto-start on login; background service |
| `make serve` | One-off manual start from a terminal |

All approaches run the same command: `akanga serve --vault ./vault --db ./.akanga.db`.
The vault and DB paths are the only things you need to adjust for your setup.

---

## Option 1 — tmux Named Session (Recommended for Developers)

If you already use tmux, this is the lowest-overhead approach. A named session
keeps the server running in the background, lets you attach to check logs, and
survives disconnection from your terminal.

**Start the server in a detached session:**

```bash
tmux new-session -d -s akanga-server \
  -e VAULT="$HOME/vault" \
  "uv run python -m akanga_core.cli serve \
    --vault $HOME/vault \
    --db $HOME/.akanga.db \
    --host 127.0.0.1 \
    --port 8000"
```

**Attach to see the live log:**

```bash
tmux attach -t akanga-server
```

Detach again without stopping the server: `Ctrl-b d`.

**Check whether the session is running:**

```bash
tmux ls | grep akanga-server
```

**Stop the server:**

```bash
tmux kill-session -t akanga-server
```

**Start the TUI in a second window of the same session:**

```bash
tmux new-window -t akanga-server \
  "uv run python -m akanga_core.cli tui \
    --vault $HOME/vault \
    --db $HOME/.akanga.db"
```

**Tip for project-local use:** If you keep your vault inside a project directory,
set `VAULT=$(pwd)/vault` and start the session from that directory so relative
paths resolve correctly.

---

## Option 2 — macOS launchd (Auto-Start on Login)

launchd is macOS's service manager. A plist file in `~/Library/LaunchAgents/`
starts Akanga automatically when you log in and keeps it running — restarting it
if it crashes.

### Step 1 — Write the plist file

Create the file at `~/Library/LaunchAgents/com.akanga.server.plist`. Substitute
your actual username and vault path where indicated.

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.akanga.server</string>

    <!-- The command to run. Adjust the paths to match your setup. -->
    <key>ProgramArguments</key>
    <array>
        <!-- Use the full path to uv — find it with: which uv -->
        <string>/Users/YOUR_USERNAME/.local/bin/uv</string>
        <string>run</string>
        <string>python</string>
        <string>-m</string>
        <string>akanga_core.cli</string>
        <string>serve</string>
        <string>--vault</string>
        <string>/Users/YOUR_USERNAME/vault</string>
        <string>--db</string>
        <string>/Users/YOUR_USERNAME/.akanga.db</string>
        <string>--host</string>
        <string>127.0.0.1</string>
        <string>--port</string>
        <string>8000</string>
    </array>

    <!-- Working directory — must contain pyproject.toml for uv to resolve the venv -->
    <key>WorkingDirectory</key>
    <string>/Users/YOUR_USERNAME/code/akanga</string>

    <!-- Start at login -->
    <key>RunAtLoad</key>
    <true/>

    <!-- Restart if the process exits unexpectedly -->
    <key>KeepAlive</key>
    <true/>

    <!-- Log files — check these when something goes wrong -->
    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/akanga/server.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/Library/Logs/akanga/server-error.log</string>

    <!-- Environment variables available to the process -->
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/Users/YOUR_USERNAME/.local/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
```

Create the log directory before loading:

```bash
mkdir -p ~/Library/Logs/akanga
```

### Step 2 — Validate the plist

```bash
plutil -lint ~/Library/LaunchAgents/com.akanga.server.plist
```

If this returns `OK`, the XML is well-formed. A parsing error here prevents
launchd from loading the service.

### Step 3 — Load the service

```bash
launchctl load ~/Library/LaunchAgents/com.akanga.server.plist
```

On macOS 11+, you may need:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.akanga.server.plist
```

### Step 4 — Check status

```bash
launchctl list | grep akanga
```

The output columns are `PID`, `exit status`, `label`. A PID in the first column
means the service is running. An exit status of `-1` means it has not run yet;
any other non-zero value is an error code — check the log files.

```bash
# Tail the log
tail -f ~/Library/Logs/akanga/server.log
tail -f ~/Library/Logs/akanga/server-error.log
```

### Management commands

```bash
# Stop (without unloading — launchd will restart it)
launchctl stop com.akanga.server

# Start manually (if stopped)
launchctl start com.akanga.server

# Unload permanently (survives reboot — service will not start at next login)
launchctl unload ~/Library/LaunchAgents/com.akanga.server.plist
# or on macOS 11+:
launchctl bootout gui/$(id -u)/com.akanga.server

# Reload after editing the plist
launchctl unload ~/Library/LaunchAgents/com.akanga.server.plist
launchctl load ~/Library/LaunchAgents/com.akanga.server.plist
```

### Common issues

**`uv` not found:** launchd runs with a minimal PATH. Use the full absolute path
to `uv` in `ProgramArguments`. Find it with `which uv` in your terminal.

**`WorkingDirectory` matters:** `uv run` resolves the virtual environment from
`pyproject.toml` in the working directory. If `WorkingDirectory` points to a
directory without `pyproject.toml`, uv will not find the venv.

**Port already in use:** If the server exits immediately and the log shows
`[Errno 48] Address already in use`, another process (or a previous akanga
instance) is on port 8000. Find it with `lsof -i :8000`.

---

## Option 3 — Linux systemd User Service

systemd user services run under your own user account — no root required. They
start when you log in (with `--user` flag) and are managed independently of
system-level services.

### Step 1 — Write the unit file

Create `~/.config/systemd/user/akanga.service`:

```ini
[Unit]
Description=Akanga knowledge graph server
After=network.target

[Service]
Type=simple

# Adjust these paths to match your setup:
WorkingDirectory=%h/code/akanga
ExecStart=%h/.local/bin/uv run python -m akanga_core.cli serve \
    --vault %h/vault \
    --db %h/.akanga.db \
    --host 127.0.0.1 \
    --port 8000

# Restart on crash, but not on clean exit (code 0)
Restart=on-failure
RestartSec=5s

# Environment
Environment=PATH=%h/.local/bin:/usr/local/bin:/usr/bin:/bin

# Log via journald (view with: journalctl --user -u akanga -f)
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=default.target
```

`%h` is a systemd specifier that expands to the home directory of the service
owner. It is equivalent to `$HOME` for user services.

### Step 2 — Enable and start

```bash
# Reload systemd after creating or editing the unit file
systemctl --user daemon-reload

# Enable: start automatically at login
systemctl --user enable akanga.service

# Start now (without waiting for next login)
systemctl --user start akanga.service
```

### Check status

```bash
systemctl --user status akanga.service
```

This shows the current state (active, failed, inactive), the PID, and the last
few lines of log output inline.

### View logs

```bash
# Follow live log output
journalctl --user -u akanga -f

# Show all logs since the last boot
journalctl --user -u akanga -b

# Show logs from the last hour
journalctl --user -u akanga --since "1 hour ago"
```

### Management commands

```bash
# Stop
systemctl --user stop akanga.service

# Restart
systemctl --user restart akanga.service

# Disable auto-start at login (does not stop the running service)
systemctl --user disable akanga.service

# Reload unit file after editing
systemctl --user daemon-reload
systemctl --user restart akanga.service
```

### Enabling lingering (keep service running after logout)

By default, systemd user services stop when the user logs out. To keep Akanga
running even when no session is active (e.g., on a headless machine or server):

```bash
loginctl enable-linger $USER
```

This is a system-level change that requires your user to have the appropriate
permissions. Verify with `loginctl show-user $USER | grep Linger`.

### Common issues

**`uv` not found:** Use the full path to `uv` (`%h/.local/bin/uv` is the default
install location from `curl -LsSf https://astral.sh/uv/install.sh | sh`). Confirm
with `which uv`.

**`WorkingDirectory` must exist:** The directory must exist when the service
starts. If it does not, systemd will fail with `chdir failed`.

**Port conflict:** If port 8000 is in use at login, systemd will restart the
service repeatedly (hitting `RestartSec=5s`). Add a longer `StartLimitBurst` or
change the port in `ExecStart`.

---

## Option 4 — Makefile Targets

For one-off manual starts from a terminal, the Makefile wraps all CLI commands
with sensible defaults. Place this at the root of your Akanga installation.

```makefile
# ──────────────────────────────────────────────────────────────
# Akanga — Makefile
# ──────────────────────────────────────────────────────────────

.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────
# Override any of these on the command line:
#   make serve VAULT=/path/to/vault PORT=9000

VAULT      ?= ./vault
DB         ?= ./.akanga.db
HOST       ?= 127.0.0.1
PORT       ?= 8000
LOG_LEVEL  ?= info
PYTHON     ?= uv run python
PYTHONPATH := src
export PYTHONPATH

# ── Phony targets ─────────────────────────────────────────────

.PHONY: help install serve tui index mcp-server \
        init-vault clean check test lint

# ── Help ──────────────────────────────────────────────────────

help: ## Show all available targets
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

# ── Install ───────────────────────────────────────────────────

install: ## Install dependencies with uv
	uv sync

# ── Runtime ───────────────────────────────────────────────────

serve: ## Start the REST API server (HOST=127.0.0.1 PORT=8000)
	$(PYTHON) -m akanga_core.cli serve \
		--vault $(VAULT) \
		--db $(DB) \
		--host $(HOST) \
		--port $(PORT)

serve-git: ## Start the server with git auto-commit enabled
	$(PYTHON) -m akanga_core.cli serve \
		--vault $(VAULT) \
		--db $(DB) \
		--host $(HOST) \
		--port $(PORT) \
		--git-init

tui: ## Start the Textual terminal UI
	$(PYTHON) -m akanga_core.cli tui \
		--vault $(VAULT) \
		--db $(DB)

index: ## Re-index the vault (run after manual file edits)
	$(PYTHON) -m akanga_core.cli index \
		--vault $(VAULT) \
		--db $(DB)

mcp-server: ## Start the MCP server (Phase 8)
	$(PYTHON) -m akanga_core.cli mcp \
		--vault $(VAULT) \
		--db $(DB)

# ── Vault setup ───────────────────────────────────────────────

init-vault: ## Create ./vault with sample notes
	@mkdir -p $(VAULT)
	@printf '%s\n' \
		'---' \
		'title: Welcome to Akanga' \
		'type: note' \
		'tags: [welcome, getting-started]' \
		'---' \
		'' \
		'Your vault is ready.' \
		> $(VAULT)/welcome.md
	@echo "Created $(VAULT)/welcome.md"

# ── Development ───────────────────────────────────────────────

test: ## Run all tests
	PYTHONPATH=src pytest -v

lint: ## Run ruff linter
	ruff check src/ tests/

check: lint test ## Run lint + tests (CI equivalent)

clean: ## Remove caches and runtime artifacts
	find . -type f -name '*.pyc' -delete
	find . -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name '.pytest_cache' -exec rm -rf {} + 2>/dev/null || true
	rm -f *.db *.db-wal *.db-shm
```

**Usage examples:**

```bash
# Start with defaults (vault=./vault, port=8000)
make serve

# Start with a custom vault and port
make serve VAULT=/Users/arthur/notes PORT=9000

# Start with git auto-commit enabled
make serve-git VAULT=/Users/arthur/notes

# Re-index after manually editing files outside Akanga
make index VAULT=/Users/arthur/notes

# Start the TUI pointing at a different vault
make tui VAULT=/Users/arthur/archive
```

---

## Checking the Server is Running

Regardless of how you started Akanga, these commands confirm it is up:

```bash
# Quick health check — should return HTTP 200
curl -s http://127.0.0.1:8000/api/v1/nodes | head -c 200

# List nodes
curl -s http://127.0.0.1:8000/api/v1/nodes | python3 -m json.tool

# Check which process is on the port
lsof -i :8000        # macOS / Linux
```

The API documentation is always available at `http://127.0.0.1:8000/docs` while
the server is running.

---

## Security Notes for Deployment

These apply regardless of which deployment method you use.

**Keep the default host binding.** The server binds to `127.0.0.1` by default.
Do not change this to `0.0.0.0` unless you understand the implications — see the
CORS and binding discussion in Phase 6.

**The vault directory is the attack surface.** Akanga has no authentication.
Anyone who can reach the server port can read and write your vault. Keep the port
inaccessible from untrusted networks (the `127.0.0.1` default ensures this for
local deployments).

**The DB file is not backed up by git.** `.akanga.db` is in `.gitignore` by design
— it is a derived index and can be rebuilt at any time with `akanga index`.
Your vault Markdown files are what git tracks. Make sure your vault is in a git
repository if you want version history and backup.

**Log files may contain vault content.** If FastAPI logs request bodies (debug
mode), the log files will contain the content of every node create and update
request. Keep log file permissions restrictive (`chmod 600`) and rotate them.
The launchd and systemd configurations above write logs to user-private locations.
