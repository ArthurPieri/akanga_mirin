from pathlib import Path
import sys
import os

# Add the src directory to sys.path
sys.path.append(os.path.abspath("solutions/phase_08/src"))

from akanga_core.links import extract_edges, resolve_path

def test_extract_edges():
    content = "See [[Blink]] and [[Flow State | supports]] and [[Invalid | ]]."
    edges = extract_edges(content)
    print(f"Extracted edges: {edges}")
    assert ("Blink", "mentions") in edges
    assert ("Flow State", "supports") in edges
    assert ("Invalid", "mentions") in edges
    print("extract_edges test passed!")

def test_resolve_path(tmp_path):
    vault_root = tmp_path / "vault"
    vault_root.mkdir()
    
    note1 = vault_root / "note1.md"
    note1.write_text("content")
    
    sub = vault_root / "sub"
    sub.mkdir()
    note2 = sub / "note2.md"
    note2.write_text("content")
    
    # Test relative to current_path
    resolved = resolve_path(vault_root, note2, "note1.md")
    print(f"Resolved relative to current: {resolved}")
    assert resolved == note1.absolute()
    
    # Test relative to vault root
    resolved = resolve_path(vault_root, note1, "sub/note2.md")
    print(f"Resolved relative to vault root: {resolved}")
    assert resolved == note2.absolute()
    
    # Test without extension
    resolved = resolve_path(vault_root, note1, "sub/note2")
    print(f"Resolved without extension: {resolved}")
    assert resolved == note2.absolute()
    
    # Test fallback
    resolved = resolve_path(vault_root, note1, "nonexistent")
    print(f"Resolved fallback: {resolved}")
    assert resolved == (vault_root / "nonexistent.md").absolute()
    
    print("resolve_path test passed!")

if __name__ == "__main__":
    test_extract_edges()
    
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        test_resolve_path(Path(tmp))
