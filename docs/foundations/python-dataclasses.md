# Python Dataclasses

**Audience:** Python developers who know classes but haven't used `@dataclass` · **Read time:** ~10 min

A dataclass is a regular Python class with a decorator that auto-generates boilerplate: `__init__`, `__repr__`, and `__eq__`. Instead of writing the same field-assignment code in every `__init__`, you declare fields as annotated class attributes and let Python generate the rest.

Dataclasses were added in Python 3.7 (PEP 557). They are the standard way to define data-carrying objects in modern Python — lighter than full classes when you don't need custom behavior, and more structured than plain dicts.

---

## The basics

Without dataclasses, a simple data object looks like this:

```python
class Point:
    def __init__(self, x: float, y: float) -> None:
        self.x = x
        self.y = y

    def __repr__(self) -> str:
        return f"Point(x={self.x!r}, y={self.y!r})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return self.x == other.x and self.y == other.y
```

With `@dataclass`, that collapses to:

```python
from dataclasses import dataclass

@dataclass
class Point:
    x: float
    y: float
```

Python generates an `__init__` that accepts `x` and `y`, a `__repr__` that shows their values, and an `__eq__` that compares them field by field. You get all three for free.

```python
p1 = Point(1.0, 2.0)
p2 = Point(1.0, 2.0)

print(p1)           # Point(x=1.0, y=2.0)
print(p1 == p2)     # True
```

---

## Fields with defaults

Fields without defaults must come before fields with defaults (same rule as function parameters):

```python
@dataclass
class Config:
    host: str
    port: int = 8080
    debug: bool = False
```

```python
cfg = Config(host="localhost")        # port=8080, debug=False
cfg2 = Config(host="0.0.0.0", port=9000)
```

---

## `field(default_factory=...)` — the mutable default problem

You cannot use a mutable object (like a list or dict) as a default value directly:

```python
@dataclass
class Node:
    tags: list[str] = []   # TypeError: mutable default is not allowed
```

Python raises a `TypeError` here because a single list object would be shared across all instances — the same bug you get with mutable default arguments in regular functions. The fix is `field(default_factory=...)`, which calls a factory function to create a fresh object for each instance:

```python
from dataclasses import dataclass, field

@dataclass
class Node:
    tags: list[str] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)
```

Now each `Node()` gets its own empty list and dict.

In akanga's `models.py`, `ActiveConfig` uses this pattern:

```python
@dataclass
class ActiveConfig:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    interval: int = 60
    timeout: int = 5
```

`params` defaults to a fresh empty dict. `interval` and `timeout` are integers (immutable), so plain defaults are fine.

---

## `frozen=True` — immutable dataclasses

Adding `frozen=True` to the decorator makes instances read-only after creation. Attempts to set attributes raise a `FrozenInstanceError`. Frozen dataclasses also get a `__hash__` method, so they can be used as dict keys or put in sets.

```python
@dataclass(frozen=True)
class Coordinate:
    lat: float
    lon: float

c = Coordinate(51.5, -0.1)
c.lat = 99.0   # FrozenInstanceError: cannot assign to field 'lat'

locations = {c}  # works because frozen dataclasses are hashable
```

Use `frozen=True` when the data is meant to be a value — something that represents a fact, not a container you update over time. Akanga's `Node` and `Edge` are not frozen because they are updated (the DB layer creates new instances from rows), but the concept is important for value objects like configuration records or cache keys.

---

## `__post_init__` — validation and derived fields

Sometimes you need to run code after the generated `__init__` has set fields — to validate, normalize, or compute derived values. Put that logic in `__post_init__`:

```python
@dataclass
class BoundedInt:
    value: int
    min_val: int = 0
    max_val: int = 100

    def __post_init__(self) -> None:
        if not (self.min_val <= self.value <= self.max_val):
            raise ValueError(
                f"value {self.value} out of range [{self.min_val}, {self.max_val}]"
            )
```

A common pattern is computing a derived field from other fields. Mark the derived field with `field(init=False)` to exclude it from `__init__`, then set it in `__post_init__`:

```python
from dataclasses import dataclass, field

@dataclass
class FullName:
    first: str
    last: str
    display: str = field(init=False)

    def __post_init__(self) -> None:
        self.display = f"{self.first} {self.last}"

name = FullName("Arthur", "Pieri")
print(name.display)  # "Arthur Pieri"
```

---

## `dataclasses.asdict()` — converting to dict

`dataclasses.asdict()` recursively converts a dataclass instance to a plain dict. Nested dataclasses, lists, and dicts are all converted. This is useful for serialization — sending data to JSON, storing in a database, or logging.

```python
from dataclasses import dataclass, asdict

@dataclass
class Point:
    x: float
    y: float

p = Point(1.5, 2.5)
print(asdict(p))  # {'x': 1.5, 'y': 2.5}
```

With nested dataclasses:

```python
@dataclass
class Line:
    start: Point
    end: Point

line = Line(Point(0, 0), Point(1, 1))
print(asdict(line))
# {'start': {'x': 0, 'y': 0}, 'end': {'x': 1, 'y': 1}}
```

One caveat: `asdict` does a deep copy. For large objects or performance-sensitive code, a manual `__dict__` access or a custom serializer may be more appropriate.

---

## Akanga's Node dataclass

`models.py` — which you build in Phase 1A — defines the central data structures. The `Node` class represents a single Markdown file in the vault:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

@dataclass
class Node:
    id: UUID
    path: str
    title: str
    type: NodeType
    tags: list[str]
    frontmatter: dict[str, Any]
    content: str
    created_at: datetime
    updated_at: datetime

    @staticmethod
    def new(path: str, title: str = "", type: NodeType = NodeType.note) -> Node:
        now = datetime.now(UTC)
        return Node(
            id=uuid4(), path=path, title=title, type=type,
            tags=[], frontmatter={}, content="",
            created_at=now, updated_at=now,
        )
```

Key observations:
- Every field is annotated — `@dataclass` reads these annotations to build `__init__`.
- `tags` is `list[str]` and `frontmatter` is `dict[str, Any]`. In the `Node.new()` factory, fresh `[]` and `{}` literals are passed explicitly rather than using `field(default_factory=...)`. That is safe because the factory method always constructs a new `Node` call; there is no class-level mutable default.
- `Node.new()` is a `@staticmethod` convenience constructor — a common pattern to give "sensible defaults" construction a name without subclassing.

---

## Akanga's Edge dataclass

`Edge` is simpler — it represents a link between two nodes:

```python
@dataclass
class Edge:
    id: UUID
    source_id: UUID
    target_id: UUID
    relation: str | None = None
```

All four fields map to columns in the SQLite `edges` table. `relation` is optional — a `None` relation means the link exists but has no labeled relationship type. The `str | None` annotation documents that contract directly.

Also in the same file, `ActiveConfig` shows `field(default_factory=dict)` in production use:

```python
@dataclass
class ActiveConfig:
    action: str
    params: dict[str, Any] = field(default_factory=dict)
    interval: int = 60
    timeout: int = 5
```

And `VirtualConfig` shows a dataclass where all fields have defaults except the required `url`:

```python
@dataclass
class VirtualConfig:
    url: str
    external_type: str = "url"
    description: str = ""
```

---

## In your implementation

| Class | File (phase where you build it) | What to notice |
|---|---|---|
| `Node` | `models.py` (Phase 1A) | Core vault node; all nine fields annotated; `Node.new()` static factory |
| `Edge` | `models.py` (Phase 1A) | Minimal graph edge; `relation: str \| None` optional field |
| `ActiveConfig` | `models.py` (Phase 1A) | `field(default_factory=dict)` for the `params` dict |
| `VirtualConfig` | `models.py` (Phase 1A) | Mix of required and defaulted string fields |

None of these dataclasses use `__post_init__` — validation happens at the parser layer (`parser.py`) before a `Node` is constructed. That is a design choice: keep the dataclasses as plain data containers, and put logic in the functions that create them.

`frozen=True` is not used here either. Akanga's nodes are mutable by intent — the indexer creates `Node` instances from parsed files and writes them to SQLite; the TUI creates them and immediately passes them to the DB. Immutability would add friction for no benefit in this flow.

The main thing dataclasses buy akanga is automatic `__eq__`: two `Node` instances with the same field values compare equal, which makes testing straightforward — construct the expected node, parse the actual file, and `assert` them equal without any custom comparison code.
