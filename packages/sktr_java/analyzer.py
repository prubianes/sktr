from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

import tree_sitter_java
from tree_sitter import Node

from sktr_core.model import (
    APIExposure,
    Dependency,
    DependencyKind,
    DependencyScope,
    Module,
    SourceFile,
    Symbol,
    SymbolKind,
    SymbolVisibility,
    System,
)
from sktr_core.plugins import AnalysisContext
from sktr_treesitter.parser import TreeSitterParser, location, node_text, walk

PACKAGE_PATTERN = re.compile(r"^\s*package\s+([A-Za-z_][\w.]*)\s*;", re.MULTILINE)
TYPE_NODES = {
    "class_declaration": SymbolKind.CLASS,
    "interface_declaration": SymbolKind.INTERFACE,
    "enum_declaration": SymbolKind.TYPE,
    "record_declaration": SymbolKind.CLASS,
    "annotation_type_declaration": SymbolKind.INTERFACE,
}
METHOD_NODES = {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}
STANDARD_PREFIXES = ("java.", "javax.", "jdk.", "org.w3c.", "org.xml.")


class JavaAnalyzer:
    language = "java"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root
        self.parser = TreeSitterParser(tree_sitter_java.language(), analyzer=self.language)

    def analyze(self, context: AnalysisContext) -> System:
        root = self._root(context)
        snapshot_complete = context.diff.metadata.get("graph_scope") == "repository"
        changed_paths = [
            path
            for path in (context.review.changed_files or context.diff.changed_files)
            if PurePosixPath(path).suffix.lower() == ".java"
        ]
        if not changed_paths:
            return System(metadata={"analyzer": self.__class__.__name__})
        class_index = (
            _class_index_from_sources(context.diff.current_file_contents)
            if snapshot_complete
            else _class_index(root)
        )
        files: list[SourceFile] = []
        diagnostics = []
        for path in changed_paths:
            current = context.diff.current_file_contents.get(path)
            if current is None and (root / path).is_file():
                current = (root / path).read_text(encoding="utf-8")
            baseline = context.diff.base_file_contents.get(path)
            if current is None and baseline is None:
                continue
            source_file, file_diagnostics = self._analyze_file(path, current, baseline, class_index)
            files.append(source_file)
            diagnostics.extend(file_diagnostics)

        return System(
            modules=[Module(name=self.language, path=".", files=files, metadata={"language": self.language})]
            if files
            else [],
            diagnostics=diagnostics,
            metadata={
                "analyzer": self.__class__.__name__,
                "test_infrastructure_detected": any(
                    "src/test" in path.replace("\\", "/")
                    for path in context.diff.repository_files
                ),
            },
        )

    def _analyze_file(
        self,
        path: str,
        current: str | None,
        baseline: str | None,
        class_index: dict[str, str],
    ) -> tuple[SourceFile, list]:
        symbols: list[Symbol] = []
        dependencies: list[Dependency] = []
        package_name = ""
        diagnostics = []
        if current is not None:
            parsed = self.parser.parse(current, file_path=path)
            diagnostics.extend(parsed.diagnostics)
            package_name = _package_name(parsed.tree.root_node, parsed.source)
            symbols = _symbols(path, parsed.tree.root_node, parsed.source)
            dependencies = _dependencies(path, parsed.tree.root_node, parsed.source)
        baseline_symbols: list[Symbol] = []
        baseline_dependencies: list[Dependency] = []
        if baseline is not None:
            parsed_baseline = self.parser.parse(baseline, file_path=path)
            baseline_symbols = _symbols(path, parsed_baseline.tree.root_node, parsed_baseline.source)
            baseline_dependencies = _dependencies(path, parsed_baseline.tree.root_node, parsed_baseline.source)
            if not package_name:
                package_name = _package_name(parsed_baseline.tree.root_node, parsed_baseline.source)

        source_module = package_name or _module_for_path(path)
        for dependency in dependencies:
            _resolve_dependency(dependency, class_index=class_index, source_module=source_module)
        for dependency in baseline_dependencies:
            _resolve_dependency(dependency, class_index=class_index, source_module=source_module)
        return (
            SourceFile(
                path=path,
                language=self.language,
                module=source_module,
                symbols=symbols,
                dependencies=dependencies,
                metadata={
                    "package": package_name,
                    "build_module": _build_module_for_path(path),
                    "baseline_dependencies": sorted({item.target for item in baseline_dependencies}),
                    "baseline_dependency_modules": sorted(
                        {item.target_module for item in baseline_dependencies if item.target_module}
                    ),
                    "baseline_symbols": sorted({_symbol_identity(symbol) for symbol in baseline_symbols}),
                    "baseline_public_symbols": sorted(
                        {
                            _symbol_identity(symbol)
                            for symbol in baseline_symbols
                            if symbol.api_exposure == APIExposure.EXPORTED
                        }
                    ),
                },
            ),
            diagnostics,
        )

    def _root(self, context: AnalysisContext) -> Path:
        if self.root is not None:
            return self.root
        return Path(context.diff.repository_root) if context.diff.repository_root else Path.cwd()


def _package_name(root: Node, source: bytes) -> str:
    declaration = next((node for node in root.named_children if node.type == "package_declaration"), None)
    if declaration is None:
        return ""
    value = node_text(declaration, source).strip()
    return value.removeprefix("package").removesuffix(";").strip()


def _symbols(path: str, root: Node, source: bytes) -> list[Symbol]:
    symbols: list[Symbol] = []
    for node in walk(root):
        kind = TYPE_NODES.get(node.type)
        if kind is not None:
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                visibility = _visibility(node, source)
                exposed = visibility in {SymbolVisibility.PUBLIC, SymbolVisibility.PROTECTED}
                symbols.append(
                    Symbol(
                        name=name,
                        kind=kind,
                        visibility=visibility,
                        api_exposure=APIExposure.EXPORTED if exposed else APIExposure.NOT_EXPORTED,
                        location=location(path, node),
                        metadata={"annotations": _annotations(node, source)},
                    )
                )
        elif node.type in METHOD_NODES:
            name = node_text(node.child_by_field_name("name"), source)
            if not name and node.type == "compact_constructor_declaration":
                name = node_text(next(iter(node.named_children), None), source)
            owner = _owner_name(node, source)
            if name:
                body = node.child_by_field_name("body")
                visibility = _visibility(node, source)
                exposed = (
                    visibility in {SymbolVisibility.PUBLIC, SymbolVisibility.PROTECTED}
                    and _containing_type_is_exposed(node, source)
                )
                metadata: dict[str, object] = {"annotations": _annotations(node, source)}
                if body is not None:
                    metadata["body_lines"] = _node_lines(body)
                symbols.append(
                    Symbol(
                        name=name,
                        kind=SymbolKind.METHOD,
                        owner=owner or None,
                        visibility=visibility,
                        api_exposure=APIExposure.EXPORTED if exposed else APIExposure.NOT_EXPORTED,
                        location=location(path, node),
                        metadata=metadata,
                    )
                )
    return _unique_symbols(symbols)


def _dependencies(path: str, root: Node, source: bytes) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for node in root.named_children:
        if node.type != "import_declaration":
            continue
        value = node_text(node, source).strip().removeprefix("import").removesuffix(";").strip()
        is_static = value.startswith("static ")
        target = value.removeprefix("static ").strip()
        if target:
            dependencies.append(
                Dependency(
                    source=path,
                    target=target,
                    kind=DependencyKind.IMPORT,
                    location=location(path, node),
                    metadata={"static": is_static},
                )
            )
    for declaration in walk(root):
        if declaration.type not in TYPE_NODES:
            continue
        for relation in declaration.named_children:
            if relation.type not in {"superclass", "super_interfaces", "extends_interfaces"}:
                continue
            kind = (
                DependencyKind.EXTENDS
                if relation.type in {"superclass", "extends_interfaces"}
                else DependencyKind.IMPLEMENTS
            )
            for type_node in walk(relation):
                if type_node.type not in {"type_identifier", "scoped_type_identifier"}:
                    continue
                if type_node.type == "type_identifier" and type_node.parent is not None and type_node.parent.type == "scoped_type_identifier":
                    continue
                target = node_text(type_node, source)
                if target:
                    dependencies.append(
                        Dependency(
                            source=path,
                            target=target,
                            kind=kind,
                            location=location(path, relation),
                        )
                    )
    return _unique_dependencies(dependencies)


def _resolve_dependency(
    dependency: Dependency,
    *,
    class_index: dict[str, str],
    source_module: str,
) -> None:
    dependency.source_module = source_module
    target = dependency.target.removesuffix(".*")
    matched_class = _matched_class(target, class_index)
    if matched_class:
        dependency.scope = DependencyScope.INTERNAL
        dependency.target_module = matched_class.rsplit(".", 1)[0] if "." in matched_class else matched_class
        dependency.target_path = class_index[matched_class]
    elif target.startswith(STANDARD_PREFIXES):
        dependency.scope = DependencyScope.STANDARD_LIBRARY
        dependency.target_module = target.rsplit(".", 1)[0]
    else:
        dependency.scope = DependencyScope.EXTERNAL
        dependency.target_module = target.rsplit(".", 1)[0] if "." in target else target
    dependency.metadata["scope"] = dependency.scope.value


def _matched_class(target: str, class_index: dict[str, str]) -> str | None:
    candidate = target
    while candidate:
        if candidate in class_index:
            return candidate
        candidate = candidate.rsplit(".", 1)[0] if "." in candidate else ""
    package_matches = sorted(name for name in class_index if name.startswith(f"{target}."))
    if package_matches:
        return package_matches[0]
    simple_matches = sorted(name for name in class_index if name.rsplit(".", 1)[-1] == target)
    return simple_matches[0] if len(simple_matches) == 1 else None


def _class_index(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for java_file in root.rglob("*.java"):
        if any(part in {"build", "target", ".gradle"} for part in java_file.parts):
            continue
        try:
            source = java_file.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = PACKAGE_PATTERN.search(source)
        qualified = f"{match.group(1)}.{java_file.stem}" if match else java_file.stem
        result[qualified] = java_file.relative_to(root).as_posix()
    return result


def _class_index_from_sources(sources: dict[str, str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for path, source in sorted(sources.items()):
        if PurePosixPath(path).suffix.lower() != ".java":
            continue
        match = PACKAGE_PATTERN.search(source)
        stem = PurePosixPath(path).stem
        qualified = f"{match.group(1)}.{stem}" if match else stem
        result[qualified] = path
    return result


def _owner_name(node: Node, source: bytes) -> str:
    parent = node.parent
    owners: list[str] = []
    while parent is not None:
        if parent.type in TYPE_NODES:
            name = node_text(parent.child_by_field_name("name"), source)
            if name:
                owners.append(name)
        parent = parent.parent
    return ".".join(reversed(owners))


def _visibility(node: Node, source: bytes) -> SymbolVisibility:
    modifiers = next((child for child in node.children if child.type == "modifiers"), None)
    value = node_text(modifiers, source) if modifiers is not None else ""
    if "public" in value.split():
        return SymbolVisibility.PUBLIC
    if "protected" in value.split():
        return SymbolVisibility.PROTECTED
    if "private" in value.split():
        return SymbolVisibility.PRIVATE
    return SymbolVisibility.INTERNAL


def _annotations(node: Node, source: bytes) -> list[str]:
    modifiers = next((child for child in node.children if child.type == "modifiers"), None)
    if modifiers is None:
        return []
    values: list[str] = []
    for child in walk(modifiers):
        if child.type not in {"annotation", "marker_annotation"}:
            continue
        value = node_text(child, source).removeprefix("@").split("(", 1)[0]
        if value:
            values.append(value)
    return sorted(set(values))


def _containing_type_is_exposed(node: Node, source: bytes) -> bool:
    parent = node.parent
    while parent is not None:
        if parent.type in TYPE_NODES:
            return _visibility(parent, source) in {SymbolVisibility.PUBLIC, SymbolVisibility.PROTECTED}
        parent = parent.parent
    return False


def _node_lines(node: Node) -> int:
    return node.end_point.row - node.start_point.row + 1


def _module_for_path(path: str) -> str:
    parts = list(PurePosixPath(path).parts)
    if "java" in parts:
        parts = parts[parts.index("java") + 1 :]
    return ".".join(parts[:-1]) or PurePosixPath(path).stem


def _build_module_for_path(path: str) -> str:
    normalized = PurePosixPath(path)
    parts = list(normalized.parts)
    if "src" not in parts:
        return "."
    prefix = parts[: parts.index("src")]
    return "/".join(prefix) or "."


def _symbol_identity(symbol: Symbol) -> str:
    name = f"{symbol.owner}.{symbol.name}" if symbol.owner else symbol.name
    return f"{symbol.kind.value}:{name}"


def _unique_symbols(symbols: list[Symbol]) -> list[Symbol]:
    seen: set[str] = set()
    result: list[Symbol] = []
    for symbol in symbols:
        identity = _symbol_identity(symbol)
        if identity not in seen:
            seen.add(identity)
            result.append(symbol)
    return result


def _unique_dependencies(dependencies: list[Dependency]) -> list[Dependency]:
    seen: set[tuple[DependencyKind, str]] = set()
    result: list[Dependency] = []
    for dependency in dependencies:
        identity = (dependency.kind, dependency.target)
        if identity not in seen:
            seen.add(identity)
            result.append(dependency)
    return result
