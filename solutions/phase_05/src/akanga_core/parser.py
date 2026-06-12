"""Parser — the single boundary between raw `.md` files and typed objects.

Every node in Akanga is one Markdown file with YAML frontmatter. Nothing
else in the system reads or writes `.md` files directly. The Phase 0
lifecycle quartet:

- `parse_node_file` — file → Node
- `write_node_file` — frontmatter + body → file (atomically)
- `content_hash`    — change detection for the Phase 2 indexer
- `create`          — mint a brand-new node inside a vault (Phase 1B adds
  reference-node parameters: `url` / `external_type` / `description`)

Phase 1A adds the inline-edge pipeline:

- `extract_inline_edges` — `[[Target | relation]]` prose shorthand → Edge list
- `merge_edges`          — dedupe inline edges into frontmatter (frontmatter wins)
- `write_back`           — sync inline edges into the frontmatter `edges:` block
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import re
import shutil
import tempfile
from datetime import date, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import frontmatter
import yaml

from .models import Edge, Node

# `[[Target | relation]]` — group 1 is the target title, group 2 the relation.
_INLINE_EDGE_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
# Fenced code blocks are stripped before edge extraction so that example
# syntax inside ``` fences is never mistaken for a real edge.
_CODE_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)


def _normalize_fm(value: Any) -> Any:
    """Recursively convert YAML-implicit date/datetime values to ISO strings.

    Bare YAML dates (``due: 2026-07-01``) parse to ``datetime.date`` — not
    JSON-serializable, and a different type than the string the author
    visually wrote. Normalizing at the parse boundary means every consumer
    downstream (DB, API, MCP, write-back) sees one type: str.
    """
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: _normalize_fm(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_normalize_fm(v) for v in value]
    return value


def parse_node_file(path: str) -> Node:
    """Parse a Markdown file with YAML frontmatter into a Node.

    Missing or invalid `id` values are replaced with a fresh uuid4 so
    every Node the system sees has a usable identity. `title` falls back
    to the filename stem, `type` defaults to "note", and the YAML dict
    is preserved in `node.frontmatter` with one normalization: implicit
    date/datetime values become ISO strings (see `_normalize_fm`).

    Raises FileNotFoundError for a missing file and lets YAML errors
    (e.g. ScannerError) propagate for malformed frontmatter.
    """
    post = frontmatter.load(path)
    fm: dict[str, Any] = _normalize_fm(post.metadata or {})

    raw_id = fm.get("id")
    try:
        node_id = str(UUID(str(raw_id)))
    except ValueError:
        node_id = str(uuid4())

    title = fm.get("title") or os.path.splitext(os.path.basename(path))[0]

    return Node(
        id=node_id,
        title=title,
        type=str(fm.get("type", "note")),
        tags=list(fm.get("tags") or []),
        content=post.content,
        path=path,
        frontmatter=fm,
    )


def content_hash(path: str) -> str:
    """Return the SHA-256 hex digest of the file's raw bytes.

    The indexer compares this hash to detect real content changes, so a
    no-op editor save never triggers a re-index. Hashing bytes (not
    decoded text) keeps the digest stable across encoding assumptions.
    """
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def write_node_file(path: str, frontmatter_dict: dict, content: str) -> None:
    """Serialize frontmatter + body to `path` with an atomic write.

    The file is written to a temp file in the SAME directory, fsynced,
    then swapped into place with `os.replace` — so a crash mid-write can
    never leave a half-written node behind. Parent directories are
    created as needed; on failure the temp file is always cleaned up.
    """
    post = frontmatter.Post(content, **frontmatter_dict)
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(frontmatter.dumps(post))
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        if os.path.exists(path):
            shutil.copymode(path, tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def create(
    title: str,
    node_type: str,
    vault: str | Path,
    url: str = "",
    external_type: str = "",
    description: str = "",
) -> Node:
    """Create a new node file in `vault` and return the parsed Node.

    Mints a fresh uuid4, stamps the vault owner from `akanga.yaml` as
    `author`, assigns the default workspace as `graph[0]`, slugs the
    title into a filename, writes the file atomically, and re-parses it
    so the returned Node reflects exactly what is on disk.

    Phase 1B: when `node_type == "reference"`, the three external-resource
    fields (`url`, `external_type`, `description`) are written as top-level
    frontmatter keys. They are never DB columns — the file keeps them.
    """
    config: dict[str, Any] = {}
    config_path = Path(vault) / "akanga.yaml"
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    fm: dict[str, Any] = {
        "id": str(uuid4()),
        "title": title,
        "type": node_type,
        "tags": [],
        "author": config.get("owner", ""),
    }
    if node_type == "reference":
        fm["url"] = url
        fm["external_type"] = external_type
        fm["description"] = description

    default_workspace = config.get("default_workspace") or {}
    if default_workspace:
        fm["graph"] = [default_workspace]

    slug = re.sub(r"[^a-z0-9-]", "", title.lower().replace(" ", "-")) or "untitled"
    target = Path(vault) / f"{slug}.md"
    write_node_file(str(target), fm, "")
    return parse_node_file(str(target))


# ---------------------------------------------------------------------------
# Phase 1A — inline edges and write-back
# ---------------------------------------------------------------------------


def extract_inline_edges(body: str) -> list[Edge]:
    """Find all `[[Target | relation]]` patterns in prose and return Edges.

    Fenced code blocks are stripped first so example syntax in ``` fences
    is ignored. Plain `[[Title]]` wikilinks (no pipe) are NOT inline edges
    and never match. `relation_id` and `target_id` are left empty — they
    are resolved later by the resolver and the sync queue.
    """
    stripped = _CODE_FENCE_RE.sub("", body)
    return [
        Edge(
            relation=relation.strip(),
            relation_id="",
            target=target.strip(),
            target_id="",
        )
        for target, relation in _INLINE_EDGE_RE.findall(stripped)
    ]


def merge_edges(existing: list[Edge], inline: list[Edge]) -> list[Edge]:
    """Combine frontmatter edges with inline edges, deduplicating.

    Edges are keyed by `(relation, target)`. Frontmatter wins: when a key
    already exists, the inline edge is skipped entirely so an already
    resolved `target_id` is never overwritten with an empty string (and a
    conflicting inline id never clobbers the resolved one).
    """
    seen: dict[tuple[str, str], Edge] = {(e.relation, e.target): e for e in existing}
    for edge in inline:
        key = (edge.relation, edge.target)
        if key not in seen:
            seen[key] = edge
    return list(seen.values())


def write_back(path: str | Path) -> None:
    """Sync inline prose edges into the frontmatter `edges:` block.

    Parse first; only write after a successful parse + merge — a file
    whose YAML cannot be parsed raises (from `parse_node_file`) and is
    left byte-for-byte untouched. When the merged list equals the
    existing one the write is skipped, making the operation idempotent.
    """
    node = parse_node_file(str(path))

    raw_edges = node.frontmatter.get("edges") or []
    existing = [
        Edge(
            relation=str(d.get("relation", "")),
            relation_id=str(d.get("relation_id", "")),
            target=str(d.get("target", "")),
            target_id=str(d.get("target_id", "")),
        )
        for d in raw_edges
        if isinstance(d, dict)
    ]

    inline = extract_inline_edges(node.content)
    merged = merge_edges(existing, inline)
    if merged == existing:
        return  # nothing changed — never rewrite a file for a no-op

    node.frontmatter["edges"] = [
        {
            "relation": e.relation,
            "relation_id": e.relation_id,
            "target": e.target,
            "target_id": e.target_id,
        }
        for e in merged
    ]
    write_node_file(str(path), node.frontmatter, node.content)
