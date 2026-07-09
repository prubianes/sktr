from __future__ import annotations

from sktr_core.model import Dependency, DependencyKind, SourceFile, System
from sktr_graph.model import Graph, GraphEdge, GraphLevel, GraphNode

SOURCE_ROOTS = {"src", "app", "lib", "packages"}


class GraphBuilder:
    def build(self, system: System, *, level: GraphLevel = GraphLevel.MODULE) -> Graph:
        if level == GraphLevel.FILE:
            return self._file_graph(system)
        return self._module_graph(system)

    def _module_graph(self, system: System) -> Graph:
        source_files = _source_files(system)
        known_modules = {_module_from_path(source_file.path) for source_file in source_files}
        nodes = {
            module: GraphNode(id=module, label=module, level=GraphLevel.MODULE)
            for module in known_modules
            if module
        }
        edges: set[tuple[str, str]] = set()

        for source_file in source_files:
            source_module = _module_from_path(source_file.path)
            if not source_module:
                continue
            for dependency in source_file.dependencies:
                target_module = _module_from_dependency(dependency)
                if not target_module or target_module == source_module or target_module not in nodes:
                    continue
                edges.add((source_module, target_module))

        return Graph(
            nodes=[nodes[key] for key in sorted(nodes)],
            edges=[GraphEdge(source=source, target=target) for source, target in sorted(edges)],
        )

    def _file_graph(self, system: System) -> Graph:
        source_files = _source_files(system)
        known_files = {source_file.path for source_file in source_files}
        nodes = {
            source_file.path: GraphNode(id=source_file.path, label=source_file.path, level=GraphLevel.FILE)
            for source_file in source_files
        }
        edges: set[tuple[str, str]] = set()

        for source_file in source_files:
            for dependency in source_file.dependencies:
                target_file = _file_from_dependency(dependency)
                if not target_file or target_file == source_file.path or target_file not in known_files:
                    continue
                edges.add((source_file.path, target_file))

        return Graph(
            nodes=[nodes[key] for key in sorted(nodes)],
            edges=[GraphEdge(source=source, target=target) for source, target in sorted(edges)],
        )


def _source_files(system: System) -> list[SourceFile]:
    return [source_file for module in system.modules for source_file in module.files]


def _module_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] in SOURCE_ROOTS:
        parts = parts[1:]
    if not parts:
        return ""
    return parts[0].removesuffix(".py")


def _module_from_dependency(dependency: Dependency) -> str:
    if dependency.kind != DependencyKind.IMPORT:
        return ""
    target = dependency.target.strip(".")
    if not target:
        return ""
    if "/" in target:
        return _module_from_path(target)
    return target.split(".", 1)[0]


def _file_from_dependency(dependency: Dependency) -> str:
    if dependency.kind != DependencyKind.IMPORT:
        return ""
    target = dependency.target.strip(".")
    if not target:
        return ""
    if target.endswith(".py"):
        return target
    if "/" in target:
        return f"{target}.py"
    return f"{target.replace('.', '/')}.py"
