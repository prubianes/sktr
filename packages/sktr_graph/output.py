from __future__ import annotations

import sys
import hashlib
import json
from pathlib import Path
import re

from sktr_graph.model import Graph


class MermaidGraphOutput:
    format = "mermaid"

    def render(self, graph: Graph) -> str:
        lines = ["graph TD"]
        node_ids = _node_ids([node.id for node in graph.nodes])
        file_nodes = [node for node in graph.nodes if node.level.value == "file"]
        if file_nodes:
            modules = sorted({node.module or "other" for node in file_nodes})
            for module in modules:
                lines.append(f"  subgraph {_node_id('module_' + module)}[{_label(module)}]")
                for node in file_nodes:
                    if (node.module or "other") == module:
                        lines.append(f"    {node_ids[node.id]}[{_label(node.label)}]")
                lines.append("  end")
        else:
            for node in graph.nodes:
                lines.append(f"  {node_ids[node.id]}[{_label(node.label)}]")
        for edge in graph.edges:
            source_id = node_ids.get(edge.source, _node_id(edge.source))
            target_id = node_ids.get(edge.target, _node_id(edge.target))
            label = f"|{edge.kind}|" if edge.kind and edge.kind != "import" else ""
            lines.append(f"  {source_id} -->{label} {target_id}")
        changed = [node_ids[node.id] for node in graph.nodes if node.changed]
        context = [node_ids[node.id] for node in graph.nodes if node.context and not node.changed]
        if changed:
            lines.append(f"  class {','.join(changed)} changed")
            lines.append("  classDef changed fill:#dff7e8,stroke:#17834b,stroke-width:2px")
        if context:
            lines.append(f"  class {','.join(context)} context")
            lines.append("  classDef context fill:#f4f4f5,stroke:#71717a,stroke-dasharray:4 3")
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


def _label(value: str) -> str:
    return json.dumps(value, ensure_ascii=True)


def _node_ids(values: list[str]) -> dict[str, str]:
    grouped: dict[str, list[str]] = {}
    for value in values:
        grouped.setdefault(_node_id(value), []).append(value)
    result: dict[str, str] = {}
    for base, originals in grouped.items():
        for original in sorted(originals):
            suffix = f"_{hashlib.sha1(original.encode()).hexdigest()[:8]}" if len(originals) > 1 else ""
            result[original] = f"{base}{suffix}"
    return result
