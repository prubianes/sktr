from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class GraphLevel(StrEnum):
    MODULE = "module"
    FILE = "file"


class GraphNode(BaseModel):
    id: str
    label: str
    level: GraphLevel


class GraphEdge(BaseModel):
    source: str
    target: str


class Graph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
