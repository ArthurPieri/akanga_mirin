# Reference Solutions

Reference implementations for **all 9 phases** live here, on `main` (decision D1).
Each `phase_NN/` tree passes its own suite and every suite before it:

    solutions/
      phase_00/src/akanga_core/parser.py
      phase_01/src/akanga_core/...
      ...
      phase_08/src/akanga_core/...
      phase_08/src/akanga_mcp/...

Run them with `make test-solution PHASE=N`; `make status` shows the full matrix.

## How to use these without wasting your own learning

The value of this curriculum is in writing the code yourself. The solutions
exist so you can check your work, get unstuck, and study a worked reference —
not so you can skip the work. CS50-style norms:

**Reasonable:**

- Diffing your code against the reference **after your tests pass**.
- Peeking at **one function** after 30+ minutes stuck on a single test, **if**
  you record what you learned — `make peek` does exactly this (shows one
  function and appends a note to your learner-local `PEEKS.md`).
- Reading a phase's solution after you have finished that phase, to compare
  approaches.

**Not reasonable:**

- Copying from the reference before attempting the implementation yourself.
- Copying a solution wholesale — ever. A green suite you didn't earn teaches
  nothing, and the conceptual gate (`make vault-check`) will show it.

## The post-green ritual

When a phase's tests go green: **diff your implementation against the
reference, then write one vault node about a difference and why it exists.**
Maybe you locked at a different granularity, ordered shutdown differently, or
budgeted the RAG context another way. The diff is where the learning compounds —
a copied solution has no diff, which is the point.
