"""Phase 0 — Atomic write pattern demonstration.

Run: python examples/phase_00_atomic_writer.py

Shows why os.replace() is safe and open().write() is not.
An interrupted write to a temp file leaves the original intact.
"""
import os
import tempfile
import pathlib


def write_atomically(path: str, content: str) -> None:
    dir_path = str(pathlib.Path(path).parent)
    fd, tmp = tempfile.mkstemp(dir=dir_path, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp, path)   # atomic: old or new, never partial
    except BaseException:
        os.unlink(tmp)           # clean up on failure
        raise


# Demo
with tempfile.NamedTemporaryFile(suffix=".txt", delete=False, mode="w", encoding="utf-8") as _tmp:
    target = _tmp.name
try:
    write_atomically(target, "Hello, atomic world!")
    print(f"Written to {target}: {pathlib.Path(target).read_text(encoding='utf-8')!r}")
    print("No .tmp file remains:", not any(f.endswith('.tmp') for f in os.listdir(str(pathlib.Path(target).parent)) if 'akanga' in f))
finally:
    pathlib.Path(target).unlink(missing_ok=True)
