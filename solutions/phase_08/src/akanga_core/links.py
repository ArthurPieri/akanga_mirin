from __future__ import annotations

import re
from pathlib import Path


def extract_edges(content: str) -> list[tuple[str, str]]:
    """
    Extract edges from content.
    Matches [[Target | relation]] or [[Target]].
    Default relation is 'mentions'.
    Returns a list of (target, relation).
    """
    # Regex to find [[Target | relation]] or [[Target]]
    # Group 1: Target (everything until | or ]])
    # Group 2: relation (optional, everything after | until ]])
    pattern = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
    matches = pattern.findall(content)

    edges = []
    for target, relation in matches:
        target = target.strip()
        relation = relation.strip() if relation else "mentions"
        if target:
            edges.append((target, relation))
    return edges


def resolve_path(vault_root: str | Path, current_path: str | Path, target: str) -> Path:
    """
    Resolve the link target to an absolute Path.
    """
    vault_root = Path(vault_root).absolute()
    current_path = Path(current_path).absolute()

    # Link targets usually refer to .md files, which might or might not have extensions in the link.
    target_p = Path(target)
    possible_targets = [target_p]
    if target_p.suffix != ".md":
        possible_targets.append(target_p.with_suffix(".md"))

    # 1. Try relative to current_path's directory
    for pt in possible_targets:
        try:
            try_path = (current_path.parent / pt).resolve()
            if try_path.exists() and try_path.is_relative_to(vault_root):
                return try_path
        except (ValueError, OSError):
            continue

    # 2. Try relative to vault root
    for pt in possible_targets:
        try:
            try_path = (vault_root / pt).resolve()
            if try_path.exists() and try_path.is_relative_to(vault_root):
                return try_path
        except (ValueError, OSError):
            continue

    # 3. Fallback: absolute path from vault root (might not exist yet)
    # Ensure it ends with .md if it's a note link
    if target_p.suffix != ".md":
        target_p = target_p.with_suffix(".md")
    return (vault_root / target_p).absolute()
