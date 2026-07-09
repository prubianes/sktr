from sktr_graph.builder import GraphBuilder
from sktr_graph.model import Graph, GraphEdge, GraphLevel, GraphNode
from sktr_graph.output import MermaidGraphOutput
from sktr_core.plugins import PluginMetadata


class MermaidOutputPlugin:
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="mermaid",
            version="0.11.0",
            type="output",
            description="Mermaid dependency graph output.",
        )

    def create_output(self) -> MermaidGraphOutput:
        return MermaidGraphOutput()

__all__ = [
    "Graph",
    "GraphBuilder",
    "GraphEdge",
    "GraphLevel",
    "GraphNode",
    "MermaidOutputPlugin",
    "MermaidGraphOutput",
]
