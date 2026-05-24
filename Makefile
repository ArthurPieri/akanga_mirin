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

docs-phase: ## Open phase doc in glow without launching full tmux (PHASE=3)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${PHASE_PAD}-*.md" 2>/dev/null | head -1); \
	if [ -z "$$DOC" ]; then \
		echo "error: no doc found for phase $${PHASE_PAD} in $(AKANGA_DOCS)/learning/"; exit 1; \
	fi; \
	$(GLOW) -p "$$DOC"

docs-all: ## Open all phase docs in glow sequentially (full review mode)
	@for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		DOC=$$(find "$(AKANGA_DOCS)/learning" -name "phase-$${PHASE_PAD}-*.md" 2>/dev/null | head -1); \
		if [ -n "$$DOC" ]; then \
			printf '\n\033[1;33m── Phase %s ──────────────────────────────────────────\033[0m\n' "$${PHASE_PAD}"; \
			$(GLOW) -p "$$DOC"; \
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
# TESTING — run tests against learner's code or solutions
# =============================================================================

test: ## Run tests for one phase against AKANGA_SRC (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	if [ ! -d "tests/phase_$${PHASE_PAD}" ]; then \
		echo "error: tests/phase_$${PHASE_PAD}/ not found — tests may not exist yet"; exit 1; \
	fi; \
	echo "Testing phase $${PHASE_PAD} against $(AKANGA_SRC) ..."; \
	AKANGA_SRC="$(AKANGA_SRC)" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v

test-solution: ## Run tests for one phase against the reference solution (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
	if [ ! -d "$$SOLUTION_SRC" ]; then \
		echo "error: no solution found at $$SOLUTION_SRC"; exit 1; \
	fi; \
	echo "Testing phase $${PHASE_PAD} against reference solution ..."; \
	AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v

test-all: ## Run all phases against their solutions (full suite verification)
	@echo "Running full test suite against solutions ..."; \
	FAILED=0; \
	for n in 0 1 2 3 4 5 6 7 8; do \
		PHASE_PAD=$$(printf "%02d" $$n); \
		SOLUTION_SRC="solutions/phase_$${PHASE_PAD}/src"; \
		if [ -d "$$SOLUTION_SRC" ] && [ -d "tests/phase_$${PHASE_PAD}" ]; then \
			printf '\n\033[1;33m── Phase %s ──\033[0m\n' "$${PHASE_PAD}"; \
			AKANGA_SRC="$$SOLUTION_SRC" $(PYTEST) tests/phase_$${PHASE_PAD}/ -v \
				|| FAILED=$$((FAILED+1)); \
		fi; \
	done; \
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
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
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
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
	SKEL="skeletons/phase_$${PHASE_PAD}"; \
	if [ ! -d "$$SKEL" ]; then \
		echo "error: no skeleton found at $$SKEL"; exit 1; \
	fi; \
	echo "Copying skeleton for phase $${PHASE_PAD} → ./src/ ..."; \
	mkdir -p src; \
	cp -r "$$SKEL/src/." src/; \
	echo "Done. Edit src/ to complete the implementation."; \
	printf 'Next: \033[36mmake test PHASE=%d\033[0m\n' "$(PHASE)"

skeleton-check: ## Verify skeleton still raises NotImplementedError — no solution leakage (PHASE=2)
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
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
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
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
# GIT — facilitator workflow
# =============================================================================

commit-progress: ## Auto-commit progress with message 'progress: phase N tests passing'
	@PHASE_PAD=$$(printf "%02d" $(PHASE)); \
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
