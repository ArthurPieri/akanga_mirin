from __future__ import annotations

import contextlib
import hashlib
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

import frontmatter

from .models import Node

def parse_node_file(path: str) -> Node:
    """Parse a Markdown file with YAML frontmatter into a Node."""
    post = frontmatter.load(path)
    metadata = post.metadata
    
    title = metadata.get("title")
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
        
    # Use id from metadata or fall back to a hash of the path if not provided
    node_id = str(metadata.get("id", ""))
    if not node_id:
        node_id = hashlib.md5(path.encode()).hexdigest()

    return Node(
        id=node_id,
        title=title,
        path=str(Path(path).absolute()),
        body=post.content,
        frontmatter=metadata
    )

def content_hash(path: str) -> str:
    """Compute SHA-256 hash of file content."""
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()

def atomic_write(path: str, content: str) -> None:
    """Write content to path atomically using a temporary file."""
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

def write_node_file(path: str, frontmatter_dict: dict, content: str) -> None:
    """Serialize frontmatter and content to a file atomically."""
    post = frontmatter.Post(content, **frontmatter_dict)
    atomic_write(path, frontmatter.dumps(post))
