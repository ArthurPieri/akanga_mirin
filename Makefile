# =============================================================================
# Akanga Mirin — Learning Repository Makefile
# =============================================================================
#
# Usage:  make <target> [PHASE=N] [FROM=N] [TO=N] [TOPIC=name]
#
# Run 'make help' to see all available targets.
#
# Environment variables:
#   AKANGA_SRC   Path to the learner's own src/ directory (default: ./src)
#   AKANGA_DOCS  Path to this repo's docs/ directory (auto-detected)
#   AKANGA_CODE  Code directory opened in the study session (default: ./src)

.DEFAULT_GOAL := help

# ── Variables ─────────────────────────────────────────────────────────────────

PHASE        ?= 0
# Phase 1 is split into 1A/1B: PHASE may carry an a/b suffix (1a, 1b).
# PHASE_NUM strips it (tests/skeletons are unified at phase_01); docs-phase/study keep it.
PHASE_NUM    := $(shell echo "$(PHASE)" | sed 's/[aAbB]$$//')
PHASE_PAD    := $(shell printf "%02d" "$(PHASE_NUM)" 2>/dev/null)

FROM         ?= 0
TO           ?= 8

TOPIC        ?=
PYTEST_ARGS  ?=

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
        vault-init vault-check \
        run serve mcp \
        test test-solution test-all test-mine test-phase-range \
        verify verify-all \
        example examples-all \
        skeleton skeleton-check \
        setup setup-phase \
        lint typecheck check \
        status where-is-my-src sync-forward \
        commit-progress push \
        docs-serve docs-build

# =============================================================================
# HELP — self-documenting (reads ## comments on target lines)
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
	@printf '  \033[1;33mVault\033[0m\n'
	@grep -E '^(vault-init|vault-check)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mRun your app\033[0m\n'
	@grep -E '^(run|serve|mcp)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
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
	@printf '  \033[1;33mDocs workflow\033[0m\n'
	@grep -E '^(docs-serve|docs-build)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[1;33mFacilitator workflow\033[0m\n'
	@grep -E '^(verify|verify-all|commit-progress|push)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '\n'
	@printf '  \033[1;33mDiagnostics\033[0m\n'
	@grep -E '^(status|where-is-my-src|sync-forward)[[:space:]]*:.*##' $(MAKEFILE_LIST) \
		| awk -F'##' '{printf "    \033[36m%-28s\033[0m %s\n", $$1, $$2}'
	@printf '\n'
	@printf '  \033[2mVariables: PHASE=N (default 0)  FROM=N  TO=N  FILE=path  TOPIC=name\033[0m\n'
	@printf '\n'

# =============================================================================
# STUDY — open tmux layout for a phase
# =============================================================================

study: ## Open tmux study session (PHASE=2 → phase 02)
	@AKANGA_DOCS="$(AKANGA_DOCS)" AKANGA_CODE="$(AKANGA_CODE)" \
		bash scripts/study.sh $(PHASE)

docs-phase: ## Open phase doc in glow without launching full tmux (PHASE=3, PHASE=1a)
	@RAW="$(PHASE)"; SUB=""; \
	case "$$RAW" in \
		*[aAbB]) SUB=$$(printf '%s' "$${RAW#"$${RAW%?}"}" | tr 'AB' 'ab'); RAW="$${RAW%?}";; \
	esac; \
	PHASE_PAD=$$(printf "%02d" "$$RAW"); \
	if [ "$$PHASE_PAD" = "01" ] && [ -z "$$SUB" ]; then \
		echo "note: Phase 1 is split into 1A and 1B — opening 1A. Use PHASE=1b for 1B."; SUB="a"; \
	fi; \
	DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${PHASE_PAD}$${SUB}-*.md" 2>/dev/null | sort | head -1); \
	if [ -z "$$DOC" ]; then \
		echo "error: no doc found for phase $${PHASE_PAD}$${SUB} in $(AKANGA_DOCS)/learning/"; exit 1; \
	fi; \
	$(GLOW) -p "$$DOC"

docs-all: ## Open all phase docs in glow sequentially (full review mode)
	@for pat in 00 01a 01b 02 03 04 05 06 07 08; do \
		DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${pat}-*.md" 2>/dev/null | sort | head -1); \
		if [ -n "$$DOC" ]; then \
			printf '\n\033[1;33m── Phase %s ──────────────────────────────────────────\033[0m\n' "$${pat}"; \
			$(GLOW) -p "$$DOC"; \
		else \
			printf '\033[0;31mwarning: no doc found for phase %s\033[0m\n' "$${pat}"; \
		fi; \
	done

foundations: ## Open a foundations doc in glow (TOPIC=sqlite → sqlite-basics.md)
	@if [ -z "$(TOPIC)" ]; then \
		printf '\033[1;36mAvailable foundations docs:\033[0m\n'; \
		ls "$(AKANGA_DOCS)/foundations/" 2>/dev/null | sed 's/\.md$$//' | sort \
			| awk '{printf "  make foundations TOPIC=%s\n", $$1}'; \
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
# VAULT — create and validate the learner's knowledge vault
# =============================================================================

vault-init: ## Create ./vault + akanga.yaml (owner from git config, Nhamandu default workspace)
	@if [ -f "vault/akanga.yaml" ]; then \
		echo "vault/akanga.yaml already exists — skipping."; \
	else \
		mkdir -p vault; \
		OWNER=$$(git config user.name 2>/dev/null || true); \
		OWNER="$${OWNER:-Your Name}"; \
		WS_UUID=$$($(PYTHON) -c "import uuid; print(uuid.uuid4())"); \
		printf 'owner: %s\ndefault_workspace:\n  name: Nhamandu\n  id: %s   # generated at init, never changes\nworkspaces: []\n' \
			"$$OWNER" "$$WS_UUID" > vault/akanga.yaml; \
		printf 'Created \033[36mvault/akanga.yaml\033[0m (owner: %s, default workspace: Nhamandu)\n' "$$OWNER"; \
	fi; \
	printf 'Vault ready at \033[36m./vault/\033[0m\n'

vault-check: ## Validate your vault (PHASE=N checks that phase's expected nodes; FULL=1 adds the >=50-node check)
	@ARGS=""; \
	if [ "$(origin PHASE)" != "file" ]; then ARGS="--phase $(PHASE)"; fi; \
	if [ -n "$(FULL)" ]; then ARGS="$$ARGS --full"; fi; \
	$(PYTHON) scripts/validate_vault.py "$${VAULT:-./vault}" $$ARGS

# =============================================================================
# RUN — launch the learner's own app (TUI / REST API / MCP server)
# =============================================================================

run: ## Launch your TUI from AKANGA_SRC (Phase 5+; VAULT=./vault DB=./.akanga.db)
	@if [ ! -d "$(AKANGA_SRC)" ]; then \
		echo "error: AKANGA_SRC ($(AKANGA_SRC)) does not exist"; exit 1; \
	fi; \
	printf 'Launching TUI from \033[36m%s\033[0m ...\n' "$(AKANGA_SRC)"; \
	printf '\033[2mTip: the graph view (Kitty protocol) degrades inside tmux — run this in a plain Ghostty/Kitty window.\033[0m\n'; \
	PYTHONPATH="$(AKANGA_SRC)" $(PYTHON) -m akanga_tui.app --vault "$${VAULT:-./vault}" --db "$${DB:-./.akanga.db}"

serve: ## Launch your FastAPI server from AKANGA_SRC (Phase 6+; localhost:8000)
	@if [ ! -d "$(AKANGA_SRC)" ]; then \
		echo "error: AKANGA_SRC ($(AKANGA_SRC)) does not exist"; exit 1; \
	fi; \
	printf 'Launching REST API from \033[36m%s\033[0m on http://127.0.0.1:8000 ...\n' "$(AKANGA_SRC)"; \
	PYTHONPATH="$(AKANGA_SRC)" $(PYTHON) -c "import uvicorn; from akanga_core.server import create_app; uvicorn.run(create_app(vault='$${VAULT:-./vault}', db_path='$${DB:-./.akanga.db}'), host='127.0.0.1', port=8000)"

mcp: ## Launch your MCP server from AKANGA_SRC (Phase 8; binds 127.0.0.1)
	@if [ ! -d "$(AKANGA_SRC)" ]; then \
		echo "error: AKANGA_SRC ($(AKANGA_SRC)) does not exist"; exit 1; \
	fi; \
	printf 'Launching MCP server from \033[36m%s\033[0m ...\n' "$(AKANGA_SRC)"; \
	PYTHONPATH="$(AKANGA_SRC)" $(PYTHON) -m akanga_mcp.server --vault "$${VAULT:-./vault}" --db "$${DB:-./.akanga.db}"

docs-serve: ## Start MKDocs dev server with live reload (localhost:8000)
	@echo "Starting MKDocs dev server ..."; \
	uv run mkdocs serve

docs-build: ## Build static site into site/ directory
	@echo "Building MKDocs site ..."; \
	uv run mkdocs build

# =============================================================================
# TESTING — run tests against learner's code or solutions
# =============================================================================

test: ## Run tests for one phase against AKANGA_SRC (PHASE=2)
	@PHASE_PAD="$(PHASE_PAD)"; \
	if [ ! -d "tests/phase_$${PHASE_PAD}" ]; then \
		echo "error: tests/phase_$${PHASE_PAD}/ not found — tests may not exist yet"; exit 1; \
	fi; \
	if [ "$(AKANGA_SRC)" = "./src" ] && [ "$(origin AKANGA_SRC)" = "default" ]; then \
		printf '\n\033[1;33m⚠  WARNING: AKANGA_SRC is not set — defaulting to ./src\033[0m\n'; \
		printf '\033[1;33m   If ./src is empty or missing, you are NOT testing your code.\033[0m\n'; \
		printf '\033[1;33m   To test your code:      AKANGA_SRC=/path/to/src make test PHASE=%d\033[0m\n' "$(PHASE)"; \
		printf '\033[1;33m   To test the solution:   make test-solution PHASE=%d\033[0m\n\n' "$(PHASE)"; \
	fi; \
	printf 'Testing phase \033[1m%s\033[0m against \033[36m%s\033[0m ...\n' "$${PHASE_PAD}" "$(AKANGA_SRC)"; \
	AKANGA_SRC="$(AKANGA_SRC)" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v $(PYTEST_ARGS)

test-solution: ## Run tests for one phase against the reference solution (PHASE=2)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SOLUTION_SRC" ]; then \
		echo "ERROR: No solution found for phase $(PHASE). Skipping." >&2; exit 1; \
	fi; \
	echo "Testing phase $${PHASE_PAD} against reference solution ..."; \
	AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v

test-all: ## Run all phases against their solutions (full suite verification)
	@echo "Running full test suite against solutions ..."; \
	FAILED=0; \
	TESTED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ -d "$$SOLUTION_SRC" ] && [ -d "tests/phase_$${PHASE_PAD}" ]; then \
			printf '\n\033[1;33m── Phase %s ──\033[0m\n' "$${PHASE_PAD}"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
			TESTED=$$((TESTED+1)); \
		fi; \
	done; \
	if [ $$TESTED -eq 0 ]; then \
		echo "ERROR: No solution directories found — test-all ran 0 tests." >&2; \
		exit 1; \
	fi; \
	if [ $$FAILED -gt 0 ]; then \
		echo ""; \
		printf '\033[0;31m%d phase(s) failed.\033[0m\n' "$$FAILED"; exit 1; \
	else \
		printf '\n\033[0;32mAll phases passed.\033[0m\n'; \
	fi

test-mine: ## Run all tests against AKANGA_SRC (your own code)
	@echo "Testing all phases against $(AKANGA_SRC) ..."; \
	AKANGA_SRC="$(AKANGA_SRC)" $(PYTEST) tests/ -v

test-phase-range: ## Run phases FROM..TO against their solutions (FROM=0 TO=3)
	@echo "Testing phases $(FROM)–$(TO) against solutions ..."; \
	FAILED=0; \
	for n in $$(seq $(FROM) $(TO)); do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ -d "$$SOLUTION_SRC" ] && [ -d "tests/phase_$${PHASE_PAD}" ]; then \
			printf '\n\033[1;33m── Phase %s ──\033[0m\n' "$${PHASE_PAD}"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		printf '\033[0;31m%d phase(s) failed.\033[0m\n' "$$FAILED"; exit 1; \
	fi

# =============================================================================
# VERIFICATION — cumulative solution correctness (facilitator targets)
# =============================================================================

verify: ## Verify solution N passes all tests 00..N cumulatively (PHASE=3)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SOLUTION_SRC" ]; then \
		echo "ERROR: Solutions for phase $(PHASE) are not yet published." >&2; exit 1; \
	fi; \
	echo "Verifying phase $${PHASE_PAD} solution against phases 00..$${PHASE_PAD} ..."; \
	FAILED=0; \
	for n in $$(seq 0 $(PHASE)); do \
		N_PAD=$$(printf "%02d" $$n); \
		if [ -d "tests/phase_$${N_PAD}" ]; then \
			printf '  \033[36m→ testing phase %s\033[0m\n' "$${N_PAD}"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${N_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		printf '\n\033[0;31mFailed: phase %s solution is not cumulative.\033[0m\n' "$${PHASE_PAD}"; exit 1; \
	else \
		printf '\n\033[0;32mPhase %s solution is cumulative — all prior tests pass.\033[0m\n' "$${PHASE_PAD}"; \
	fi

verify-all: ## Verify all 9 phases are cumulative (facilitator, slow)
	@echo "Verifying cumulative correctness for all phases ..."; \
	FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ ! -d "$$SOLUTION_SRC" ]; then continue; fi; \
		printf '\n\033[1;33m── Verifying phase %s (cumulative 00..%s) ──\033[0m\n' "$${PHASE_PAD}" "$${PHASE_PAD}"; \
		for m in $$(seq 0 $$n); do \
			M_PAD=$$(printf "%02d" $$m); \
			if [ -d "tests/phase_$${M_PAD}" ]; then \
				AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${M_PAD}/ -q \
					|| FAILED=$$((FAILED+1)); \
			fi; \
		done; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		printf '\n\033[0;31m%d cumulative check(s) failed.\033[0m\n' "$$FAILED"; exit 1; \
	else \
		printf '\n\033[0;32mAll phases cumulative — full verification passed.\033[0m\n'; \
	fi

# =============================================================================
# EXAMPLES — standalone concept demo scripts
# =============================================================================

example: ## Run the standalone example script for a phase (PHASE=2)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SCRIPT=$$(find examples -name "phase_$${PHASE_PAD}_*.py" 2>/dev/null | head -1); \
	if [ -z "$$SCRIPT" ]; then \
		echo "error: no example script found for phase $${PHASE_PAD} in examples/"; exit 1; \
	fi; \
	echo "Running $$SCRIPT ..."; \
	$(PYTHON) "$$SCRIPT"

examples-all: ## Run all 9 phase example scripts sequentially
	@FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SCRIPT=$$(find examples -name "phase_$${PHASE_PAD}_*.py" 2>/dev/null | head -1); \
		if [ -n "$$SCRIPT" ]; then \
			printf '\n\033[1;33m── Phase %s: %s ──\033[0m\n' "$${PHASE_PAD}" "$$SCRIPT"; \
			$(PYTHON) "$$SCRIPT" || FAILED=$$((FAILED+1)); \
		fi; \
	done; \
	if [ $$FAILED -gt 0 ]; then \
		printf '\033[0;31m%d example(s) failed.\033[0m\n' "$$FAILED"; exit 1; \
	fi

# =============================================================================
# SKELETON — set up or verify learner's starting point
# =============================================================================

skeleton: ## Copy skeleton for a phase into ./src/ as the learner's starting point (PHASE=2)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SKEL="skeletons/phase_$${PHASE_PAD}"; \
	if [ ! -d "$$SKEL" ]; then \
		echo "error: no skeleton found at $$SKEL"; exit 1; \
	fi; \
	echo "Copying skeleton for phase $${PHASE_PAD} → ./src/ ..."; \
	mkdir -p src; \
	COPIED=0; SKIPPED=0; \
	for f in $$(cd "$$SKEL/src" && find . -type f | sed 's|^\./||'); do \
		if [ -e "src/$$f" ]; then \
			SKIPPED=$$((SKIPPED+1)); \
		else \
			mkdir -p "src/$$(dirname "$$f")"; \
			cp "$$SKEL/src/$$f" "src/$$f"; \
			COPIED=$$((COPIED+1)); \
		fi; \
	done; \
	printf 'Copied %d new file(s).\n' "$$COPIED"; \
	if [ "$$SKIPPED" -gt 0 ]; then \
		printf '\033[0;33mPreserved %d existing file(s) in src/ — your implementations were NOT overwritten.\033[0m\n' "$$SKIPPED"; \
		printf 'To inspect what the new skeleton ships: \033[36mls %s/src\033[0m\n' "$$SKEL"; \
	fi; \
	echo "Done. Edit src/ to complete the implementation."; \
	printf 'Next: \033[36mmake test PHASE=%d\033[0m\n' "$(PHASE)"

skeleton-check: ## Verify skeleton still raises NotImplementedError — no solution leakage (PHASE=2)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SKEL="skeletons/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SKEL" ]; then \
		echo "error: no skeleton found at $$SKEL"; exit 1; \
	fi; \
	echo "Checking skeleton for phase $${PHASE_PAD} — all stubs must raise NotImplementedError ..."; \
	$(PYTHON) scripts/skeleton_check.py "$$SKEL"

# =============================================================================
# SETUP — install dependencies
# =============================================================================

setup: ## Install all dependencies for the full learning path
	@echo "Installing all dependencies via uv ..."; \
	uv sync --all-extras; \
	printf '\n\033[0;32mDone.\033[0m Run \033[36mmake test PHASE=0\033[0m to verify.\n'

setup-phase: ## Install only the dependencies needed through a given phase (PHASE=2)
	@echo "Installing dependencies for phases 0–$(PHASE) ..."; \
	uv sync; \
	printf '\033[0;32mDone.\033[0m\n'

# =============================================================================
# QUALITY — lint, typecheck, full gate
# =============================================================================

lint: ## Lint all Python files in tests/ skeletons/ solutions/ examples/
	@DIRS=""; \
	for d in tests skeletons solutions examples src; do \
		if [ -d "$$d" ]; then DIRS="$$DIRS $$d"; fi; \
	done; \
	if [ -z "$$DIRS" ]; then \
		echo "No Python directories found to lint."; exit 0; \
	fi; \
	$(RUFF) check $$DIRS

typecheck: ## Run mypy on solutions/phase_NN/src/ (PHASE=3)
	@PHASE_PAD="$(PHASE_PAD)"; \
	SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SRC" ]; then \
		echo "error: no solution at $$SRC"; exit 1; \
	fi; \
	$(MYPY) "$$SRC"

check: ## Full quality gate: lint + test-all (run before a facilitator commit)
	@$(MAKE) lint
	@$(MAKE) test-all
	@printf '\n\033[0;32mAll checks passed.\033[0m\n'

# =============================================================================
# DIAGNOSTICS — understand the current state of the repo
# =============================================================================

status: ## Show phase completion matrix (skeleton / tests / solution per phase)
	@printf '\n  \033[1;36mPhase Completion Status\033[0m\n\n'; \
	printf '  %-8s %-12s %-10s %-12s\n' 'Phase' 'Skeleton' 'Tests' 'Solution'; \
	printf '  %-8s %-12s %-10s %-12s\n' '-----' '--------' '-----' '--------'; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SKEL=$$([ -d "skeletons/phase_$${PHASE_PAD}" ] && echo "✓ done" || echo "- todo"); \
		TEST=$$([ -d "tests/phase_$${PHASE_PAD}" ] && echo "✓ done" || echo "- todo"); \
		SOLN=$$([ -d "solutions/phase_$${PHASE_PAD}" ] && echo "✓ done" || echo "- todo"); \
		printf '  %-8s %-12s %-10s %-12s\n' "$$PHASE_PAD" "$$SKEL" "$$TEST" "$$SOLN"; \
	done; \
	printf '\n'

where-is-my-src: ## Show which source directory 'make test' is pointing at
	@if [ -d "$(AKANGA_SRC)" ]; then \
		printf '\033[0;32mAKANGA_SRC = %s\033[0m (directory exists)\n' "$(AKANGA_SRC)"; \
		printf 'Contents:\n'; \
		ls "$(AKANGA_SRC)" 2>/dev/null | awk '{printf "  %s\n", $$1}'; \
	else \
		printf '\033[0;31mAKANGA_SRC = %s\033[0m (DOES NOT EXIST)\n' "$(AKANGA_SRC)"; \
		printf 'Set it: export AKANGA_SRC=/path/to/your/src\n'; \
	fi

sync-forward: ## Preview or apply a fix from phase FROM to all later phases (FROM=2 FILE=src/...)
	@if [ -z "$(FILE)" ]; then \
		echo "Usage: make sync-forward FROM=2 FILE=src/akanga_core/parser.py"; \
		echo "       make sync-forward FROM=2 FILE=src/akanga_core/parser.py APPLY=1"; \
		exit 1; \
	fi; \
	$(PYTHON) scripts/sync_forward.py "$(FILE)" $(FROM) $(if $(APPLY),--apply,)

# =============================================================================
# GIT — facilitator workflow
# =============================================================================

commit-progress: ## Auto-commit progress with message 'progress: phase N tests passing'
	@PHASE_PAD="$(PHASE_PAD)"; \
	MSG="progress: phase $${PHASE_PAD} tests passing"; \
	git add tests/ solutions/ skeletons/ examples/ docs/ scripts/ Makefile 2>/dev/null || true; \
	git commit -m "$$MSG"; \
	echo "Committed: $$MSG"

push: ## Push to remote — prompts for confirmation before executing
	@read -p "Push to remote? [y/N] " CONFIRM; \
	if [ "$$CONFIRM" = "y" ] || [ "$$CONFIRM" = "Y" ]; then \
		git push; \
	else \
		echo "Aborted."; \
	fi
