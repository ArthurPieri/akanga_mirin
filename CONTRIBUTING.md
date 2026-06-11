# Contributing to Akanga Mirin

## Before you change anything

Read, in this order:

1. `docs/status-remediation.md` — decisions **D1–D11** (Round 2) and **E1–E10**
   (Round 3). These are settled; do not re-litigate them in a PR.
2. The Resolution Logs in `docs/adversarial-analysis-v2.md` and
   `docs/adversarial-analysis-v3.md` — before changing any **semantics**
   (schemas, event ordering, context budgets, API contracts), check whether the
   behavior you want to change was an explicit decision.

## How solutions work

Reference solutions for all 9 phases live in `solutions/phase_NN/` on `main`
(decision D1). They are the authoritative implementations the test suites and
docs are checked against — fixing them in place is the correct fix path.
`make test-solution PHASE=N` must stay green for every phase you touch.

## The canonical-tree rule

Each module is **introduced in exactly one phase** and copied forward
byte-identical into every later phase tree (e.g. `parser.py` is introduced in
phase 00; phases 01–08 carry identical copies). Never patch a downstream copy:

1. Fix the module in its **introduction phase**.
2. Run `make sync-forward FROM=N FILE=src/akanga_core/<module>.py` to propagate.

The canonical manifest and the drift check (`sync_forward --check-all`) enforce
this in CI — a PR that diverges a downstream copy fails the gate.

## Quality gates

- `make check` before opening a PR — lint plus the full test matrix.
- `make verify PHASE=N` for any phase whose solution you touched — the
  cumulative gate (phase N's tree must pass all suites up through phase N).
- Phase doc changes require a corresponding test change in the same PR.
- All new phases must include at least one error-path test.
