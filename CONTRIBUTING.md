# Contributing to Akanga Mirin

Thank you for contributing to this learning path. This document covers the rules that keep the repo safe for learners.

---

## The Five Rules

1. **Run `make check` before opening a PR.** This runs lint + all tests against the reference solutions. A PR that breaks `make check` will not be merged.

2. **Do not modify `solutions/`.** The reference solutions are the ground truth for the test suite. If you believe a solution has a bug, open an issue and explain the problem — do not push a fix directly. Solutions live on the `solutions` branch, not `main`.

3. **SENTINEL comments are load-bearing — do not remove.** Lines marked `# SENTINEL` in skeleton files exist so `scripts/skeleton_check.py` can verify that students have not shipped solution code accidentally. Removing a SENTINEL silently breaks this check.

4. **Phase doc changes require a corresponding test change in the same PR.** If you clarify what a method should return, update the test that verifies the return value. Docs and tests must stay in sync.

5. **All new phases must include at least one error-path test.** Every phase test file must test at least one failure mode: malformed input, missing file, read-only resource, or similar. Happy-path-only test suites teach learners that error paths don't matter.

---

## Repository Structure

```
main            — phase docs, Makefile, skeletons, tests, this repo's source
solutions       — reference implementations (separate branch — do not modify on main)
```

Learners clone `main`. Solutions are available on the `solutions` branch for reference after completing each phase.

---

## Reporting Issues

- **Bug in a phase doc** — open a [GitHub Issue](https://github.com/ArthurPieri/akanga_mirin/issues) with the label `content-error`. Include the phase number, the incorrect statement, and a correction.
- **Bug in a test** — open an issue with the label `bug`. Include the failing phase, the command you ran, and the full error output.
- **Feature request** — open an issue with the label `enhancement`. Check `docs/future-ideas.md` first; the feature may already be parked there with a reason.

---

## Phase 8 (FastMCP / MCP)

Phase 8 has a shorter shelf life than other phases because it depends on the FastMCP library and the Model Context Protocol specification, both of which are under active development. Phase 8 has a named maintainer responsible for keeping its phase doc, skeleton, and solution current after MCP spec changes. If you notice Phase 8 is out of date, open an issue — do not submit a silent fix.

---

## Scope

This repo is local-first and single-user by design. Contributions that add cloud sync, Docker, vector embeddings, or multi-user features will not be merged — not because the ideas are bad, but because they are explicitly out of scope for the MVP and V1. See `docs/future-ideas.md` for context.
