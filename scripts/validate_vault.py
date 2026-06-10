#!/usr/bin/env python3
"""
validate_vault.py — validate a learner's vault directory.

Usage:
    python scripts/validate_vault.py /path/to/vault
"""

import argparse
import re
import sys
from pathlib import Path

def validate_vault(vault_path: str) -> bool:
    path = Path(vault_path)
    if not path.is_dir():
        print(f"Error: {vault_path} is not a directory", file=sys.stderr)
        return False

    # 1. Count nodes (Markdown files)
    nodes = list(path.glob("**/*.md"))
    node_count = len(nodes)
    print(f"Found {node_count} nodes.")

    # 2. Check node count
    count_ok = node_count >= 50
    if not count_ok:
        print(f"Validation FAILED: Found {node_count} nodes (minimum 50 required).")
    else:
        print("Node count validation PASSED (>= 50).")

    # 3. Validate edges
    # Standard format: [[Target | relation]]
    # We strip code blocks first.
    _edge_pattern = re.compile  # documents the [[Target|relation]] format; per-relation validation TODO(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
    any_link_pattern = re.compile(r"\[\[([^\]]+)\]\]")
    
    total_edges = 0
    malformed_edges = []

    for node_file in nodes:
        try:
            content = node_file.read_text(encoding="utf-8")
            # Strip code blocks
            content = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
            
            # Find all [[...]] links
            all_links = any_link_pattern.findall(content)
            for link_text in all_links:
                if "|" not in link_text:
                    malformed_edges.append((node_file.name, link_text, "Missing relation (format: [[Target|relation]])"))
                else:
                    parts = link_text.split("|")
                    target = parts[0].strip()
                    relation = parts[1].strip()
                    if not target:
                        malformed_edges.append((node_file.name, link_text, "Empty target"))
                    elif not relation:
                        malformed_edges.append((node_file.name, link_text, "Empty relation"))
                    else:
                        total_edges += 1
        except Exception as e:
            print(f"Error reading {node_file}: {e}", file=sys.stderr)

    print(f"Found {total_edges} properly formatted edges.")
    
    edges_ok = True
    if malformed_edges:
        edges_ok = False
        print(f"Validation FAILED: Found {len(malformed_edges)} malformed edges:")
        for file, link, reason in malformed_edges[:10]:
            print(f"  {file}: [[{link}]] - {reason}")
        if len(malformed_edges) > 10:
            print(f"  ... and {len(malformed_edges) - 10} more.")
    else:
        print("Edge formatting validation PASSED.")

    return count_ok and edges_ok

def main():
    parser = argparse.ArgumentParser(description="Validate an Akanga vault directory.")
    parser.add_argument("vault", help="Path to the vault directory")
    args = parser.parse_args()

    if validate_vault(args.vault):
        print("\nOverall Vault Validation: PASSED")
        sys.exit(0)
    else:
        print("\nOverall Vault Validation: FAILED")
        sys.exit(1)

if __name__ == "__main__":
    main()
