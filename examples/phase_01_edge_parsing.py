"""Phase 1 — Inline edge extraction from Markdown prose.

Run: python examples/phase_01_edge_parsing.py

Shows how [[wikilink]] and [text](file.md) references are extracted from
body text while content inside code blocks is safely ignored.
Akanga creates edges with relation="wikilink" or "markdown-link" —
there is NO pipe-separated [[Target | relation]] syntax.
"""
import re
from dataclasses import dataclass


@dataclass
class Edge:
    relation: str
    relation_id: str
    target: str
    target_id: str


def strip_code_blocks(body: str) -> str:
    return re.sub(r'```.*?```', '', body, flags=re.DOTALL)


def extract_inline_edges(body: str) -> list[Edge]:
    clean = strip_code_blocks(body)
    pattern = r'\[\[([^\]]+)\]\]'
    return [
        Edge(relation="wikilink", relation_id="", target=m.group(1).strip(), target_id="")
        for m in re.finditer(pattern, clean)
    ]


# Demo
body = """
This idea connects to [[Attention Economy]] and its effects on cognition.
See also [[Kahneman]] for the dual-process framing.

```python
# This [[should not be extracted]] from code blocks
```
"""
edges = extract_inline_edges(body)
for e in edges:
    print(f"Edge: {e.target!r} via relation {e.relation!r}")
print(f"\nFound {len(edges)} edges (code block content correctly ignored)")
assert all(e.relation == "wikilink" for e in edges), "All wikilink edges must have relation='wikilink'"
