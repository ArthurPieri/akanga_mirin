"""Phase 00 test suite — Filesystem as Database.

Tests the learner's parser module, which must live at AKANGA_SRC/parser.py
(or AKANGA_SRC/akanga_core/parser.py).  The module must export:

    parse(path) -> Node
    write(node, path)
    create(title, type, vault) -> Node
    hash(path) -> str

The Node dataclass fields tested here:
    id        — string UUID written into frontmatter; generated on create
    title     — str
    type      — str (e.g. "note")
    tags      — list[str]
    body      — str  (markdown body, everything after frontmatter)
    path      — Path or str — the file path the node was loaded from

All imports happen inside test functions (or the _parser fixture) so that
the AKANGA_SRC sys.path insertion from conftest runs first.
"""
from __future__ import annotations

import hashlib
import os
import uuid
from pathlib import Path
from textwrap import dedent

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_parser():
    """Import the learner's parser module.

    Tries ``parser`` first (flat layout), then ``akanga_core.parser``
    (package layout).  Raises ImportError with a helpful message if neither
    is found.
    """
    try:
        import parser as _p  # noqa: PLC0415
        # Guard against accidentally importing the built-in 'parser' module
        # that existed in Python < 3.9 — it never had a 'parse' function.
        if not hasattr(_p, "parse") and not hasattr(_p, "parse_node_file"):
            raise ImportError("built-in parser stub, not learner code")
        return _p
    except ImportError:
        pass

    try:
        import akanga_core.parser as _p  # noqa: PLC0415
        return _p
    except ImportError:
        pass

    pytest.fail(
        "Could not import a parser module from AKANGA_SRC.\n"
        "Expected one of:\n"
        "  $AKANGA_SRC/parser.py\n"
        "  $AKANGA_SRC/akanga_core/parser.py\n"
        "Make sure your file exists and has no syntax errors."
    )


def _get_fn(mod, *names):
    """Return the first attribute found in *names*, or fail with a clear message."""
    for name in names:
        fn = getattr(mod, name, None)
        if fn is not None:
            return fn
    pytest.fail(
        f"Parser module has none of the expected functions: {list(names)}.\n"
        f"Implement one of them in your parser.py."
    )


def _node_field(node, *names):
    """Return the first matching attribute from *node*, or fail."""
    for name in names:
        val = getattr(node, name, _MISSING)
        if val is not _MISSING:
            return val
    pytest.fail(
        f"Node object has none of the expected fields: {list(names)}.\n"
        f"Implement your Node dataclass with one of those field names."
    )


_MISSING = object()


def _make_md(tmp_path: Path, *, filename="node.md", **frontmatter_kwargs) -> Path:
    """Write a minimal valid .md file and return its path."""
    fm_lines = ["---"]
    for key, value in frontmatter_kwargs.items():
        if isinstance(value, list):
            fm_lines.append(f"{key}:")
            for item in value:
                fm_lines.append(f"  - {item}")
        else:
            fm_lines.append(f"{key}: {value}")
    fm_lines += ["---", "", "Body content here."]
    node_file = tmp_path / filename
    node_file.write_text("\n".join(fm_lines) + "\n", encoding="utf-8")
    return node_file


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def parser():
    """The learner's parser module, imported once per test module."""
    return _load_parser()


@pytest.fixture(scope="module")
def parse_fn(parser):
    """The learner's parse / parse_node_file function."""
    return _get_fn(parser, "parse", "parse_node_file")


@pytest.fixture(scope="module")
def write_fn(parser):
    """The learner's write / write_node_file function."""
    return _get_fn(parser, "write", "write_node_file")


@pytest.fixture(scope="module")
def hash_fn(parser):
    """The learner's hash / content_hash function."""
    return _get_fn(parser, "hash", "content_hash")


@pytest.fixture(scope="module")
def create_fn(parser):
    """The learner's create function."""
    return _get_fn(parser, "create")


# ---------------------------------------------------------------------------
# Happy-path tests
# ---------------------------------------------------------------------------

def test_parse_basic_frontmatter(tmp_path, parse_fn):
    """Parse a well-formed file and verify all core fields are returned."""
    node_file = _make_md(
        tmp_path,
        id="a3f7c2be-1234-5678-abcd-ef0123456789",
        title="Test Node",
        type="note",
        tags=["test", "example"],
    )

    node = parse_fn(str(node_file))

    node_id = _node_field(node, "id")
    assert str(node_id) == "a3f7c2be-1234-5678-abcd-ef0123456789", (
        f"Expected id 'a3f7c2be-1234-5678-abcd-ef0123456789', got {node_id!r}"
    )

    node_title = _node_field(node, "title")
    assert node_title == "Test Node", f"Expected title 'Test Node', got {node_title!r}"

    node_type = _node_field(node, "type")
    assert str(node_type) == "note", f"Expected type 'note', got {node_type!r}"

    node_tags = _node_field(node, "tags")
    assert set(node_tags) == {"test", "example"}, (
        f"Expected tags {{'test', 'example'}}, got {node_tags!r}"
    )


def test_parse_generates_uuid_when_missing(tmp_path, parse_fn):
    """When frontmatter has no 'id', the parser must generate a UUID."""
    node_file = _make_md(tmp_path, title="No ID Node", type="note")

    node = parse_fn(str(node_file))

    node_id = _node_field(node, "id")
    assert node_id, "Expected a generated id, got empty/None"
    # Must be a valid UUID format
    try:
        uuid.UUID(str(node_id))
    except ValueError:
        pytest.fail(
            f"Generated id {node_id!r} is not a valid UUID. "
            "Use uuid.uuid4() to generate node ids."
        )


def test_parse_invalid_uuid_replaced(tmp_path, parse_fn):
    """When 'id' is not a valid UUID string, the parser must generate a new one."""
    node_file = _make_md(tmp_path, id="not-a-uuid", title="Bad ID Node", type="note")

    node = parse_fn(str(node_file))

    node_id = _node_field(node, "id")
    try:
        parsed_uuid = uuid.UUID(str(node_id))
    except ValueError:
        pytest.fail(
            f"After replacing an invalid id, got {node_id!r} which is still not a valid UUID."
        )
    assert str(parsed_uuid) != "not-a-uuid", (
        "The invalid id 'not-a-uuid' was not replaced with a generated UUID."
    )


def test_content_hash_matches_sha256(tmp_path, hash_fn):
    """content_hash / hash must return the SHA-256 hex digest of the file bytes."""
    node_file = tmp_path / "hash-test.md"
    known_content = b"---\ntitle: Hash Test\ntype: note\n---\n\nBody.\n"
    node_file.write_bytes(known_content)

    expected = hashlib.sha256(known_content).hexdigest()
    actual = hash_fn(str(node_file))

    assert actual == expected, (
        f"Expected SHA-256 {expected!r}, got {actual!r}.\n"
        "Read the file in binary mode and use hashlib.sha256."
    )


def test_content_hash_changes_on_edit(tmp_path, hash_fn):
    """The hash must change whenever the file content changes."""
    node_file = tmp_path / "hash-change-test.md"
    node_file.write_text("---\ntitle: Original\ntype: note\n---\n\nOriginal body.\n", encoding="utf-8")

    hash_before = hash_fn(str(node_file))

    node_file.write_text("---\ntitle: Original\ntype: note\n---\n\nEdited body.\n", encoding="utf-8")

    hash_after = hash_fn(str(node_file))

    assert hash_before != hash_after, (
        "Hash did not change after editing the file. "
        "The hash must reflect the current file content."
    )


def test_write_node_file_roundtrip(tmp_path, parse_fn, write_fn):
    """write then parse must produce an identical node (idempotence)."""
    node_file = _make_md(
        tmp_path,
        id="b2c3d4e5-abcd-ef01-2345-678901234567",
        title="Roundtrip Node",
        type="note",
        tags=["alpha", "beta"],
    )

    first_parse = parse_fn(str(node_file))

    # write accepts either (node, path) or (path, frontmatter_dict, content)
    try:
        write_fn(first_parse, str(node_file))
    except TypeError:
        # Alternate signature: write_node_file(path, frontmatter_dict, content)
        fm = _node_field(first_parse, "frontmatter")
        body = _node_field(first_parse, "body", "content")
        write_fn(str(node_file), fm, body)

    second_parse = parse_fn(str(node_file))

    assert str(_node_field(second_parse, "id")) == str(_node_field(first_parse, "id")), (
        "id changed after write → parse. The UUID must be preserved."
    )
    assert _node_field(second_parse, "title") == _node_field(first_parse, "title"), (
        "title changed after write → parse."
    )
    assert str(_node_field(second_parse, "type")) == str(_node_field(first_parse, "type")), (
        "type changed after write → parse."
    )
    assert set(_node_field(second_parse, "tags")) == set(_node_field(first_parse, "tags")), (
        "tags changed after write → parse."
    )


def test_write_is_atomic(tmp_path, parse_fn, write_fn):
    """After a successful write, no .md.tmp files must remain in the directory."""
    node_file = _make_md(
        tmp_path,
        id="c3d4e5f6-bcde-f012-3456-789012345678",
        title="Atomic Write Node",
        type="note",
    )

    node = parse_fn(str(node_file))

    try:
        write_fn(node, str(node_file))
    except TypeError:
        fm = _node_field(node, "frontmatter")
        body = _node_field(node, "body", "content")
        write_fn(str(node_file), fm, body)

    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], (
        f"Temp file(s) left behind after write: {tmp_files}.\n"
        "Use os.replace(tmp, target) to atomically move the temp file."
    )


def test_failed_replace_preserves_original_file(tmp_path, parse_fn, write_fn, monkeypatch):
    """A write that dies at the rename step must leave the previous version intact.

    Fault injection (adversarial-analysis-v3 finding #11): round 3 showed that
    a plain ``write_text()`` passes the leftover-tmp atomicity check — this
    test makes atomicity falsifiable. We patch os.replace / os.rename /
    Path.replace / Path.rename to raise (simulating a crash or full disk at
    the commit step), attempt to overwrite an EXISTING file with NEW content,
    and assert the original bytes survive. Patching os.replace itself keeps
    the test universal: it works whether the temp file lives in the same
    directory, /tmp, or anywhere else.
    """
    node_file = _make_md(
        tmp_path,
        id="e9f0a1b2-3456-7890-abcd-ef1234567890",
        title="Original Title",
        type="note",
    )
    original_text = node_file.read_text(encoding="utf-8")

    node = parse_fn(str(node_file))

    # Mutate the node (best effort across Node shapes) so a NON-atomic write
    # would visibly change the file — writing back identical bytes would let
    # a plain write_text() implementation pass undetected.
    new_title = "DESTROYED BY FAILED WRITE"
    try:
        node.title = new_title
    except Exception:
        try:
            object.__setattr__(node, "title", new_title)
        except Exception:
            pass
    fm = getattr(node, "frontmatter", None)
    if isinstance(fm, dict):
        fm["title"] = new_title

    def _boom(*args, **kwargs):
        raise OSError("Injected fault: power loss at the rename step")

    # Patch every rename/replace spelling so the commit step fails no matter
    # how the implementation moves the temp file into place.
    monkeypatch.setattr(os, "replace", _boom)
    monkeypatch.setattr(os, "rename", _boom)
    monkeypatch.setattr(Path, "replace", _boom)
    monkeypatch.setattr(Path, "rename", _boom)

    def _call_write():
        try:
            write_fn(node, str(node_file))
        except TypeError:
            # Alternate signature: write_node_file(path, frontmatter_dict, content)
            fm_alt = _node_field(node, "frontmatter")
            body = _node_field(node, "body", "content")
            write_fn(str(node_file), fm_alt, body)

    # The injected OSError may propagate (correct: the caller learns the save
    # failed) or be handled internally — either way the file must be intact.
    try:
        _call_write()
    except Exception:
        pass

    assert node_file.read_text(encoding="utf-8") == original_text, (
        "The original file was corrupted or overwritten when the rename step "
        "failed.\n"
        "a failed write must never destroy the previous version — that is the "
        "whole point of temp+rename: write the FULL new content to a temp "
        "file (same directory, same filesystem), then os.replace(tmp, target) "
        "as the single atomic commit step. If this test changed your file, "
        "you are writing directly to the target (e.g. write_text) — a crash "
        "mid-write leaves a truncated or half-new note, and a crash before "
        "the write leaves you with nothing."
    )


def test_parse_tags_as_list(tmp_path, parse_fn):
    """Tags from frontmatter must be returned as a list of strings."""
    node_file = _make_md(
        tmp_path,
        id="d4e5f6a7-cdef-0123-4567-890123456789",
        title="Tagged Node",
        type="note",
        tags=["foo", "bar", "baz"],
    )

    node = parse_fn(str(node_file))

    tags = _node_field(node, "tags")
    assert isinstance(tags, list), (
        f"Expected tags to be a list, got {type(tags).__name__!r}. "
        "frontmatter.get('tags', []) returns a list."
    )
    assert all(isinstance(t, str) for t in tags), (
        f"All tags must be strings, got {tags!r}"
    )
    assert set(tags) == {"foo", "bar", "baz"}, (
        f"Expected tags {{'foo', 'bar', 'baz'}}, got {tags!r}"
    )


def test_parse_default_type_is_note(tmp_path, parse_fn):
    """A file without a 'type' field must default to type 'note'."""
    content = dedent("""\
        ---
        id: e5f6a7b8-def0-1234-5678-901234567890
        title: No Type Node
        ---

        Body.
        """)
    node_file = tmp_path / "no-type.md"
    node_file.write_text(content, encoding="utf-8")

    node = parse_fn(str(node_file))

    node_type = _node_field(node, "type")
    assert str(node_type) == "note", (
        f"Expected default type 'note', got {node_type!r}. "
        "Use: type = frontmatter.get('type', 'note')"
    )


def test_parse_note_type(tmp_path, parse_fn):
    """A file with 'type: note' must parse with type == 'note'."""
    node_file = _make_md(
        tmp_path,
        id="f6a7b8c9-ef01-2345-6789-012345678901",
        title="Explicit Note Type",
        type="note",
    )

    node = parse_fn(str(node_file))

    node_type = _node_field(node, "type")
    assert str(node_type) == "note", f"Expected type 'note', got {node_type!r}"


def test_parse_body_content(tmp_path, parse_fn):
    """The markdown body after frontmatter must be preserved in the node."""
    content = dedent("""\
        ---
        id: a7b8c9d0-f012-3456-7890-123456789012
        title: Body Test
        type: note
        ---

        This is the body.
        It has multiple lines.
        """)
    node_file = tmp_path / "body-test.md"
    node_file.write_text(content, encoding="utf-8")

    node = parse_fn(str(node_file))

    body = _node_field(node, "body", "content")
    assert "This is the body." in body, (
        f"Expected body to contain 'This is the body.', got {body!r}.\n"
        "Store the content after the frontmatter delimiter in node.body (or node.content)."
    )
    assert "multiple lines" in body, (
        f"Body appears truncated. Got {body!r}"
    )


# ---------------------------------------------------------------------------
# create() tests — the flagship deliverable of this phase
# ---------------------------------------------------------------------------

def _call_create(create_fn, *, title: str, node_type: str, vault):
    """Call the learner's create() accepting either keyword convention.

    Tries create(title=, type=, vault=) first (doc signature), then
    create(title=, node_type=, vault=) (skeleton signature), then positional.
    """
    try:
        return create_fn(title=title, type=node_type, vault=vault)
    except TypeError:
        pass
    try:
        return create_fn(title=title, node_type=node_type, vault=vault)
    except TypeError:
        pass
    return create_fn(title, node_type, vault)


def test_create_writes_file_with_fresh_uuid(tmp_vault, create_fn, parse_fn):
    """create() must write a .md file into the vault and stamp a fresh uuid4."""
    node = _call_create(
        create_fn, title="Fast Thinking is Unreliable", node_type="note", vault=tmp_vault
    )

    md_files = [p for p in tmp_vault.rglob("*.md")]
    assert md_files, (
        "create() must write a .md file into the vault directory, but no .md "
        f"file was found in {tmp_vault}.\n"
        "Derive a slug from the title (e.g. 'My Note' → 'my-note.md') and "
        "write it atomically with write_node_file."
    )

    node_path = _node_field(node, "path")
    assert node_path and Path(node_path).exists(), (
        f"create() returned a node whose path {node_path!r} does not exist on disk.\n"
        "Return parse_node_file(written_path) so node.path points at the real file."
    )

    parsed = parse_fn(str(node_path))
    parsed_id = _node_field(parsed, "id")
    try:
        parsed_uuid = uuid.UUID(str(parsed_id))
    except ValueError:
        pytest.fail(
            f"The id written by create() is not a valid UUID: {parsed_id!r}.\n"
            "Generate node ids with uuid.uuid4()."
        )
    assert parsed_uuid.version == 4, (
        f"create() must stamp a version-4 UUID (uuid.uuid4()), got version "
        f"{parsed_uuid.version} for {parsed_id!r}."
    )
    assert _node_field(parsed, "title") == "Fast Thinking is Unreliable", (
        f"Title written by create() does not survive a parse round-trip.\n"
        f"Expected 'Fast Thinking is Unreliable', got {_node_field(parsed, 'title')!r}."
    )


def test_create_stamps_author_from_vault_config(tmp_vault, create_fn, parse_fn):
    """create() must read akanga.yaml and stamp the vault owner as 'author'.

    The tmp_vault fixture writes an akanga.yaml with owner: 'Test User'.
    """
    node = _call_create(
        create_fn, title="Author Stamp Node", node_type="note", vault=tmp_vault
    )

    node_path = _node_field(node, "path")
    parsed = parse_fn(str(node_path))
    fm = _node_field(parsed, "frontmatter")
    assert isinstance(fm, dict), (
        f"node.frontmatter must be the raw YAML dict, got {type(fm).__name__!r}."
    )
    assert fm.get("author") == "Test User", (
        f"create() must stamp the vault owner from akanga.yaml as 'author' in "
        f"frontmatter. Expected author 'Test User', got {fm.get('author')!r}.\n"
        "Read the config with yaml.safe_load((vault / 'akanga.yaml').read_text()) "
        "and write config['owner'] into the frontmatter 'author' key."
    )


def test_create_roundtrip(tmp_vault, create_fn, parse_fn, write_fn):
    """create → parse → write → parse must preserve id, title, and content (doc Deliverable)."""
    node = _call_create(
        create_fn, title="Roundtrip via Create", node_type="note", vault=tmp_vault
    )

    node_path = _node_field(node, "path")
    parsed = parse_fn(str(node_path))

    assert str(_node_field(parsed, "id")) == str(_node_field(node, "id")), (
        "id changed between create() and parse(). The UUID written to "
        "frontmatter must be the one create() returns."
    )
    assert _node_field(parsed, "title") == _node_field(node, "title"), (
        "title changed between create() and parse()."
    )

    # write accepts either (node, path) or (path, frontmatter_dict, content)
    try:
        write_fn(parsed, str(node_path))
    except TypeError:
        fm = _node_field(parsed, "frontmatter")
        body = _node_field(parsed, "body", "content")
        write_fn(str(node_path), dict(fm), body)

    re_parsed = parse_fn(str(node_path))
    assert str(_node_field(re_parsed, "id")) == str(_node_field(parsed, "id")), (
        "id changed after write → parse. write_node_file must not rewrite the UUID."
    )
    assert _node_field(re_parsed, "title") == _node_field(parsed, "title"), (
        "title changed after write → parse — the write → parse cycle must be idempotent."
    )
    assert _node_field(re_parsed, "body", "content") == _node_field(parsed, "body", "content"), (
        "content changed after write → parse — the write → parse cycle must be idempotent."
    )


# ---------------------------------------------------------------------------
# Error-path tests  (CCR-9 requirement — at least one per phase)
# ---------------------------------------------------------------------------

def test_parse_nonexistent_file_raises(tmp_path, parse_fn):
    """Parsing a file that does not exist must raise an exception."""
    missing_path = tmp_path / "does-not-exist.md"
    assert not missing_path.exists(), "Precondition: file must not exist"

    with pytest.raises((FileNotFoundError, OSError, Exception)) as exc_info:
        parse_fn(str(missing_path))

    # Tighten the assertion: we expect a genuine IO error, not a generic crash
    exc = exc_info.value
    assert isinstance(exc, (FileNotFoundError, OSError)), (
        f"Expected FileNotFoundError or OSError for a missing file, got {type(exc).__name__}: {exc}"
    )


def test_write_node_file_to_nonexistent_dir_creates_it(tmp_path, parse_fn, write_fn):
    """Writing to a path inside a non-existent subdirectory must create the directory."""
    # First create a node we can write back
    source_file = _make_md(
        tmp_path,
        id="b8c9d0e1-0123-4567-8901-234567890123",
        title="Dir Creation Node",
        type="note",
    )
    node = parse_fn(str(source_file))

    new_dir = tmp_path / "subdir" / "nested"
    target_path = new_dir / "dir-creation-node.md"
    assert not new_dir.exists(), "Precondition: subdirectory must not exist yet"

    try:
        write_fn(node, str(target_path))
    except TypeError:
        fm = _node_field(node, "frontmatter")
        body = _node_field(node, "body", "content")
        write_fn(str(target_path), fm, body)

    assert new_dir.exists(), (
        f"Expected directory {new_dir} to be created, but it was not.\n"
        "Use os.makedirs(dir_path, exist_ok=True) before writing."
    )
    assert target_path.exists(), (
        f"Expected file {target_path} to exist after write, but it was not created."
    )


def test_malformed_frontmatter(tmp_path, parse_fn):
    """Parsing a file with malformed frontmatter must be handled (e.g., ScannerError)."""
    # Malformed YAML: missing closing quote on a multi-line string or invalid indentation
    content = dedent("""\
        ---
        title: "Malformed Title
        type: note
        ---

        Body.
        """)
    node_file = tmp_path / "malformed.md"
    node_file.write_text(content, encoding="utf-8")

    # We expect the parser to raise an exception when encountering malformed YAML.
    # frontmatter.ScannerError is the specific one, but we accept generic Exception
    # as long as it doesn't crash silently.
    with pytest.raises(Exception):
        parse_fn(str(node_file))
