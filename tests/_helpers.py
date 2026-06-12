"""Shared test-infrastructure helpers. No fixtures live here.

This module is the single home for the dual-layout import policy: learner
code may live flat (``src/db.py``) or as a package (``src/akanga_core/db.py``),
so every suite loads modules by trying candidates in order. Before
consolidation that policy existed as 23 hand-copied loader functions which
had quietly forked on exception breadth, guards, and search order
(adversarial-analysis-v5 #1) — the per-phase ``_load_*`` wrappers remain (so
call sites and learner-facing names don't change), but they are now one-line
delegations to :func:`load_attr`, and the policy decisions live here, once:

- **ImportError is caught, not just ModuleNotFoundError**, and every
  candidate's real error is included in the failure message — a module that
  *exists but is broken* is reported with its actual traceback text instead
  of a misleading "cannot import" (the worst of the pre-consolidation forks).
- **Guards are explicit**: ``guard=`` rejects same-name impostors (e.g. an
  unrelated ``parser`` package from site-packages) with a clear message.
- **Search order is the caller's choice** and therefore visible at the call
  site — flat-first everywhere except Phase 8's MCP loader, which documents
  why it is package-first.

Imports no learner code at import time, so importing this module is always
safe during collection.
"""
from __future__ import annotations

import importlib
from collections.abc import Callable
from typing import Any

import pytest

Candidate = tuple[str, str | None]


def load_attr(
    *candidates: Candidate,
    guard: Callable[[Any], bool] | None = None,
    guard_desc: str = "",
    hint: str = "",
) -> Any:
    """Return the first loadable candidate ``(module_name, attr_name)``.

    ``attr_name=None`` returns the module object itself. ``guard`` (with a
    human-readable ``guard_desc``) rejects objects that import fine but are
    not the learner's code. On total failure, ``pytest.fail`` reports every
    candidate's actual error, so "your file is missing" and "your file is
    broken" are distinguishable at a glance.
    """
    errors: list[str] = []
    for module_name, attr_name in candidates:
        try:
            module = importlib.import_module(module_name)
        except ImportError as exc:  # includes ModuleNotFoundError
            errors.append(f"{module_name}: {type(exc).__name__}: {exc}")
            continue
        target = module if attr_name is None else getattr(module, attr_name, None)
        if target is None:
            errors.append(f"{module_name}: imported, but has no attribute {attr_name!r}")
            continue
        if guard is not None and not guard(target):
            errors.append(
                f"{module_name}{'.' + attr_name if attr_name else ''}: rejected — "
                f"{guard_desc or 'failed the loader guard (wrong module of the same name?)'}"
            )
            continue
        return target

    wanted = hint or (candidates[0][1] or candidates[0][0])
    detail = "\n  ".join(errors)
    pytest.fail(
        f"\n\nCannot load {wanted}. Tried:\n  {detail}\n"
        "If the file exists, the error above comes from INSIDE it — fix that "
        "import/syntax problem and re-run. If it does not exist yet, check "
        "AKANGA_SRC and the phase doc's deliverable list."
    )
