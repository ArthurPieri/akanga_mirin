from dataclasses import dataclass
from uuid import UUID


# class EdgeRelation: ...


@dataclass
class Edge:
    id: UUID
    source_id: UUID
    target_id: UUID
    # TODO: validate the relations types
    relation: str | None = None
