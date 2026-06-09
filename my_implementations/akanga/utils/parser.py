def parse_node_file(path: str): ...  # -> Node:


def content_hash(path: str) -> str: ...


def write_node_file(path: str, frontmatter_dict: dict, content: str) -> None: ...


def create(title: str, node_type: str, vault: str): ...  # -> Node:
