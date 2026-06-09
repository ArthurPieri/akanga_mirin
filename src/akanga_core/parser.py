from __future__ import annotations

import os

import frontmatter

from .models import Node, NodeType
from datetime import datetime, timezone
from uuid import UUID, uuid4
import hashlib
import tempfile
import shutil


def parse_node_file(path: str) -> Node:
    """WHAT: Parse a Markdown file with YAML frontmatter and return a Node dataclass.

    WHY: Every piece of information in Akanga is stored as a `.md` file on disk.
    The parser is the single entry-point that converts raw files into the typed
    `Node` objects the rest of the system works with. Nothing reads files directly
    — they always go through this function first.

    HOW:
    1. Use `frontmatter.load(path)` to parse the file. It returns a `Post`
       object with `.metadata` (the YAML dict) and `.content` (the Markdown body).
    2. Extract `title` from metadata. If missing, fall back to the filename
       without its extension: `os.path.splitext(os.path.basename(path))[0]`.
    3. Extract `type` from metadata and wrap it in `NodeType(...)`. Default to
       `"note"` if the key is absent.
    4. Use `os.path.getctime(path)` and `os.path.getmtime(path)` (both wrapped
       with `datetime.fromtimestamp(..., UTC)`) for `created_at` and `updated_at`.
    5. Read the raw `id` field from metadata. Try to parse it with `UUID(str(raw_id))`.
       If it is missing or invalid, generate a fresh one with `uuid4()`.
    6. Construct and return a `Node(...)` with all the fields above, plus
       `tags=fm.get("tags", [])`, `frontmatter=fm`, and `content=post.content`.
    """
    post = frontmatter.load(path)
    metadata = post.metadata
    content = post.content

    title = metadata.get("title", None)
    if not title:
        title = os.path.splitext(os.path.basename(path))[0]
    title = str(title)

    note_type = metadata.get("type", None)
    if note_type not in NodeType._value2member_map_:
        note_type = None
    if not note_type:
        note_type = NodeType.note
    note_type = NodeType(note_type)

    created_at = os.path.getctime(path)
    created_at = datetime.fromtimestamp(created_at, tz=timezone.utc)
    if not created_at:
        created_at = datetime.now(tz=timezone.utc)

    updated_at = os.path.getmtime(path)
    updated_at = datetime.fromtimestamp(updated_at, tz=timezone.utc)
    if not updated_at:
        updated_at = created_at

    raw_id = metadata.get("id", None)
    try:
        id = UUID(str(raw_id))
    except Exception as exc:
        print("\n\n", exc, "\n\n")
        id = uuid4()

    return Node(
        id=id,
        path=path,
        title=title,
        type=note_type,
        tags=post.get("tags", []),  # type: ignore
        frontmatter=metadata,
        content=content,
        created_at=created_at,
        updated_at=updated_at,
    )


def content_hash(path: str) -> str:
    """WHAT: Compute a SHA-256 hex digest of the file at `path`.

    WHY: The indexer uses this hash to detect whether a file's contents have
    actually changed before re-parsing it. Without the hash check, every
    file-watcher event (including no-op saves from an editor) would trigger
    a full re-index of every watched file.

    HOW:
    1. Open the file in binary mode (`"rb"`).
    2. Read its entire contents with `.read()`.
    3. Pass the bytes to `hashlib.sha256(...)` and call `.hexdigest()` on the
       result.
    4. Return the hex string.
    """
    with open(path, "rb") as f:
        data = f.read()

    hash = hashlib.sha256(data)
    return hash.hexdigest()


def write_node_file(path: str, frontmatter_dict: dict, content: str) -> None:
    """WHAT: Serialize `frontmatter_dict` + `content` back to a Markdown file at `path`,
    using an atomic write so partial failures never corrupt the file.

    WHY: Akanga nodes are the source of truth for all data. A crash mid-write
    would leave a half-written file, corrupting the node and any edges that
    reference it. Writing to a temp file on the same filesystem and then
    calling `os.replace` makes the swap atomic at the OS level.

    HOW:
    1. Build a `frontmatter.Post(content, **frontmatter_dict)` object.
    2. Determine the directory of `path` with `os.path.dirname(path) or "."`.
       Call `os.makedirs(dir_path, exist_ok=True)` to ensure it exists.
    3. Create a temp file in the SAME directory as `path` using
       `tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")`. This returns
       `(fd, tmp_path)` where `fd` is an open file descriptor.
    4. Wrap the write in a try/except so the temp file is always cleaned up on
       failure:
         a. Open `fd` with `os.fdopen(fd, "w", encoding="utf-8")` and write
            `frontmatter.dumps(post)` to it.
         b. IMPORTANT: Call `os.fsync(fd)` before closing the file to ensure
            data is flushed to disk.
         c. If the original file exists, use `shutil.copymode(path, tmp_path)`
            to preserve permissions.
         d. Call `os.replace(tmp_path, path)` to atomically swap the file.
         e. On any `BaseException`, suppress OSError and call `os.unlink(tmp_path)`,
            then re-raise.
    """
    post = frontmatter.Post(content, **frontmatter_dict)

    dir_path = os.path.dirname(path)
    if not dir_path:
        dir_path = "."
    os.makedirs(dir_path, exist_ok=True)

    fd, temp_path = tempfile.mkstemp(dir=dir_path, suffix=".md.tmp")

    try:
        with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
            temp_file.write(frontmatter.dumps(post))
            os.fsync(fd)

        if os.path.isfile(path):
            shutil.copymode(path, temp_path)

        os.replace(temp_path, path)
    except Exception as exc:
        os.unlink(temp_path)
        raise exc


def create(title: str, node_type: str, vault: str) -> Node:
    """WHAT: Create a new Node file in vault and return the parsed Node.

    WHY: Provides a single entry point for creating new knowledge graph nodes.
    The function writes the file atomically (like write_node_file) and reads
    the vault config (akanga.yaml) to stamp the correct owner and default workspace.

    HOW:
    1. Generate a new UUID with uuid4().
    2. Read vault config: config_path = Path(vault) / "akanga.yaml". If the file exists,
       load it with `import yaml; yaml.safe_load(config_path.read_text())` — `pyyaml` is
       installed as a dependency of `python-frontmatter` so `import yaml` works. If the
       file is absent, use defaults (owner="", default_workspace={}).
    3. Build a Node with the given title, node_type, and a stub frontmatter dict.
    4. Convert the title to a filename-safe slug — e.g.
       `title.lower().replace(" ", "-") + ".md"` (strip any remaining special characters
       as needed). For example: "My Note" → "my-note.md".
       Write the file atomically to `Path(vault) / slug` using write_node_file.
    5. Return parse_node_file on the written file to get the final Node.
    """
    raise NotImplementedError(
        "Generate UUID, read akanga.yaml with yaml.safe_load (import yaml — available via "
        "python-frontmatter dep) for owner/workspace defaults, build Node, derive slug via "
        "title.lower().replace(' ', '-'), call write_node_file to persist it, "
        "return parse_node_file result."
    )
