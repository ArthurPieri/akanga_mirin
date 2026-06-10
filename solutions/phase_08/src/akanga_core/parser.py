"""Markdown + YAML frontmatter parsing and atomic file writes.

The parser is the ONLY component that reads node prose. The database stores
metadata exclusively (Phase 2 rule / BUG-01), so anything that needs body
text — the RAG context builder, the API, the TUI — calls
:func:`parse_node_file` to read it from disk at use time.
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import frontmatter

from .models import ParsedNote


def parse_node_file(path: str | Path) -> ParsedNote:
    """Parse a Markdown file with YAML frontmatter into a :class:`ParsedNote`."""
    path = Path(path)
    post = frontmatter.load(str(path))
    metadata: dict[str, Any] = dict(post.metadata)

    title = str(metadata.get("title") or path.stem)
    node_id = str(metadata.get("id") or "")
    if not node_id:
        # Deterministic fallback so unidentified files still get a stable ID.
        node_id = hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:32]

    raw_tags = metadata.get("tags") or []
    tags = [str(t) for t in raw_tags] if isinstance(raw_tags, list) else [str(raw_tags)]

    return ParsedNote(
        id=node_id,
        title=title,
        type=str(metadata.get("type") or "note"),
        tags=tags,
        path=str(path.absolute()),
        content=post.content,
        frontmatter=metadata,
    )


def content_hash(path: str | Path) -> str:
    """Compute the SHA-256 hash of a file's raw bytes."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def atomic_write(path: str | Path, content: str) -> None:
    """Write *content* to *path* atomically via a temp file + os.replace."""
    path = str(path)
    dir_path = os.path.dirname(path) or "."
    os.makedirs(dir_path, exist_ok=True)

    fd, tmp_path = tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        if os.path.exists(path):
            shutil.copymode(path, tmp_path)
        os.replace(tmp_path, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp_path)
        raise


def write_node_file(path: str | Path, frontmatter_dict: dict[str, Any], content: str) -> None:
    """Serialize frontmatter + content and write the file atomically."""
    post = frontmatter.Post(content, **frontmatter_dict)
    atomic_write(path, frontmatter.dumps(post))
