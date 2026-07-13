from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GraphLevel(StrEnum):
    MODULE = "module"
    FILE = "file"


class GraphScope(StrEnum):
    CHANGES = "changes"
    REPOSITORY = "repository"


class GraphNode(BaseModel):
    id: str
    label: str
    level: GraphLevel
    module: str | None = None
    changed: bool = False
    context: bool = False


class GraphEdge(BaseModel):
    source: str
    target: str
    kind: str | None = None
    scope: str | None = None


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
