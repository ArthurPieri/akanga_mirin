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
