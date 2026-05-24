# Python Type Annotations

Python is dynamically typed — you can assign any value to any variable at any time. Type annotations are a way to document your intentions about what types a variable or function should hold, without changing how Python actually runs the code. They were standardized in PEP 484 (Python 3.5) and have become the expected style in serious Python codebases.

---

## What they are and why they exist

Before annotations, you had two choices: write docstrings that might go stale, or hope the reader could infer types from context. Annotations make types explicit in the code itself, and because tools like mypy, pyright, and your editor's language server can read them, you get real-time feedback when you pass the wrong type to a function.

```python
# Without annotations — you have to read the body to know what's valid
def greet(name):
    return "Hello, " + name

# With annotations — the contract is visible at the signature
def greet(name: str) -> str:
    return "Hello, " + name
```

---

## Basic variable and function annotations

Variable annotations use a colon after the name:

```python
count: int = 0
label: str = "active"
ratio: float = 0.95
enabled: bool = True
```

Function annotations go on each parameter and after the `->` for the return type:

```python
def add(x: int, y: int) -> int:
    return x + y

def is_empty(text: str) -> bool:
    return len(text) == 0

def log_message(message: str) -> None:   # None means "returns nothing"
    print(message)
```

---

## Optional and union types

`Optional[X]` means the value can be `X` or `None`. It was the original spelling from the `typing` module:

```python
from typing import Optional

def find_user(user_id: int) -> Optional[str]:
    # returns a username string, or None if not found
    ...
```

Python 3.10 introduced a cleaner spelling using `|`:

```python
def find_user(user_id: int) -> str | None:
    ...
```

The akanga codebase uses the `|` form consistently. In `eventbus.py`:

```python
self._loop: asyncio.AbstractEventLoop | None = None
```

`Union[X, Y]` lets you express "either of these types" when neither is `None`:

```python
from typing import Union

def process(value: Union[str, int]) -> str:
    return str(value)

# Python 3.10+ spelling:
def process(value: str | int) -> str:
    return str(value)
```

In `models.py`, the `Edge` dataclass uses this for its optional relation field:

```python
@dataclass
class Edge:
    id: UUID
    source_id: UUID
    target_id: UUID
    relation: str | None = None
```

---

## Generic containers

Python's built-in container types support subscript notation to describe what they hold:

```python
names: list[str] = []
scores: dict[str, int] = {}
unique_ids: set[int] = set()
pair: tuple[str, int] = ("alice", 42)
```

Before Python 3.9, you had to import capitalized versions from `typing`:

```python
from typing import List, Dict, Set
names: List[str] = []
```

Modern Python (3.9+) uses lowercase built-ins directly — that is what akanga does. From `models.py`:

```python
tags: list[str]
frontmatter: dict[str, Any]
```

And from `eventbus.py`:

```python
self._subs: dict[str, list[Subscriber]] = {}
```

That last one is a nested generic: a dict mapping strings to lists of `Subscriber` objects.

---

## `from __future__ import annotations`

This import appears at the top of every akanga source file. It changes how Python handles annotations: instead of evaluating them immediately when the module loads, it stores them as strings and evaluates them lazily.

```python
from __future__ import annotations  # must be the very first import
```

Why does this matter? Without it, any type referenced in an annotation must already be defined at the point where the annotation appears. This creates circular-import problems in larger codebases. With deferred evaluation, you can write:

```python
from __future__ import annotations

class Node:
    def copy(self) -> Node:  # Node isn't fully defined yet, but this is fine
        ...
```

Without the import, `-> Node` would fail at class-definition time because `Node` doesn't exist yet when that line runs.

The practical rule: put `from __future__ import annotations` at the top of every module that uses type annotations. Python 3.11+ makes this the default behavior, but until your project drops 3.10 support, the import is necessary.

---

## `from typing import Any`

`Any` is an escape hatch that tells type checkers "I don't know the type, or I don't want to restrict it." It turns off checking for that value.

```python
from typing import Any

def store(value: Any) -> None:
    ...  # value could be anything; no checking applied
```

In akanga, `Any` appears where data comes from external sources whose structure isn't fixed. The `frontmatter` field of `Node` holds raw YAML-parsed data, which could contain strings, lists, nested dicts, or anything:

```python
frontmatter: dict[str, Any]
```

Using `Any` here is honest: the actual shape depends on what the user wrote in their Markdown files. Avoid `Any` when you do know the type — it silences errors rather than preventing them.

---

## `Callable` — function types

`Callable` describes a value that can be called (a function, a method, a lambda). The syntax is:

```python
Callable[[arg_types...], return_type]
```

In `watcher.py`, `VaultWatcher` accepts two callback parameters. The callbacks receive a file path string and return nothing:

```python
from collections.abc import Callable

class VaultWatcher:
    def __init__(
        self,
        vault_path: str,
        on_change: Callable[[str], None],
        on_delete: Callable[[str], None],
        debounce_sec: float = 0.5,
    ):
```

This tells the reader (and the type checker) exactly what kind of function to pass: one that takes a `str` and returns `None`.

`Callable` also appears in the `Subscriber` type alias in `eventbus.py`, which adds async into the mix:

```python
from collections.abc import Callable, Coroutine
from typing import Any

Subscriber = Callable[[str, Any], Coroutine[Any, Any, None]]
```

That means: a callable that takes a `str` and an `Any`, and returns a coroutine (i.e., it is an `async def` function).

---

## Type aliases

You can name a type expression to avoid repeating it. This is what the `Subscriber` line above does — it creates a name for a complex callable signature:

```python
Subscriber = Callable[[str, Any], Coroutine[Any, Any, None]]
```

Now `Subscriber` can be used as a type anywhere in the module:

```python
def subscribe(self, topic: str, callback: Subscriber) -> None:
    ...
```

This is far more readable than writing the full `Callable[...]` inline every time.

---

## Annotations are NOT enforced at runtime

This is the most important thing to understand about Python type annotations: **Python ignores them when it runs your code.** Passing the wrong type does not raise an error.

```python
def double(x: int) -> int:
    return x * 2

double("hello")  # runs fine, returns "hellohello"
```

Annotations exist for:
- **Static analysis tools** — mypy and pyright read them and report type errors before you run the code.
- **Editor support** — autocomplete, hover documentation, and inline warnings.
- **Human readers** — the annotation is documentation that cannot go stale because it lives in the code.

If you want runtime type enforcement, you need a separate library like Pydantic or explicit `isinstance` checks.

---

## In this codebase

Places where annotations are doing the most work in akanga:

| File | What to look for |
|---|---|
| `src/akanga_core/models.py` | Every field of `Node`, `Edge`, `ActiveConfig`, `VirtualConfig` is annotated — this is the canonical reference for the data model |
| `src/akanga_core/eventbus.py` | The `Subscriber` type alias; `dict[str, list[Subscriber]]` showing nested generics |
| `src/akanga_core/watcher.py` | `Callable[[str], None]` for callback parameters; `dict[str, threading.Timer]` in the handler |
| `src/akanga_core/parser.py` | Return type annotations on `parse_node_file` (`-> Node`) and `content_hash` (`-> str`) |

The `from __future__ import annotations` import appears at line 1 of every source file in `src/akanga_core/`. That is not coincidence — it is a project-wide convention that eliminates forward-reference errors and should be the first thing you add when creating a new module.
