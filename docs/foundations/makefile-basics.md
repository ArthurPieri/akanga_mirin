# Makefile Basics

**Audience:** anyone who can open a terminal — no prior make experience · **Read time:** ~15 min

---

Make is a tool from 1976 that most developers think of as "that C build system."
That reputation is accurate but incomplete. Make is equally good as a command
runner: a single file that turns long, hard-to-remember shell commands into short,
consistent names you never have to look up.

In the Akanga learning path, the Makefile is the primary interface. Instead of
remembering `AKANGA_SRC=./src uv run pytest tests/phase_02/ -v`, you type
`make test PHASE=2`. This doc explains how that works.

---

## 1. What a Makefile is

A Makefile is a text file named `Makefile` (capital M, no extension) that lives in
your project directory. When you run `make` in that directory, it reads the file and
executes the instructions you ask for.

The mental model that matters: **Make is a dictionary from names to shell commands.**
The name is a "target." The shell commands are the "recipe." That's the whole idea.

```
$ make help       ← runs the recipe for the "help" target
$ make test       ← runs the recipe for the "test" target
$ make test PHASE=2  ← runs "test" with a variable set
```

Make was originally designed to rebuild C programs only when their source files
changed — which is why it is called "make" and why it talks about targets and
dependencies. For a command runner like Akanga's Makefile, that file-tracking
feature is mostly irrelevant. You need to know it exists (and how to turn it off
for action targets) but you won't use it much.

---

## 2. Makefile anatomy

A Makefile is made of **rules**. Each rule has three parts:

```
target: prerequisites
	recipe line 1
	recipe line 2
```

- **target** — the name you call with `make target`. Often a filename in build
  systems; in a command runner it is almost always a short action name.
- **prerequisites** — zero or more other targets that must run before this one.
  Often empty for action targets.
- **recipe** — one or more shell commands. Each line runs in its own subshell.
  **Must be indented with a tab character, not spaces.** This is Make's most
  notorious quirk.

A minimal, complete Makefile:

```makefile
hello:
	echo "Hello from Make"

greet: hello
	echo "This runs after hello"
```

Running:

```
$ make hello
echo "Hello from Make"
Hello from Make

$ make greet
echo "Hello from Make"
Hello from Make
echo "This runs after greet"
This runs after greet
```

Make echoes each command before running it. Prefix a command with `@` to silence
the echo:

```makefile
hello:
	@echo "Hello from Make"
```

Now `make hello` prints only:

```
Hello from Make
```

---

## 3. .PHONY — the most important Makefile line

If a file named `hello` exists in your directory, `make hello` will see it and say
"target is up to date — nothing to do." This breaks every action target.

The fix is `.PHONY`. Declare every action target as phony and Make will always run
its recipe, regardless of whether a file with that name exists:

```makefile
.PHONY: hello greet

hello:
	@echo "Hello from Make"

greet: hello
	@echo "This runs after hello"
```

**Rule:** every target that is an action (not a real file) must be in `.PHONY`.
In the Akanga Makefile, that is every target: `test`, `help`, `setup`, `lint`, etc.

---

## 4. Variables

Variables hold values you want to reuse or allow callers to override.

```makefile
# Simple assignment — evaluated once when Make reads the file
NAME := Arthur

# Lazy assignment — evaluated each time the variable is used
GREETING = Hello, $(NAME)!

# Default — only set if not already defined
PHASE ?= 0
```

Reference a variable with `$(VARIABLE_NAME)`:

```makefile
.PHONY: greet
greet:
	@echo "$(GREETING)"
```

### Overriding from the command line

Any variable can be overridden at the command line:

```
$ make greet NAME=Alice
Hello, Alice!
```

This is how `make test PHASE=2` works. `PHASE` is declared with `?= 0` (default 0),
and `PHASE=2` on the command line overrides it for that run only.

### Shell expansion in variables

Use `:=` with `$(shell ...)` to capture shell output into a variable:

```makefile
PHASE_PAD := $(shell printf "%02d" $(PHASE))
```

Now `PHASE_PAD` is always a zero-padded two-digit string: `PHASE=3` → `PHASE_PAD=03`.

---

## 5. .DEFAULT_GOAL

Without instructions, `make` runs the first target in the file. `.DEFAULT_GOAL`
makes this explicit and readable:

```makefile
.DEFAULT_GOAL := help
```

Now `make` (no arguments) runs the `help` target. This is how `make help` becomes
the front door: the learner types `make` and immediately sees all available commands.

---

## 6. The self-documenting help target

The Akanga Makefile's `help` target generates its output from `##` comments written
directly on each target declaration:

```makefile
test: ## Run tests for one phase against AKANGA_SRC (PHASE=2)
	@...
```

The `help` recipe uses `grep` and `awk` to extract these comments and format them:

```makefile
help:
	@grep -E '^[a-zA-Z_-]+:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'
```

`$(MAKEFILE_LIST)` is a Make built-in that lists all Makefile files being read.
The `grep` finds lines of the form `target: ## comment`. The `awk` splits on `##`
and formats the target name (field 1) and comment (field 2) into two columns.
The `\033[36m` and `\033[0m` are ANSI escape codes for cyan text and reset.

**The benefit:** the comment and the recipe are on the same line, so they stay in
sync automatically. There is no separate documentation map to maintain.

---

## 7. Automatic variables

Inside a recipe, Make provides automatic variables that refer to parts of the rule:

| Variable | Meaning |
|---|---|
| `$@` | The name of the target |
| `$<` | The first prerequisite |
| `$^` | All prerequisites (space-separated) |
| `$*` | The stem of a pattern rule match |

For a command-runner Makefile like Akanga's, these appear rarely. You mainly see
them in recipes that involve file names. Example:

```makefile
%.o: %.c
	cc -c $< -o $@
```

This pattern rule compiles any `.c` file into a `.o` file. `$<` is the `.c` input,
`$@` is the `.o` output. You do not need to write pattern rules in Akanga's Makefile,
but you will see them in C projects that use Make as a build system.

---

## 8. Pattern rules

A pattern rule uses `%` as a wildcard. It lets one rule handle many targets:

```makefile
%.html: %.md
	pandoc $< -o $@
```

This converts any `.md` file to `.html`. Run `make notes.html` and Make looks for
`notes.md`, then runs `pandoc notes.md -o notes.html`.

In the Akanga Makefile, targets are explicit (not pattern-matched) because the
action names do not map directly to filenames.

---

## 9. Common pitfalls

**Tabs, not spaces.** Makefile recipes must start with a real tab character. Most
editors use spaces by default. The error `Makefile:5: *** missing separator` means
you have spaces where Make expects a tab. Configure your editor to use tabs in
Makefile files:

- **Neovim:** `autocmd FileType make setlocal noexpandtab`
- **VS Code:** Set "Editor: Insert Spaces" to false for Makefile file type

**Each recipe line runs in its own subshell.** Variables set in one line are not
visible in the next. If you need multi-step shell logic, either join lines with `\`
or use a single shell invocation:

```makefile
# These run in separate subshells — cd has no effect on the second line
wrong:
	cd /tmp
	ls          # still lists the original directory

# Use && to chain commands in one subshell
right:
	cd /tmp && ls

# Or use \ to continue the recipe on the next line (one subshell)
also-right:
	cd /tmp \
	&& ls
```

**Forgetting .PHONY.** If `make test` stops working because a file named `test`
appeared in your directory, you forgot `.PHONY: test`. Always declare action targets
as phony up front.

**Quoting shell variables in recipes.** Make expands `$(VAR)` before the shell sees
the recipe. To use a shell variable inside a recipe, use `$$VAR` (double dollar sign
— Make passes it to the shell as a literal `$VAR`):

```makefile
test:
	@for n in 1 2 3; do \
		echo "Phase $$n"; \    # $$ → shell variable $n
	done
```

---

## 10. A working 20-line example

Copy this into an empty directory, name it `Makefile`, and run `make`:

```makefile
.DEFAULT_GOAL := help
.PHONY: help greet count clean

NAME  ?= World
COUNT ?= 3

help:
	@echo "Targets: greet, count, clean"
	@echo "Variables: NAME=$(NAME) COUNT=$(COUNT)"

greet: ## Say hello to NAME
	@echo "Hello, $(NAME)!"

count: ## Count from 1 to COUNT
	@for n in $$(seq 1 $(COUNT)); do \
		echo "  $$n"; \
	done

clean: ## Remove any temp files
	@rm -f *.tmp
	@echo "Cleaned."
```

Try:

```
$ make
Targets: greet, count, clean
Variables: NAME=World COUNT=3

$ make greet
Hello, World!

$ make greet NAME=Alice
Hello, Alice!

$ make count COUNT=5
  1
  2
  3
  4
  5

$ make clean
Cleaned.
```

Notice:
- `.DEFAULT_GOAL := help` makes `make` (no args) show the help.
- `.PHONY` lists every action target.
- `NAME ?= World` sets a default that `NAME=Alice` overrides.
- `$$(seq ...)` uses `$$` to pass `$(seq ...)` to the shell without Make expanding it.
- `$$n` is the shell variable `$n` inside the loop.
- `@` on each recipe line suppresses the command echo, showing only output.

That is everything you need to read and write the Akanga Mirin Makefile.

---

## Next steps

- Run `make help` in the akanga_mirin repo to see the learning path's full target list.
- Read the `Makefile` source: the structure will be immediately recognizable after
  this doc.
- For deeper reference: `man make` or the GNU Make manual at
  `https://www.gnu.org/software/make/manual/make.html`.
