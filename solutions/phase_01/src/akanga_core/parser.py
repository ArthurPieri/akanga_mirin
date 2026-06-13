"""Markdown + YAML frontmatter parsing, atomic writes, and edge write-back.

Every piece of information in Akanga is stored as a ``.md`` file on disk, and
this module is the single boundary between those raw files and the typed
:class:`~akanga_core.models.Node` objects the rest of the system works with.
Nothing reads node files directly — it always goes through the parser.

Phase 0 surface (unchanged contract):

- :func:`parse_node_file` — file → ``Node``
- :func:`write_node_file` — frontmatter dict + body → file (atomic)
- :func:`content_hash`   — SHA-256 of the raw file bytes
- :func:`create`         — mint a new node file in a vault

Phase 1 additions:

- :func:`extract_inline_edges` — find ``[[Target | relation]]`` in prose (1A)
- :func:`merge_edges`          — dedupe inline edges into frontmatter (1A)
- :func:`write_back`           — the save-path pipeline tying them together (1A)
- :func:`create` grows reference-node support (``url`` / ``external_type`` /
  ``description`` top-level frontmatter keys) (1B)
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import re
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import frontmatter
import yaml

from .models import Edge, Node

# Matches the inline edge shorthand: [[Target Title | relation-name]].
# Group 1 = target title (no ']' or '|'), group 2 = relation name (no ']').
# A plain wikilink [[Target]] has no pipe and therefore never matches.
_INLINE_EDGE_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")

# Matches fenced code blocks and inline code spans so example syntax inside
# ``` fences or `backticks` is ignored.
_FENCED_CODE_RE = re.compile(r"```.*?```", re.DOTALL)
_INLINE_CODE_RE = re.compile(r"`[^`]+`")

# THE wikilink pipe grammar (single source). A pipe segment is a RELATION only
# when it is slug-shaped after stripping; anything else (spaces, uppercase, a
# leading digit, punctuation, an escaped `\|`) is an Obsidian-style display
# alias and yields a plain wikilink, not a typed edge.
RELATION_SLUG_RE = re.compile(r"^[a-z][a-z0-9_-]*$")

# Characters allowed in a filename slug after lowercasing and hyphenating.
_SLUG_STRIP_RE = re.compile(r"[^a-z0-9\-_]")


def split_pipe_segment(segment: str) -> tuple[str, str]:
    """Classify the text after a wikilink pipe: relation vs display alias.

    Returns ``("relation", slug)`` when ``segment`` (after stripping) matches
    ``^[a-z][a-z0-9_-]*$`` — a lowercase slug such as ``supports`` or
    ``relates-to``. Otherwise returns ``("alias", text)``: spaces, uppercase, a
    leading digit, or punctuation all mean an Obsidian-style display alias,
    which is NOT a typed relation. Callers detect an escaped ``\\|`` first.
    """
    text = segment.strip()
    if RELATION_SLUG_RE.match(text):
        return ("relation", text)
    return ("alias", text)


# ---------------------------------------------------------------------------
# Phase 0 surface
# ---------------------------------------------------------------------------

def parse_node_file(path: str | Path) -> Node:
    """Parse a Markdown file with YAML frontmatter and return a :class:`Node`.

    Contract details that matter downstream:

    - ``title`` falls back to the filename stem when frontmatter omits it.
    - ``type`` defaults to ``"note"`` (plain string — no enum).
    - ``id`` is always a *valid UUID string*: a missing or malformed id is
      replaced with a fresh ``uuid4()``. Later phases key every DB row and
      edge on this id, so the parser is where validity is enforced.
    - ``content_hash`` stays ``""`` — the Phase 2 indexer fills it.
    - Malformed YAML raises (``yaml.scanner.ScannerError`` via
      ``frontmatter.load``); a missing file raises ``FileNotFoundError``.
      Callers must never receive a half-parsed node.
    """
    path = Path(path)
    post = frontmatter.load(str(path))
    metadata: dict[str, Any] = dict(post.metadata)

    title = str(metadata.get("title") or path.stem)
    node_type = str(metadata.get("type") or "note")

    try:
        node_id = str(UUID(str(metadata.get("id"))))
    except (ValueError, TypeError):
        # Missing or invalid id — mint a fresh one. The file on disk is NOT
        # rewritten here; persisting the id is a write-path concern.
        node_id = str(uuid4())

    raw_tags = metadata.get("tags") or []
    tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [str(raw_tags)]

    return Node(
        id=node_id,
        title=title,
        type=node_type,
        tags=tags,
        content=post.content,
        path=str(path),
        frontmatter=metadata,
    )


def content_hash(path: str | Path) -> str:
    """Compute the SHA-256 hex digest of the raw bytes of the file at *path*.

    The Phase 2 indexer compares this hash before re-parsing, so no-op editor
    saves (which still fire file-watcher events) never trigger a re-index.
    Hashing bytes — not decoded text — keeps the digest exact and cheap.
    """
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def write_node_file(path: str | Path, frontmatter_dict: dict[str, Any], content: str) -> None:
    """Serialize *frontmatter_dict* + *content* to *path* with an atomic write.

    Node files are the source of truth for all data, so a crash mid-write must
    never leave a half-written file behind. The write goes to a temp file in
    the SAME directory (same filesystem — a requirement for atomic rename) and
    is swapped into place with ``os.replace``, which is atomic at the OS
    level. On any failure the temp file is removed and the original file is
    left untouched.
    """
    path = str(path)
    post = frontmatter.Post(content, **frontmatter_dict)

    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(frontmatter.dumps(post))
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


# ---------------------------------------------------------------------------
# Phase 1A — inline edges and write-back
# ---------------------------------------------------------------------------

def extract_inline_edges(body: str) -> list[Edge]:
    """Find all ``[[Target | relation]]`` patterns in *body* as :class:`Edge` objects.

    Inline edge shorthand lets users write relationships naturally inside
    prose — "See also ``[[Architecture | documents]]``" — without switching
    to frontmatter. This is step one of the write-back pipeline: extract
    here, then :func:`merge_edges` into frontmatter.

    Three deliberate exclusions:

    - Fenced code blocks and inline code spans are stripped first, so example
      syntax inside ``` fences or `backticks` is never mistaken for a real edge.
    - Plain wikilinks (``[[Target]]`` with no pipe) carry no relation and
      therefore produce no edges.
    - The pipe grammar (:func:`split_pipe_segment`) decides what counts: only a
      slug-shaped segment is a relation. A display alias (``[[Note | My
      Alias]]``) or an escaped pipe (``[[Note \\| text]]``) is NOT a typed edge —
      it stays a plain wikilink.

    ``relation_id`` and ``target_id`` are left empty — resolving them is the
    resolver/sync-queue's job, not the extractor's.
    """
    stripped = _INLINE_CODE_RE.sub("", _FENCED_CODE_RE.sub("", body))
    edges: list[Edge] = []
    for target, segment in _INLINE_EDGE_RE.findall(stripped):
        if target.endswith("\\"):
            continue  # escaped pipe → display alias, never a relation
        kind, slug = split_pipe_segment(segment)
        if kind == "relation":
            edges.append(
                Edge(relation=slug, relation_id="", target=target.strip(), target_id="")
            )
    return edges


def merge_edges(existing: list[Edge], inline: list[Edge]) -> list[Edge]:
    """Combine frontmatter edges with inline edges, deduplicating by (relation, target).

    Frontmatter is the source of truth: inline edges are synced INTO it, never
    over it. When an inline edge duplicates an existing (relation, target)
    pair, the existing entry wins outright — in particular its resolved
    ``target_id`` is preserved, because re-resolution is expensive and a
    conflicting inline id is a sign of stale prose. ``target_id`` is excluded
    from the dedup key for exactly this reason: an unresolved inline edge
    (``target_id=""``) must dedupe against its resolved frontmatter twin.

    Ordering: existing edges first (original order), then new inline edges in
    appearance order — so repeated merges are stable and idempotent.
    """
    seen: dict[tuple[str, str], Edge] = {(e.relation, e.target): e for e in existing}
    for edge in inline:
        seen.setdefault((edge.relation, edge.target), edge)
    return list(seen.values())


def _edge_from_dict(raw: dict[str, Any]) -> Edge:
    """Build an :class:`Edge` from a frontmatter dict entry.

    Accepts both underscored (``relation_id``) and hyphenated
    (``relation-id``) key spellings so hand-authored vaults following either
    convention parse identically. Missing keys default to ``""``.
    """
    def get(key: str) -> str:
        value = raw.get(key, raw.get(key.replace("_", "-"), ""))
        return str(value) if value is not None else ""

    return Edge(
        relation=get("relation"),
        relation_id=get("relation_id"),
        target=get("target"),
        target_id=get("target_id"),
    )


def _edge_to_dict(edge: Edge) -> dict[str, str]:
    """Serialize an :class:`Edge` to the frontmatter ``edges:`` entry shape."""
    return {
        "relation": edge.relation,
        "relation_id": edge.relation_id,
        "target": edge.target,
        "target_id": edge.target_id,
    }


def write_back(path: str | Path) -> None:
    """Sync inline prose edges into the frontmatter ``edges:`` list of one file.

    Called by the file-watcher handler after every save, so it must be both
    idempotent and safe:

    - **Idempotent**: merging is keyed on (relation, target), and the file is
      only rewritten when the merged list actually differs from what is
      already in frontmatter. A second call on an unchanged file is a no-op.
    - **Safe**: parsing happens FIRST. If the frontmatter YAML is malformed,
      :func:`parse_node_file` raises and this function never writes — a
      broken file is left byte-for-byte untouched rather than "fixed" into
      data loss. The eventual write is atomic (:func:`write_node_file`).
    """
    node = parse_node_file(path)

    raw_edges = node.frontmatter.get("edges") or []
    existing = [_edge_from_dict(raw) for raw in raw_edges]
    inline = extract_inline_edges(node.content)
    merged = merge_edges(existing, inline)

    if merged == existing:
        return

    node.frontmatter["edges"] = [_edge_to_dict(edge) for edge in merged]
    write_node_file(path, node.frontmatter, node.content)


# ---------------------------------------------------------------------------
# Phase 0 create(), extended in 1B for reference nodes
# ---------------------------------------------------------------------------

def _slugify(title: str) -> str:
    """Convert a node title to a filename-safe slug.

    Lowercase, spaces to hyphens, then strip anything outside
    ``[a-z0-9-_]``. ``"Fast Thinking is Unreliable"`` →
    ``"fast-thinking-is-unreliable"``.
    """
    slug = _SLUG_STRIP_RE.sub("", title.lower().replace(" ", "-")).strip("-")
    return slug or "untitled"


def create(
    title: str,
    node_type: str,
    vault: str | Path,
    url: str = "",
    external_type: str = "",
    description: str = "",
) -> Node:
    """Create a new node file in *vault* and return the parsed :class:`Node`.

    The single entry point for minting knowledge-graph nodes. It stamps a
    fresh ``uuid4()`` id and the vault owner (from ``akanga.yaml``) as
    ``author``, derives a slug filename from the title, writes the file
    atomically, and returns the result of re-parsing the written file — so
    the returned ``Node.path`` always points at a real on-disk file and the
    round-trip (create → parse) is verified by construction.

    Phase 1B extends this for **reference nodes**: when
    ``node_type == "reference"``, the three top-level frontmatter keys
    ``url``, ``external_type``, and ``description`` are written so the node
    can point at an external resource (webpage, paper, repo).
    """
    vault = Path(vault)

    config: dict[str, Any] = {}
    config_path = vault / "akanga.yaml"
    if config_path.exists():
        config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}

    fm: dict[str, Any] = {
        "id": str(uuid4()),
        "title": title,
        "type": node_type,
        "tags": [],
        "author": str(config.get("owner", "")),
    }
    # Workspace membership (Phase 0 behavior, formalized in 1B): every new node
    # joins the vault's default workspace, recorded as a name+id pair — the same
    # dual-key pattern edges use, so a workspace rename never breaks membership.
    default_workspace = config.get("default_workspace") or {}
    if default_workspace:
        fm["graph"] = [default_workspace]
    if node_type == "reference":
        fm["url"] = url
        fm["external_type"] = external_type
        fm["description"] = description

    node_path = vault / f"{_slugify(title)}.md"
    write_node_file(node_path, fm, "")
    return parse_node_file(node_path)
