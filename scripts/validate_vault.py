#!/usr/bin/env python3
"""
validate_vault.py — validate a learner's vault directory.

Checks, in order:
  1. The vault directory exists and contains Markdown nodes.
  2. Edges are well-formed — both the canonical frontmatter `edges:` block
     (list of {relation, relation-id, target, target-id}) and the inline
     shorthand `[[Target | relation]]` taught in Phase 1A.
  3. Relation names match the 71-type vocabulary in
     docs/foundations/relation-vocabulary.md (soft warning + nearest-match
     suggestion — custom relations are allowed by design).
  4. With --phase N: the phase doc's "Vault Nodes to Create" table is present
     (hard failure when expected nodes are missing).
  5. With --full: the global >= 50 node count check.

Exit codes: 0 = passed (possibly with warnings), 1 = hard failure.

Usage:
    python scripts/validate_vault.py ./vault
    python scripts/validate_vault.py ./vault --phase 2
    python scripts/validate_vault.py ./vault --phase 1a
    python scripts/validate_vault.py ./vault --full
"""

from __future__ import annotations

import argparse
import difflib
import re
import sys
from pathlib import Path

# ── Per-phase expected-node manifests ─────────────────────────────────────────
# Extracted from each phase doc's "Vault Nodes to Create" table
# (docs/learning/phase-NN-*.md). Keep in sync when the docs change.

PHASE_MANIFESTS: dict[str, list[str]] = {
    "0": [
        "YAML Frontmatter",
        "UUID",
        "Idempotence",
        "Atomic Write",
        "Content Hash",
        "Python Dataclass",
        "os.replace",
        "Vault Configuration",
    ],
    "1a": [
        "Directed Graph",
        "Labeled Property Graph",
        "Source of Truth",
        "Eventual Consistency",
        "Two-Pass Parsing",
    ],
    "1b": [
        "Node Types as Schema Variants",
        "Reference Integrity",
        "UUID",
        "Background Sync Queue",
        "Workspace Registry",
        "Nhamandu",
        "Akanga",
    ],
    "2": [
        "SQLite",
        "WAL Mode",
        "Adjacency List",
        "Derived Index",
        "Two-Pass Indexing",
        "FTS5",
        "Thread Safety",
    ],
    "3": [
        "Graph Traversal",
        "BFS",
        "DFS",
        "Cycle Detection",
        "Ego-Graph",
        "Directed Edge Traversal",
        "Graph Density Ceiling",
        "Canvas Renderer in v2",
    ],
    "4": [
        "File Watching",
        "Debouncing",
        "Threads vs asyncio",
        "Event Bus",
        "run_coroutine_threadsafe",
        "Sync Queue Drain",
        "watchdog",
    ],
    "5": [
        "Reactive TUI",
        "Widget Composition",
        "Event-Driven UI",
        "Keyboard-First Mouse-Aware",
        "Two-Layer Graph Renderer",
        "Suspend/Resume",
        "Textual",
        "textual-kitty",
        "Kitty Terminal Graphics Protocol",
    ],
    "6": [
        "REST",
        "FastAPI",
        "Lifespan Context Manager",
        "Pydantic",
        "WebSocket",
        "Path Traversal Protection",
        "API Boundary",
        "OpenAPI",
    ],
    "7": [
        "Git Commit Model",
        "GitPython",
        "Non-Fatal Error Handling",
        "Idempotent Commit",
        ".gitignore as Contract",
    ],
    "8": [
        "MCP",
        "FastMCP",
        "Graph RAG",
        "Triple Serialization",
        "MCP Tool Design",
        "API Boundary for AI Clients",
    ],
}

INLINE_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")
CODE_BLOCK_RE = re.compile(r"```.*?```", flags=re.DOTALL)
VOCAB_ROW_RE = re.compile(r"^\|\s*`([A-Z]{2}-\d{3})`\s*\|\s*`([a-z_]+)`", re.MULTILINE)


def normalize_phase(raw: str) -> str:
    """'01a' → '1a', '00' → '0', '2' → '2'. Returns lowercase, no leading zeros."""
    p = raw.strip().lower()
    m = re.fullmatch(r"0*(\d+)([ab]?)", p)
    if not m:
        return p
    return m.group(1) + m.group(2)


def load_vocabulary() -> dict[str, str]:
    """Return {relation_name: relation_id} from relation-vocabulary.md, or {} if missing."""
    vocab_path = (
        Path(__file__).resolve().parent.parent
        / "docs" / "foundations" / "relation-vocabulary.md"
    )
    if not vocab_path.is_file():
        return {}
    text = vocab_path.read_text(encoding="utf-8")
    return {name: rid for rid, name in VOCAB_ROW_RE.findall(text)}


def split_frontmatter(content: str) -> tuple[str | None, str]:
    """Split a node file into (frontmatter_text, body). frontmatter_text is None if absent."""
    if not content.startswith("---"):
        return None, content
    end = content.find("\n---", 3)
    if end == -1:
        return None, content
    return content[3:end].strip("\n"), content[end + 4:]


def parse_frontmatter(fm_text: str) -> dict:
    """Parse frontmatter YAML. Uses PyYAML when available, else a minimal
    line-based parser good enough for `title:` and the taught `edges:` block."""
    try:
        import yaml  # provided transitively by python-frontmatter

        data = yaml.safe_load(fm_text)
        return data if isinstance(data, dict) else {}
    except ImportError:
        pass
    except Exception:
        return {"__parse_error__": True}

    # Fallback: minimal parser for title + edges list
    data: dict = {}
    edges: list[dict] = []
    in_edges = False
    current: dict | None = None
    for line in fm_text.splitlines():
        if not line.strip():
            continue
        if not line.startswith(" "):
            in_edges = False
            current = None
            if line.startswith("edges:"):
                rest = line[len("edges:"):].strip()
                if rest in ("", "|"):
                    in_edges = True
                else:
                    data["edges"] = [] if rest == "[]" else rest
                continue
            if ":" in line:
                key, _, val = line.partition(":")
                data[key.strip()] = val.strip().strip("'\"")
            continue
        if in_edges:
            stripped = line.strip()
            if stripped.startswith("- "):
                current = {}
                edges.append(current)
                stripped = stripped[2:]
            if ":" in stripped and current is not None:
                key, _, val = stripped.partition(":")
                current[key.strip()] = val.strip().strip("'\"")
    if in_edges or edges:
        data["edges"] = edges
    return data


def validate_vault(
    vault_path: str,
    phase: str | None = None,
    full: bool = False,
) -> bool:
    """Returns True when no HARD failure occurred. Warnings never fail the run."""
    path = Path(vault_path)
    if not path.is_dir():
        print(f"Error: {vault_path} is not a directory", file=sys.stderr)
        return False

    hard_failures: list[str] = []
    warnings: list[str] = []

    nodes = sorted(path.glob("**/*.md"))
    print(f"Found {len(nodes)} nodes.")

    vocab = load_vocabulary()
    if not vocab:
        warnings.append(
            "relation-vocabulary.md not found — skipping relation-name validation."
        )

    titles: set[str] = set()
    total_edges = 0

    for node_file in nodes:
        rel_name = node_file.relative_to(path)
        try:
            content = node_file.read_text(encoding="utf-8")
        except Exception as e:
            hard_failures.append(f"{rel_name}: unreadable ({e})")
            continue

        fm_text, body = split_frontmatter(content)

        # ── Title (frontmatter `title:`, fallback: filename stem) ────────────
        title = node_file.stem
        fm: dict = {}
        if fm_text is not None:
            fm = parse_frontmatter(fm_text)
            if fm.pop("__parse_error__", None):
                hard_failures.append(f"{rel_name}: malformed YAML frontmatter")
            if isinstance(fm.get("title"), str) and fm["title"].strip():
                title = fm["title"].strip()
        titles.add(title)
        titles.add(node_file.stem)

        used_relations: list[tuple[str, str]] = []  # (relation, relation_id)

        # ── 1. Frontmatter edges: block (the canonical taught format) ────────
        fm_edges = fm.get("edges")
        if isinstance(fm_edges, list):
            for i, edge in enumerate(fm_edges):
                if not isinstance(edge, dict):
                    hard_failures.append(
                        f"{rel_name}: edges[{i}] is not a mapping "
                        "(expected relation / relation-id / target / target-id)"
                    )
                    continue
                relation = str(edge.get("relation", "") or "").strip()
                relation_id = str(
                    edge.get("relation-id", edge.get("relation_id", "")) or ""
                ).strip()
                target = str(edge.get("target", "") or "").strip()
                if not relation:
                    hard_failures.append(f"{rel_name}: edges[{i}] has an empty relation")
                    continue
                if not target:
                    hard_failures.append(f"{rel_name}: edges[{i}] has an empty target")
                    continue
                total_edges += 1
                used_relations.append((relation, relation_id))

        # ── 2. Inline [[Target | relation]] shorthand in the body ───────────
        prose = CODE_BLOCK_RE.sub("", body)
        for link_text in INLINE_LINK_RE.findall(prose):
            if "|" not in link_text:
                warnings.append(
                    f"{rel_name}: untyped wikilink [[{link_text.strip()}]] — "
                    "consider the typed form [[Target | relation]]"
                )
                continue
            target, _, relation = link_text.partition("|")
            target, relation = target.strip(), relation.strip()
            if not target:
                hard_failures.append(f"{rel_name}: [[{link_text}]] has an empty target")
            elif not relation:
                hard_failures.append(f"{rel_name}: [[{link_text}]] has an empty relation")
            else:
                total_edges += 1
                used_relations.append((relation, ""))

        # ── 3. Relation-name vocabulary check (soft) ─────────────────────────
        for relation, relation_id in used_relations:
            if not vocab:
                break
            if relation in vocab:
                expected_id = vocab[relation]
                if relation_id and re.fullmatch(r"[A-Z]{2}-\d{3}", relation_id) \
                        and relation_id != expected_id:
                    warnings.append(
                        f"{rel_name}: relation '{relation}' has id '{relation_id}' "
                        f"but the vocabulary says '{expected_id}'"
                    )
                continue
            suggestion = difflib.get_close_matches(relation, vocab.keys(), n=1)
            hint = f" — did you mean '{suggestion[0]}'?" if suggestion else ""
            warnings.append(
                f"{rel_name}: relation '{relation}' is not in the built-in "
                f"vocabulary{hint} (custom relations are allowed — "
                "just make sure this one is intentional)"
            )

    print(f"Found {total_edges} edges (frontmatter blocks + inline shorthand).")

    # ── 4. Per-phase expected nodes ───────────────────────────────────────────
    if phase is not None:
        key = normalize_phase(phase)
        keys = ["1a", "1b"] if key == "1" else [key]
        if any(k not in PHASE_MANIFESTS for k in keys):
            print(
                f"Error: unknown phase '{phase}' "
                f"(expected one of: {', '.join(sorted(PHASE_MANIFESTS))})",
                file=sys.stderr,
            )
            return False
        titles_lower = {t.lower() for t in titles}
        for k in keys:
            missing = [t for t in PHASE_MANIFESTS[k] if t.lower() not in titles_lower]
            if missing:
                hard_failures.append(
                    f"phase {k}: missing expected vault node(s): "
                    + ", ".join(f"'{t}'" for t in missing)
                )
            else:
                print(f"Phase {k} node manifest PASSED ({len(PHASE_MANIFESTS[k])} nodes present).")

    # ── 5. Global node-count check (--full only) ─────────────────────────────
    if full:
        if len(nodes) < 50:
            hard_failures.append(
                f"full-vault check: found {len(nodes)} nodes (minimum 50 required)"
            )
        else:
            print("Node count validation PASSED (>= 50).")

    # ── Report ────────────────────────────────────────────────────────────────
    if warnings:
        print(f"\n{len(warnings)} warning(s):")
        for w in warnings[:20]:
            print(f"  warning: {w}")
        if len(warnings) > 20:
            print(f"  ... and {len(warnings) - 20} more.")

    if hard_failures:
        print(f"\n{len(hard_failures)} hard failure(s):")
        for f in hard_failures[:20]:
            print(f"  FAIL: {f}")
        if len(hard_failures) > 20:
            print(f"  ... and {len(hard_failures) - 20} more.")
        return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate an Akanga vault directory.")
    parser.add_argument("vault", help="Path to the vault directory")
    parser.add_argument(
        "--phase",
        metavar="N",
        default=None,
        help="Check the phase's expected vault nodes (0, 1a, 1b, 2..8; '1' checks both 1a and 1b)",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Also enforce the global >= 50 node-count check",
    )
    args = parser.parse_args()

    if validate_vault(args.vault, phase=args.phase, full=args.full):
        print("\nOverall Vault Validation: PASSED")
        sys.exit(0)
    else:
        print("\nOverall Vault Validation: FAILED")
        sys.exit(1)


if __name__ == "__main__":
    main()
