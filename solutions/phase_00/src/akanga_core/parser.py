"""Phase 0 parser — the filesystem IS the database.

Every node in Akanga is one Markdown file with YAML frontmatter. This
module is the single boundary between raw files and typed `Node`
objects: nothing else in the system reads or writes `.md` files
directly. Four operations cover the whole lifecycle:

- `parse_node_file` — file → Node
- `write_node_file` — frontmatter + body → file (atomically)
- `content_hash`    — change detection for the Phase 2 indexer
- `create`          — mint a brand-new node inside a vault
"""
from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import frontmatter
import yaml

from .models import Node
from .textutil import slugify, unique_path


def parse_node_file(path: str) -> Node:
    """Parse a Markdown file with YAML frontmatter into a Node.

    Missing or invalid `id` values are replaced with a fresh uuid4 so
    every Node the system sees has a usable identity. `title` falls back
    to the filename stem, `type` defaults to "note", and the raw YAML
    dict is preserved unmodified in `node.frontmatter`.

    Raises FileNotFoundError for a missing file and lets YAML errors
    (e.g. ScannerError) propagate for malformed frontmatter.
    """
    post = frontmatter.load(path)
    fm: dict[str, Any] = post.metadata

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


def create(title: str, node_type: str, vault: str) -> Node:
    """Create a new node file in `vault` and return the parsed Node.

    Mints a fresh uuid4, stamps the vault owner from `akanga.yaml` as
    `author`, assigns the default workspace as `graph[0]`, slugs the
    title into a filename, writes the file atomically, and re-parses it
    so the returned Node reflects exactly what is on disk.
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
    default_workspace = config.get("default_workspace") or {}
    if default_workspace:
        fm["graph"] = [default_workspace]

    target = Path(unique_path(str(vault), slugify(title)))
    write_node_file(str(target), fm, "")
    return parse_node_file(str(target))
