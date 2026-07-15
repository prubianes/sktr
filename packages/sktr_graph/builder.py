from __future__ import annotations

from pathlib import PurePosixPath

from sktr_core.model import Dependency, DependencyKind, SourceFile, System
from sktr_graph.model import Graph, GraphEdge, GraphLevel, GraphNode

SOURCE_ROOTS = {"src", "app", "lib", "packages"}


class GraphBuilder:
    def build(
        self,
        system: System,
        *,
        level: GraphLevel = GraphLevel.MODULE,
        changed_files: set[str] | None = None,
    ) -> Graph:
        changed = changed_files or set()
        if level == GraphLevel.FILE:
            return self._file_graph(system, changed)
        return self._module_graph(system, changed)

    def _module_graph(self, system: System, changed_files: set[str]) -> Graph:
        source_files = _source_files(system)
        known_modules = {_source_module(source_file) for source_file in source_files}
        target_modules = {
            target
            for source_file in source_files
            for dependency in source_file.dependencies
            if (target := dependency.target_module or _module_from_dependency(dependency))
            and _is_internal(dependency)
            and _has_resolved_target(dependency)
        }
        all_modules = known_modules | target_modules
        changed_modules = {
            _source_module(source_file)
            for source_file in source_files
            if source_file.path in changed_files
        }
        nodes = {
            module: GraphNode(
                id=module,
                label=module,
                level=GraphLevel.MODULE,
                module=module,
                changed=module in changed_modules,
                context=module not in known_modules,
            )
            for module in all_modules
            if module
        }
        edges: dict[tuple[str, str], GraphEdge] = {}

        for source_file in source_files:
            source_module = _source_module(source_file)
            if not source_module:
                continue
            for dependency in source_file.dependencies:
                target_module = dependency.target_module or _module_from_dependency(dependency)
                if (
                    not target_module
                    or target_module == source_module
                    or target_module not in nodes
                    or not _is_internal(dependency)
                ):
                    continue
                key = (source_module, target_module)
                edges.setdefault(key, _edge(source_module, target_module, dependency))

        return Graph(
            nodes=[nodes[key] for key in sorted(nodes)],
            edges=[edges[key] for key in sorted(edges)],
        )

    def _file_graph(self, system: System, changed_files: set[str]) -> Graph:
        source_files = _source_files(system)
        known_files = {source_file.path for source_file in source_files}
        target_files = {
            dependency.target_path
            for source_file in source_files
            for dependency in source_file.dependencies
            if dependency.target_path and _is_internal(dependency)
        }
        all_files = known_files | target_files
        modules = {source_file.path: _source_module(source_file) for source_file in source_files}
        target_modules = {
            dependency.target_path: dependency.target_module
            for source_file in source_files
            for dependency in source_file.dependencies
            if dependency.target_path and dependency.target_module
        }
        nodes = {
            path: GraphNode(
                id=path,
                label=path,
                level=GraphLevel.FILE,
                module=modules.get(path) or target_modules.get(path) or _module_from_path(path),
                changed=path in changed_files,
                context=path not in known_files,
            )
            for path in all_files
        }
        edges: dict[tuple[str, str], GraphEdge] = {}

        for source_file in source_files:
            for dependency in source_file.dependencies:
                target_file = dependency.target_path
                if (
                    not target_file
                    or target_file == source_file.path
                    or target_file not in nodes
                    or not _is_internal(dependency)
                ):
                    continue
                key = (source_file.path, target_file)
                edges.setdefault(key, _edge(source_file.path, target_file, dependency))

        return Graph(
            nodes=[nodes[key] for key in sorted(nodes)],
            edges=[edges[key] for key in sorted(edges)],
        )


class GraphQuery:
    def focus(self, graph: Graph, node_id: str) -> Graph:
        _require_node(graph, node_id)
        selected = {node_id}
        for edge in graph.edges:
            if edge.source == node_id or edge.target == node_id:
                selected.update((edge.source, edge.target))
        return _subgraph(graph, selected)

    def dependencies_of(self, graph: Graph, node_id: str) -> Graph:
        return _reachable_subgraph(graph, node_id, reverse=False)

    def dependents_of(self, graph: Graph, node_id: str) -> Graph:
        return _reachable_subgraph(graph, node_id, reverse=True)

    def cycles(self, graph: Graph) -> Graph:
        adjacency = _adjacency(graph.edges)
        cycle_edges = [
            edge for edge in graph.edges if _can_reach(adjacency, edge.target, edge.source)
        ]
        selected = {value for edge in cycle_edges for value in (edge.source, edge.target)}
        return Graph(
            nodes=[node for node in graph.nodes if node.id in selected],
            edges=cycle_edges,
        )


def _source_files(system: System) -> list[SourceFile]:
    return [source_file for module in system.modules for source_file in module.files]


def _module_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] in SOURCE_ROOTS:
        parts = parts[1:]
    if not parts:
        return ""
    return PurePosixPath(parts[0]).stem


def _source_module(source_file: SourceFile) -> str:
    return source_file.module or _module_from_path(source_file.path)


def _module_from_dependency(dependency: Dependency) -> str:
    if dependency.kind != DependencyKind.IMPORT:
        return ""
    target = dependency.target.strip(".")
    if not target:
        return ""
    if "/" in target:
        return _module_from_path(target)
    return target.split(".", 1)[0]


def _is_internal(dependency: Dependency) -> bool:
    return dependency.scope.value not in {"external", "standard_library"}


def _has_resolved_target(dependency: Dependency) -> bool:
    return bool(
        dependency.target_path
        or dependency.target_module
        or dependency.scope.value == "internal"
    )


def _edge(source: str, target: str, dependency: Dependency) -> GraphEdge:
    return GraphEdge(
        source=source,
        target=target,
        kind=dependency.kind.value,
        scope=dependency.scope.value,
    )


def _require_node(graph: Graph, node_id: str) -> None:
    if node_id not in {node.id for node in graph.nodes}:
        raise ValueError(f"Graph node not found: {node_id}")


def _subgraph(graph: Graph, selected: set[str]) -> Graph:
    return Graph(
        nodes=[node for node in graph.nodes if node.id in selected],
        edges=[edge for edge in graph.edges if edge.source in selected and edge.target in selected],
    )


def _reachable_subgraph(graph: Graph, node_id: str, *, reverse: bool) -> Graph:
    _require_node(graph, node_id)
    adjacency: dict[str, set[str]] = {}
    for edge in graph.edges:
        source, target = (edge.target, edge.source) if reverse else (edge.source, edge.target)
        adjacency.setdefault(source, set()).add(target)
    selected = {node_id}
    pending = [node_id]
    while pending:
        current = pending.pop()
        for target in sorted(adjacency.get(current, set())):
            if target not in selected:
                selected.add(target)
                pending.append(target)
    return _subgraph(graph, selected)


def _adjacency(edges: list[GraphEdge]) -> dict[str, set[str]]:
    adjacency: dict[str, set[str]] = {}
    for edge in edges:
        adjacency.setdefault(edge.source, set()).add(edge.target)
    return adjacency


def _can_reach(adjacency: dict[str, set[str]], source: str, target: str) -> bool:
    pending = [source]
    visited: set[str] = set()
    while pending:
        current = pending.pop()
        if current == target:
            return True
        if current in visited:
            continue
        visited.add(current)
        pending.extend(sorted(adjacency.get(current, set()), reverse=True))
    return False
