# Implementation Plan — Makefile Strategy

> **Status:** Pre-implementation. Derived from `analysis-and-enhancements.md` decisions.
> This document covers the complete Makefile strategy for the akanga_mirin learning
> repository: root Makefile, learner project Makefile template, foundations doc, and
> per-phase integration guidance.

---

## Philosophy

The Makefile is the primary interface to this repository. A learner should never need
to remember a raw `pytest` invocation, a raw `glow` command, or a `uv run` flag
sequence. Every workflow — study, test, verify, example, skeleton, lint — is a single
`make <target>` call.

**Three design rules:**

1. **`make help` is the front door.** Every learner runs it first. It must be welcoming,
   organized, and show the most important targets immediately.
2. **Defaults are safe and sensible.** `make test` without arguments tests phase 00.
   `make study` opens phase 00. No target requires arguments to produce a useful
   non-error result.
3. **Facilitators and learners share one Makefile.** Facilitator targets (verify,
   commit-progress, push) are present but grouped separately in the help output. They
   do not clutter the learner view.

---

## Part 1 — Root Makefile (akanga_mirin/)

This Makefile lives at the root of the learning repository. It is the single interface
for every workflow: study, test, example, skeleton, verify, lint, setup, and git.

```makefile
# =============================================================================
# Akanga Mirin — Learning Repository Makefile
# =============================================================================
#
# Usage:  make <target> [PHASE=N] [FROM=N] [TO=N] [TOPIC=name]
#
# Run 'make help' to see all available targets.
#
# Environment:
#   AKANGA_SRC   Path to the learner's own src/ directory (default: ./src)
#   AKANGA_DOCS  Path to this repo's docs/ (default: ./docs — auto-detected)
#   AKANGA_CODE  Code directory opened in the study session (default: ./src)

.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────────────────────

PHASE        ?= 0
PHASE_PAD    := $(shell printf "%02d" $(PHASE))

FROM         ?= 0
TO           ?= 8

TOPIC        ?=

AKANGA_SRC   ?= ./src
AKANGA_DOCS  ?= $(shell pwd)/docs
AKANGA_CODE  ?= $(shell pwd)/src

PYTHON       := uv run python
PYTEST       := uv run pytest
RUFF         := uv run ruff
MYPY         := uv run mypy
GLOW         := glow

# ── .PHONY declarations ────────────────────────────────────────────────────────

.PHONY: help \
        study docs-phase docs-all foundations \
        test test-solution test-all test-mine test-phase-range \
        verify verify-all \
        example examples-all \
        skeleton skeleton-check \
        setup setup-phase \
        lint typecheck check \
        commit-progress push

# =============================================================================
# HELP — self-documenting target (reads ## comments)
# =============================================================================

help: ## Show this help message
	@printf '\n'
	@printf '  \033[1;36mAkanga Mirin — Learning Repository\033[0m\n'
	@printf '  Build a personal knowledge graph, phase by phase.\n'
	@printf '\n'
	@printf '  \033[1;33mStudy workflow\033[0m\n'
	@grep -E '^(study|docs-phase|docs-all|foundations)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mTesting workflow\033[0m\n'
	@grep -E '^(test|test-solution|test-all|test-mine|test-phase-range)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mExamples workflow\033[0m\n'
	@grep -E '^(example|examples-all)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mSkeleton workflow\033[0m\n'
	@grep -E '^(skeleton|skeleton-check)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mSetup workflow\033[0m\n'
	@grep -E '^(setup|setup-phase)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mQuality workflow\033[0m\n'
	@grep -E '^(lint|typecheck|check)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mFacilitator workflow\033[0m\n'
	@grep -E '^(verify|verify-all|commit-progress|push)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[2mVariables: PHASE=N (default 0)  FROM=N  TO=N  TOPIC=name\033[0m\n'
	@printf '\n'

# =============================================================================
# STUDY — open tmux layout for a phase
# =============================================================================

study: ## Open tmux study session (PHASE=2 → phase 02)
	@AKANGA_DOCS="$(AKANGA_DOCS)" AKANGA_CODE="$(AKANGA_CODE)" \
		bash scripts/study.sh $(PHASE)

docs-phase: ## Open phase doc in glow (PHASE=3 → phase 03 doc)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${PHASE_PAD}-*.md" 2>/dev/null | head -1); \
	if [ -z "$$DOC" ]; then \
		echo "error: no doc found for phase $${PHASE_PAD}"; exit 1; \
	fi; \
	$(GLOW) -p "$$DOC"

docs-all: ## Open all phase docs in glow sequentially (review mode)
	@for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${PHASE_PAD}-*.md" 2>/dev/null | head -1); \
		if [ -n "$$DOC" ]; then \
			echo "\n── Phase $${PHASE_PAD} ──────────────────────────────────────────"; \
			$(GLOW) -p "$$DOC"; \
		fi; \
	done

foundations: ## Open a foundations doc in glow (TOPIC=sqlite → sqlite-basics.md)
	@if [ -z "$(TOPIC)" ]; then \
		echo "Usage: make foundations TOPIC=sqlite"; \
		ls docs/foundations/ 2>/dev/null | sed 's/\.md$$//' | sort; \
		exit 0; \
	fi; \
	DOC="$(AKANGA_DOCS)/foundations/$(TOPIC).md"; \
	if [ ! -f "$$DOC" ]; then \
		DOC=$$(find "$(AKANGA_DOCS)/foundations" -name "*$(TOPIC)*" 2>/dev/null | head -1); \
	fi; \
	if [ -z "$$DOC" ] || [ ! -f "$$DOC" ]; then \
		echo "error: no foundations doc matching '$(TOPIC)'"; exit 1; \
	fi; \
	$(GLOW) -p "$$DOC"

# =============================================================================
# TESTING — run tests against learner's code or solutions
# =============================================================================

test: ## Run tests for one phase against AKANGA_SRC (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	echo "Testing phase $${PHASE_PAD} against $(AKANGA_SRC) ..."; \
	AKANGA_SRC="$(AKANGA_SRC)" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v

test-solution: ## Run tests for one phase against reference solution (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SOLUTION_SRC" ]; then \
		echo "error: no solution found at $$SOLUTION_SRC"; exit 1; \
	fi; \
	echo "Testing phase $${PHASE_PAD} against solution ..."; \
	AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v

test-all: ## Run all phases against their solutions (full suite verification)
	@echo "Running full test suite against solutions ..."; \
	FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ -d "$$SOLUTION_SRC" ] && [ -d "tests/phase_$${PHASE_PAD}" ]; then \
			echo "\n── Phase $${PHASE_PAD} ──"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		echo "\n$${FAILED} phase(s) failed"; exit 1; \
	else \
		echo "\nAll phases passed."; \
	fi

test-mine: ## Run all tests against AKANGA_SRC (learner's own code)
	@echo "Testing all phases against $(AKANGA_SRC) ..."; \
	AKANGA_SRC="$(AKANGA_SRC)" $(PYTEST) tests/ -v

test-phase-range: ## Run phases FROM..TO against solutions (FROM=0 TO=3)
	@echo "Testing phases $(FROM)–$(TO) against solutions ..."; \
	FAILED=0; \
	for n in $$(seq $(FROM) $(TO)); do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ -d "$$SOLUTION_SRC" ] && [ -d "tests/phase_$${PHASE_PAD}" ]; then \
			echo "\n── Phase $${PHASE_PAD} ──"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		echo "\n$${FAILED} phase(s) failed"; exit 1; \
	fi

# =============================================================================
# VERIFICATION — cumulative solution checks (facilitator)
# =============================================================================

verify: ## Verify solution N passes tests 00..N cumulatively (PHASE=3)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SOLUTION_SRC" ]; then \
		echo "error: no solution at $$SOLUTION_SRC"; exit 1; \
	fi; \
	echo "Verifying phase $${PHASE_PAD} solution against phases 00..$${PHASE_PAD} ..."; \
	FAILED=0; \
	for n in $$(seq 0 $(PHASE)); do \
		N_PAD=$$(printf "%02d" $$n); \
		if [ -d "tests/phase_$${N_PAD}" ]; then \
			echo "  → testing phase $${N_PAD}"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${N_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		echo "\nFailed: phase $${PHASE_PAD} solution is not cumulative"; exit 1; \
	else \
		echo "\nPhase $${PHASE_PAD} solution is cumulative — all prior tests pass."; \
	fi

verify-all: ## Verify all 9 phases are cumulative (facilitator, slow)
	@echo "Verifying cumulative correctness for all phases ..."; \
	FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ ! -d "$$SOLUTION_SRC" ]; then continue; fi; \
		echo "\n── Verifying phase $${PHASE_PAD} (cumulative 00..$${PHASE_PAD}) ──"; \
		for m in $$(seq 0 $$n); do \
			M_PAD=$$(printf "%02d" $$m); \
			if [ -d "tests/phase_$${M_PAD}" ]; then \
				AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${M_PAD}/ -q \
					|| FAILED=$$((FAILED+1)); \
			fi; \
		done; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		echo "\n$${FAILED} cumulative check(s) failed"; exit 1; \
	else \
		echo "\nAll phases cumulative — full verification passed."; \
	fi

# =============================================================================
# EXAMPLES — standalone concept demo scripts
# =============================================================================

example: ## Run the example script for a phase (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SCRIPT=$$(find examples -name "phase_$${PHASE_PAD}_*.py" 2>/dev/null | head -1); \
	if [ -z "$$SCRIPT" ]; then \
		echo "error: no example script found for phase $${PHASE_PAD} in examples/"; exit 1; \
	fi; \
	echo "Running $$SCRIPT ..."; \
	$(PYTHON) "$$SCRIPT"

examples-all: ## Run all 9 example scripts sequentially
	@FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SCRIPT=$$(find examples -name "phase_$${PHASE_PAD}_*.py" 2>/dev/null | head -1); \
		if [ -n "$$SCRIPT" ]; then \
			echo "\n── Phase $${PHASE_PAD}: $$SCRIPT ──"; \
			$(PYTHON) "$$SCRIPT" || FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		echo "\n$${FAILED} example(s) failed"; exit 1; \
	fi

# =============================================================================
# SKELETON — set up or check learner's starting point
# =============================================================================

skeleton: ## Copy skeleton for a phase into ./src/ (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SKEL="skeletons/phase_$${PHASE_PAD}"; \
	if [ ! -d "$$SKEL" ]; then \
		echo "error: no skeleton found at $$SKEL"; exit 1; \
	fi; \
	echo "Copying skeleton for phase $${PHASE_PAD} → ./src/ ..."; \
	mkdir -p src; \
	cp -r "$$SKEL/src/." src/; \
	echo "Done. Edit src/ to complete the implementation."; \
	echo "Run: make test PHASE=$(PHASE)"

skeleton-check: ## Verify skeleton still raises NotImplementedError (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SKEL="skeletons/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SKEL" ]; then \
		echo "error: no skeleton found at $$SKEL"; exit 1; \
	fi; \
	echo "Checking skeleton for phase $${PHASE_PAD} — all methods must raise NotImplementedError ..."; \
	$(PYTHON) - <<'PYEOF'
import ast, sys, pathlib
phase = "$(PHASE_PAD)"
skel = pathlib.Path("skeletons/phase_" + phase + "/src")
errors = []
for py in skel.rglob("*.py"):
    tree = ast.parse(py.read_text())
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            # Skip functions whose body is only docstring + raise NotImplementedError
            stmts = [s for s in body if not isinstance(s, ast.Expr) or not isinstance(s.value, ast.Constant)]
            if stmts:
                # Check if any statement is a raise NotImplementedError
                has_not_impl = any(
                    isinstance(s, ast.Raise)
                    and isinstance(getattr(s.exc, 'func', None), ast.Name)
                    and s.exc.func.id == 'NotImplementedError'
                    for s in body
                )
                if not has_not_impl and node.name not in ('__init__', '__repr__', '__str__'):
                    errors.append(f"{py}:{node.lineno}: {node.name}() has implementation — possible solution leakage")
if errors:
    print("FAIL — skeleton contains implemented methods:")
    for e in errors:
        print("  ", e)
    sys.exit(1)
else:
    print("OK — all stub methods raise NotImplementedError")
PYEOF

# =============================================================================
# SETUP — dependency installation
# =============================================================================

setup: ## Install all dependencies for the full learning path
	@echo "Installing all dependencies ..."; \
	uv sync --all-extras; \
	echo "Done. Run 'make test PHASE=0' to verify."

setup-phase: ## Install dependencies needed through a given phase (PHASE=2)
	@echo "Installing dependencies for phases 0–$(PHASE) ..."; \
	uv sync; \
	echo "Done."

# =============================================================================
# QUALITY — lint, typecheck, and full check
# =============================================================================

lint: ## Lint all Python files in tests/ skeletons/ solutions/ examples/
	@$(RUFF) check tests/ skeletons/ solutions/ examples/ src/ 2>/dev/null || \
		$(RUFF) check tests/ skeletons/ solutions/ examples/

typecheck: ## Run mypy on solutions/phase_NN/src/ (PHASE=3)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SRC" ]; then \
		echo "error: no solution at $$SRC"; exit 1; \
	fi; \
	$(MYPY) "$$SRC"

check: lint test-all ## Run lint + typecheck + test-all (full quality gate)
	@echo "\nAll checks passed."

# =============================================================================
# GIT — facilitator workflow
# =============================================================================

commit-progress: ## Auto-commit with message 'progress: phase N tests passing'
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	MSG="progress: phase $${PHASE_PAD} tests passing"; \
	git add tests/ solutions/ skeletons/ examples/ docs/ scripts/ Makefile; \
	git commit -m "$$MSG"; \
	echo "Committed: $$MSG"

push: ## Push to remote (prompts for confirmation)
	@read -p "Push to remote? [y/N] " CONFIRM; \
	if [ "$$CONFIRM" = "y" ] || [ "$$CONFIRM" = "Y" ]; then \
		git push; \
	else \
		echo "Aborted."; \
	fi
```

---

## Part 2 — Learner's Project Makefile Template

This Makefile lives in the learner's own project directory (their Akanga
implementation). Copy it into their repo root. It assumes `uv` and `PYTHONPATH=src`.

```makefile
# =============================================================================
# Akanga — Your Implementation Makefile
# =============================================================================
#
# Copy this file to the root of your own Akanga project.
# Set MIRIN to the path of the akanga_mirin learning repo.
#
# Usage: make <target> [PHASE=N]

.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────────────────────

PHASE    ?= 0
PHASE_PAD := $(shell printf "%02d" $(PHASE))

# Path to the akanga_mirin learning repo (where tests/ lives)
MIRIN    ?= $(HOME)/code/akanga_mirin

VAULT    ?= ./vault
DB       ?= ./.akanga.db
HOST     ?= 127.0.0.1
PORT     ?= 8000

PYTHON   := uv run python
PYTEST   := uv run pytest
RUFF     := uv run ruff

.PHONY: help test run serve index init-vault mcp clean lint setup

# =============================================================================
# HELP
# =============================================================================

help:
	@printf '\n'
	@printf '  \033[1;36mAkanga — Your Implementation\033[0m\n'
	@printf '\n'
	@printf '  \033[1;33mLearning workflow\033[0m\n'
	@printf '    \033[36m%-26s\033[0m %s\n' "make test PHASE=2" "Run phase 02 tests against your src/"
	@printf '    \033[36m%-26s\033[0m %s\n' "make test" "Run phase 00 tests (default)"
	@printf '\n'
	@printf '  \033[1;33mRuntime workflow\033[0m\n'
	@printf '    \033[36m%-26s\033[0m %s\n' "make run" "Start the Textual TUI"
	@printf '    \033[36m%-26s\033[0m %s\n' "make serve" "Start the REST API server"
	@printf '    \033[36m%-26s\033[0m %s\n' "make index" "Re-index the vault"
	@printf '    \033[36m%-26s\033[0m %s\n' "make mcp" "Start the MCP server"
	@printf '\n'
	@printf '  \033[1;33mSetup workflow\033[0m\n'
	@printf '    \033[36m%-26s\033[0m %s\n' "make init-vault" "Create vault/ and akanga.yaml"
	@printf '    \033[36m%-26s\033[0m %s\n' "make setup" "Install project dependencies"
	@printf '\n'
	@printf '  \033[1;33mQuality workflow\033[0m\n'
	@printf '    \033[36m%-26s\033[0m %s\n' "make lint" "Lint src/ with ruff"
	@printf '    \033[36m%-26s\033[0m %s\n' "make clean" "Remove .akanga.db and __pycache__"
	@printf '\n'
	@printf '  \033[2mSet MIRIN to override path to akanga_mirin: make test PHASE=2 MIRIN=~/code/akanga_mirin\033[0m\n'
	@printf '\n'

# =============================================================================
# LEARNING
# =============================================================================

test: ## Run phase tests against your src/
	@if [ ! -d "$(MIRIN)/tests/phase_$(PHASE_PAD)" ]; then \
		echo "error: tests not found at $(MIRIN)/tests/phase_$(PHASE_PAD)"; \
		echo "Set MIRIN to the path of the akanga_mirin repo."; \
		exit 1; \
	fi; \
	echo "Testing phase $(PHASE_PAD) against ./src/ ..."; \
	AKANGA_SRC=./src $(PYTEST) "$(MIRIN)/tests/phase_$(PHASE_PAD)/" -v

# =============================================================================
# RUNTIME
# =============================================================================

run: ## Start the Textual TUI
	$(PYTHON) -m akanga_core.cli tui --vault $(VAULT) --db $(DB)

serve: ## Start the REST API server
	$(PYTHON) -m akanga_core.cli serve \
		--vault $(VAULT) --db $(DB) \
		--host $(HOST) --port $(PORT)

index: ## Re-index the vault
	$(PYTHON) -m akanga_core.cli index --vault $(VAULT) --db $(DB)

mcp: ## Start the MCP server
	$(PYTHON) -m akanga_core.cli mcp-server --vault $(VAULT) --db $(DB)

init-vault: ## Create vault/ directory and akanga.yaml config
	@mkdir -p $(VAULT)
	@if [ ! -f "$(VAULT)/akanga.yaml" ]; then \
		printf 'vault:\n  path: $(VAULT)\ngit:\n  enabled: false\n  auto_push: false\n' \
			> $(VAULT)/akanga.yaml; \
		echo "Created $(VAULT)/akanga.yaml"; \
	else \
		echo "$(VAULT)/akanga.yaml already exists — skipping."; \
	fi
	@echo "Vault ready at $(VAULT)/"

# =============================================================================
# QUALITY
# =============================================================================

lint: ## Lint src/ with ruff
	$(RUFF) check src/

clean: ## Remove .akanga.db, __pycache__, .coverage
	@rm -f $(DB) $(DB)-wal $(DB)-shm .coverage
	@find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned."

# =============================================================================
# SETUP
# =============================================================================

setup: ## Install project dependencies
	uv sync
	@echo "Done. Run 'make init-vault' then 'make run'."
```

---

## Part 3 — docs/foundations/makefile-basics.md

This is the complete foundations document for Make. It is written for Python developers
who have never written a Makefile, teaches Make as a command runner (not a build system),
and ends with a working 20-line example the learner can run immediately.

The full file is created at `docs/foundations/makefile-basics.md` by task MF-4.

**Document outline:**

1. What Make is and why developers use it (not just for C — it is a self-documenting
   command runner that any project can adopt)
2. Makefile anatomy: target, prerequisites, recipe — with a minimal two-target example
3. `.PHONY`: why every "action" target needs it; what happens without it
4. Variables: simple assignment (`:=`), lazy assignment (`=`), command-line override
   (`make test PHASE=2`), defaults with `?=`
5. The `.DEFAULT_GOAL` special variable
6. Automatic variables (`$@`, `$<`, `$^`) — where they appear in Akanga's Makefile
7. Pattern rules — brief, with a `%.o: %.c` example for context
8. Silent recipes with `@` — why the help target uses `@printf`
9. The `##`-comment help pattern — how the Akanga Makefile generates its help output
10. Common pitfalls: tabs not spaces, running phony targets as real files, forgetting
    to quote shell variables in recipes
11. A complete standalone 20-line Makefile the learner can copy and run immediately

---

## Part 4 — Makefile Integration Throughout the Learning Path

### Which targets to highlight per phase

Each phase doc should include a "Makefile quick reference" box — a three-line callout
at the top (below the time estimate) showing exactly what to run. No phase should
require a learner to look up the target name.

| Phase | Primary targets | New targets introduced |
|---|---|---|
| 0 | `make setup`, `make skeleton PHASE=0`, `make test PHASE=0` | `setup`, `skeleton`, `test` |
| 1 | `make test PHASE=1`, `make test-solution PHASE=1` | `test-solution` |
| 2 | `make test PHASE=2`, `make example PHASE=2` | `example` |
| 3 | `make test PHASE=3`, `make example PHASE=3` | — |
| 4 | `make test PHASE=4`, `make skeleton-check PHASE=4` | `skeleton-check` |
| 5 | `make test PHASE=5`, `make test-phase-range FROM=0 TO=5` | `test-phase-range` |
| 6 | `make test PHASE=6`, `make verify PHASE=6` | `verify` |
| 7 | `make test PHASE=7`, `make commit-progress PHASE=7` | `commit-progress` |
| 8 | `make test PHASE=8`, `make verify-all`, `make check` | `verify-all`, `check` |

**Recommendation on where to teach Make itself:** The `foundations/makefile-basics.md`
doc is the right home for the conceptual explanation. Phase 0 links to it with:
"If you've never used Make before, read `docs/foundations/makefile-basics.md` — it
takes about 20 minutes." The concept is not woven into any phase doc because it is
not specific to Akanga; it is general infrastructure knowledge that any learner may
already have.

**Callout box format for each phase doc** (insert below the time estimate line):

```markdown
> **Quick start:**
> ```
> make skeleton PHASE=0      # copy starting stubs into ./src/
> make test PHASE=0          # run the tests (they will fail — that's correct)
> make test-solution PHASE=0 # see what passing looks like
> ```
```

Phases 1–8 repeat this pattern with the appropriate phase number and replace
`make skeleton` with `make example PHASE=N` once examples exist.

---

## Part 5 — Self-Documenting Help Target

The `make help` output is the first thing every new learner sees. It uses ANSI color
codes and a `printf`-based layout (not `echo`, which is not portable) organized into
workflow groups.

### Expected output

```
  Akanga Mirin — Learning Repository
  Build a personal knowledge graph, phase by phase.

  Study workflow
    study                        Open tmux study session (PHASE=2 → phase 02)
    docs-phase                   Open phase doc in glow (PHASE=3 → phase 03 doc)
    docs-all                     Open all phase docs in glow sequentially (review mode)
    foundations                  Open a foundations doc in glow (TOPIC=sqlite → sqlite-basics.md)

  Testing workflow
    test                         Run tests for one phase against AKANGA_SRC (PHASE=2)
    test-solution                Run tests for one phase against reference solution (PHASE=2)
    test-all                     Run all phases against their solutions (full suite verification)
    test-mine                    Run all tests against AKANGA_SRC (learner's own code)
    test-phase-range             Run phases FROM..TO against solutions (FROM=0 TO=3)

  Examples workflow
    example                      Run the example script for a phase (PHASE=2)
    examples-all                 Run all 9 example scripts sequentially

  Skeleton workflow
    skeleton                     Copy skeleton for a phase into ./src/ (PHASE=2)
    skeleton-check               Verify skeleton still raises NotImplementedError (PHASE=2)

  Setup workflow
    setup                        Install all dependencies for the full learning path
    setup-phase                  Install dependencies needed through a given phase (PHASE=2)

  Quality workflow
    lint                         Lint all Python files in tests/ skeletons/ solutions/ examples/
    typecheck                    Run mypy on solutions/phase_NN/src/ (PHASE=3)
    check                        Run lint + typecheck + test-all (full quality gate)

  Facilitator workflow
    verify                       Verify solution N passes tests 00..N cumulatively (PHASE=3)
    verify-all                   Verify all 9 phases are cumulative (facilitator, slow)
    commit-progress              Auto-commit with message 'progress: phase N tests passing'
    push                         Push to remote (prompts for confirmation)

  Variables: PHASE=N (default 0)  FROM=N  TO=N  TOPIC=name
```

The help target generates this from `##` comments on each target line. The `grep`/`awk`
pipeline reads only the comment on the target declaration line — no separate help map
to maintain.

---

## Part 6 — Task List

Tasks are in dependency order. All MF-1, MF-2, MF-3 can be parallelized. MF-4
through MF-7 depend on MF-1 existing (so the phase doc additions reference real
targets). MF-8 depends on all.

---

### MF-1 — Create root Makefile

**File:** `akanga_mirin/Makefile`
**Depends on:** nothing
**Effort:** 2 hours
**Who:** any contributor

Copy the Makefile from Part 1 of this document into the repo root. Verify:

- `make help` displays correctly with color groups
- `make setup` installs dependencies without error
- `make test PHASE=0` produces a meaningful error (no tests yet) rather than silent
  failure
- `make skeleton PHASE=0` fails gracefully when `skeletons/phase_00/` doesn't exist

**Acceptance criteria:**
- `make help` renders without error on macOS zsh and bash.
- All `.PHONY` declarations are present.
- PHASE defaults to 0 when not provided (`make test` runs phase 00, not phase 0).
- `make check` is callable even before solutions exist (exits non-zero, does not crash).
- Tabs are used for recipe indentation throughout (not spaces).

---

### MF-2 — Create learner's project Makefile template

**File:** `akanga_mirin/templates/project-makefile` (no `.mk` extension — learners
copy it as `Makefile`)
**Depends on:** nothing
**Effort:** 45 minutes
**Who:** any contributor

Copy the Makefile from Part 2 into `templates/project-makefile`. Add a header comment
explaining how to use it: `cp templates/project-makefile Makefile`.

**Acceptance criteria:**
- `make help` works in a fresh directory with no vault.
- `make init-vault` creates `vault/` and `vault/akanga.yaml` without error.
- `make test PHASE=0 MIRIN=/path/to/akanga_mirin` reaches the correct test directory
  or fails with a clear "tests not found" message.
- `make clean` is safe to run in an empty directory.

---

### MF-3 — Create docs/foundations/makefile-basics.md

**File:** `akanga_mirin/docs/foundations/makefile-basics.md`
**Depends on:** nothing (docs/foundations/ directory created as part of this task)
**Effort:** 3 hours
**Who:** any contributor comfortable explaining tooling to intermediate Python
developers

Write the full document following the outline in Part 3. The document must:
- Explain Make as a command runner, not a build system, in the first paragraph
- Include a 20-line standalone example Makefile that a learner can copy into an
  empty directory and run with `make hello` immediately
- Cover all 10 topics in the outline

**Acceptance criteria:**
- The 20-line example Makefile in the document runs correctly on macOS and Linux.
- Every code block is syntactically correct (uses tabs, not spaces).
- The help target section shows the exact grep/awk command used in the Akanga Makefile.
- No topic in the outline is omitted.
- Document reads in under 25 minutes for an intermediate Python developer.

---

### MF-4 — Add Makefile quick-reference callout to each phase doc (0–8)

**Files:** all 9 `docs/learning/phase-NN-*.md` files
**Depends on:** MF-1 (targets must exist to reference)
**Effort:** 1 hour total (about 7 minutes per phase)
**Who:** any contributor

Insert the quick-reference callout box (from Part 4) immediately below the estimated
time line in each phase doc. Each callout shows exactly three targets relevant to
that phase.

**Acceptance criteria:**
- All 9 phase docs contain the callout.
- Callout targets match the phase number exactly.
- No existing content is modified — insert only.
- The callout renders correctly in glow (run `make docs-phase PHASE=N` to verify).

---

### MF-5 — Add foundations/makefile-basics.md link to Phase 0

**File:** `docs/learning/phase-00-file-system-as-database.md`
**Depends on:** MF-3 (foundations doc must exist)
**Effort:** 10 minutes
**Who:** any contributor

Add one sentence to Phase 0 linking to the foundations doc, with a read-time note.
Place it in the "Prerequisites" or "Setup" section if present; otherwise add it
immediately before the first concept.

Exact text: "If you've never written a Makefile before, read
`docs/foundations/makefile-basics.md` — it covers everything you need in about 20
minutes and you can return to this phase immediately after."

**Acceptance criteria:**
- Link is present and the relative path resolves correctly.
- Link does not appear in phases 1–8 (it is a one-time primer, not repeated).

---

### MF-6 — Smoke-test all Makefile targets

**Depends on:** MF-1, MF-2, and at least one phase's tests, skeletons, solutions,
and examples created
**Effort:** 1.5 hours
**Who:** any contributor with the full repo cloned

Run every target in the root Makefile and verify expected output or expected graceful
failure. Document results in a short checklist.

**Test matrix:**

| Target | Expected result |
|---|---|
| `make help` | Colored output, all groups present |
| `make setup` | Dependencies installed via uv |
| `make test PHASE=0` | Tests run (pass or fail — not crash) |
| `make test-solution PHASE=0` | Solution tests run and pass |
| `make test-all` | Runs all available solutions, no crash |
| `make test-mine` | Runs against ./src/ (may fail if src empty) |
| `make test-phase-range FROM=0 TO=2` | Runs phases 00, 01, 02 |
| `make verify PHASE=0` | Verifies phase 00 solution cumulatively |
| `make verify-all` | Verifies all available solutions |
| `make example PHASE=0` | Runs examples/phase_00_*.py |
| `make examples-all` | Runs all available examples |
| `make skeleton PHASE=0` | Copies skeletons/phase_00/src/ → ./src/ |
| `make skeleton-check PHASE=0` | Reports OK or lists leaked methods |
| `make lint` | Ruff runs without crash |
| `make typecheck PHASE=0` | mypy runs on solutions/phase_00/src/ |
| `make check` | Runs lint + test-all |
| `make docs-phase PHASE=0` | Opens phase 00 doc in glow |
| `make foundations TOPIC=sqlite` | Opens sqlite-basics.md in glow |
| `make study PHASE=0` | Launches tmux session (or reports tmux missing) |
| `make commit-progress PHASE=0` | Creates a git commit (run in a test branch) |
| `make push` | Prompts for confirmation and aborts on "N" |

**Acceptance criteria:**
- Every target in the test matrix produces the expected result.
- No target exits silently with code 0 when it should have errored.
- `make help` and `make setup` work on a fresh clone before any other targets.

---

### MF-7 — Test learner's project Makefile template (integration test)

**Depends on:** MF-2, MF-1 (for MIRIN path)
**Effort:** 45 minutes

Create a fresh empty directory, copy `templates/project-makefile` as `Makefile`,
run `uv init`, and verify:

- `make help` works
- `make setup` works
- `make init-vault` creates `vault/`
- `make test PHASE=0 MIRIN=/path/to/akanga_mirin` reaches the test suite correctly

**Acceptance criteria:**
- All four targets above pass in a directory with no prior Akanga code.
- `make clean` on an empty directory does not error.

---

### MF-8 — Review pass

**Depends on:** MF-1 through MF-7 all complete
**Effort:** 45 minutes
**Who:** one person who did not write the Makefiles

Read the root Makefile, the template Makefile, and `makefile-basics.md` end-to-end
as a learner would on their first day. Verify:

- Every `## comment` in the root Makefile is accurate.
- `make help` output matches what the targets actually do.
- The foundations doc's 20-line example runs without modification.
- No target name in the phase doc callouts differs from the actual target name.

**Acceptance criteria:**
- At least one reviewer who did not write the Makefiles has run `make help` and
  read all three files.
- Any discrepancy between docs and implementation is corrected before this task
  is marked complete.

---

### Summary Table

| Task | Dependency | Effort | Blocks |
|---|---|---|---|
| MF-1 — Root Makefile | — | 2 h | MF-4, MF-6 |
| MF-2 — Learner template Makefile | — | 45 min | MF-7 |
| MF-3 — makefile-basics.md | — | 3 h | MF-4, MF-5 |
| MF-4 — Phase doc callouts (×9) | MF-1 | 1 h | MF-8 |
| MF-5 — Phase 0 foundations link | MF-3 | 10 min | MF-8 |
| MF-6 — Smoke-test all targets | MF-1, tests/solutions exist | 1.5 h | MF-8 |
| MF-7 — Integration-test template | MF-2 | 45 min | MF-8 |
| MF-8 — Review pass | MF-1–MF-7 | 45 min | — |
| **Total** | | **~9.75 h** | |

MF-1, MF-2, and MF-3 can be parallelized across three contributors. MF-4 and MF-5
can start as soon as MF-1 and MF-3 are merged respectively. MF-6 requires at least
one complete phase (tests + skeleton + solution + example) to exist in the repo.
