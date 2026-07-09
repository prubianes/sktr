from __future__ import annotations

import sys
from pathlib import Path
import re

from sktr_graph.model import Graph


class MermaidGraphOutput:
    format = "mermaid"

    def render(self, graph: Graph) -> str:
        lines = ["graph TD"]
        for edge in graph.edges:
            source_id = _node_id(edge.source)
            target_id = _node_id(edge.target)
            if source_id == edge.source and target_id == edge.target:
                lines.append(f"  {edge.source} --> {edge.target}")
            else:
                lines.append(f"  {source_id}[{edge.source}] --> {target_id}[{edge.target}]")
        return "\n".join(lines)

    def write(self, graph: Graph, destination: str | None = None) -> None:
        content = self.render(graph)
        if destination is None:
            sys.stdout.write(content + "\n")
            return

        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content + "\n", encoding="utf-8")


def _node_id(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]", "_", value)
    if not normalized:
        return "unknown"
    if normalized[0].isdigit():
        return f"n_{normalized}"
    return normalized
