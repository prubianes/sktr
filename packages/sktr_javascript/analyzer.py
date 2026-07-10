from __future__ import annotations

import json
import os
from pathlib import Path, PurePosixPath

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Node

from sktr_core.model import (
    Dependency,
    DependencyKind,
    DependencyScope,
    Module,
    SourceFile,
    Symbol,
    SymbolKind,
    System,
)
from sktr_core.plugins import AnalysisContext
from sktr_treesitter.parser import TreeSitterParser, location, node_text, walk

EXTENSIONS = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"}
RESOLUTION_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


class JavaScriptTypeScriptAnalyzer:
    language = "javascript-typescript"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root
        self.parsers = {
            "javascript": TreeSitterParser(tree_sitter_javascript.language(), analyzer=self.language),
            "typescript": TreeSitterParser(tree_sitter_typescript.language_typescript(), analyzer=self.language),
            "tsx": TreeSitterParser(tree_sitter_typescript.language_tsx(), analyzer=self.language),
        }

    def analyze(self, context: AnalysisContext) -> System:
        root = self._root(context)
        changed_paths = [
            path
            for path in (context.review.changed_files or context.diff.changed_files)
            if PurePosixPath(path).suffix.lower() in EXTENSIONS
        ]
        if not changed_paths:
            return System(metadata={"analyzer": self.__class__.__name__})
        workspaces = _workspace_packages(root)
        files: list[SourceFile] = []
        diagnostics = []
        for path in changed_paths:
            current = context.diff.current_file_contents.get(path)
            if current is None and (root / path).is_file():
                current = (root / path).read_text(encoding="utf-8")
            baseline = context.diff.base_file_contents.get(path)
            if current is None and baseline is None:
                continue
            source_file, file_diagnostics = self._analyze_file(root, workspaces, path, current, baseline)
            files.append(source_file)
            diagnostics.extend(file_diagnostics)

        return System(
            modules=[Module(name=self.language, path=".", files=files, metadata={"language": self.language})]
            if files
            else [],
            diagnostics=diagnostics,
            metadata={"analyzer": self.__class__.__name__},
        )

    def _analyze_file(
        self,
        root: Path,
        workspaces: dict[str, Path],
        path: str,
        current: str | None,
        baseline: str | None,
    ) -> tuple[SourceFile, list]:
        parser = self._parser(path)
        symbols: list[Symbol] = []
        dependencies: list[Dependency] = []
        diagnostics = []
        if current is not None:
            parsed = parser.parse(current, file_path=path)
            diagnostics.extend(parsed.diagnostics)
            symbols = _symbols(path, parsed.tree.root_node, parsed.source)
            dependencies = _dependencies(path, parsed.tree.root_node, parsed.source)
        baseline_symbols: list[Symbol] = []
        baseline_dependencies: list[Dependency] = []
        if baseline is not None:
            parsed_baseline = parser.parse(baseline, file_path=path)
            baseline_symbols = _symbols(path, parsed_baseline.tree.root_node, parsed_baseline.source)
            baseline_dependencies = _dependencies(path, parsed_baseline.tree.root_node, parsed_baseline.source)

        source_module = _module_for_path(path, root, workspaces)
        for dependency in dependencies:
            _resolve_dependency(dependency, root=root, workspaces=workspaces, source_module=source_module)
        return (
            SourceFile(
                path=path,
                language=_language_for_path(path),
                module=source_module,
                symbols=symbols,
                dependencies=dependencies,
                metadata={
                    "baseline_dependencies": sorted({item.target for item in baseline_dependencies}),
                    "baseline_symbols": sorted({_symbol_identity(symbol) for symbol in baseline_symbols}),
                },
            ),
            diagnostics,
        )

    def _parser(self, path: str) -> TreeSitterParser:
        suffix = PurePosixPath(path).suffix.lower()
        if suffix == ".tsx":
            return self.parsers["tsx"]
        if suffix == ".ts":
            return self.parsers["typescript"]
        return self.parsers["javascript"]

    def _root(self, context: AnalysisContext) -> Path:
        if self.root is not None:
            return self.root
        return Path(context.diff.repository_root) if context.diff.repository_root else Path.cwd()


def _symbols(path: str, root: Node, source: bytes) -> list[Symbol]:
    symbols: list[Symbol] = []
    for node in walk(root):
        if node.type in {"class_declaration", "class"}:
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(_symbol(path, node, name, SymbolKind.CLASS))
                body = node.child_by_field_name("body")
                for method in body.named_children if body else []:
                    if method.type == "method_definition":
                        method_name = node_text(method.child_by_field_name("name"), source)
                        if method_name:
                            symbols.append(_symbol(path, method, method_name, SymbolKind.METHOD, owner=name))
        elif node.type in {"function_declaration", "generator_function_declaration"}:
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(_symbol(path, node, name, SymbolKind.FUNCTION))
        elif node.type == "interface_declaration":
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(_symbol(path, node, name, SymbolKind.INTERFACE))
        elif node.type == "type_alias_declaration":
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(_symbol(path, node, name, SymbolKind.TYPE))
        elif node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in {"arrow_function", "function_expression"}:
                name = node_text(node.child_by_field_name("name"), source)
                if name:
                    symbols.append(_symbol(path, node, name, SymbolKind.FUNCTION))
    return _unique_symbols(symbols)


def _dependencies(path: str, root: Node, source: bytes) -> list[Dependency]:
    dependencies: list[Dependency] = []
    for node in walk(root):
        target = ""
        if node.type in {"import_statement", "export_statement"}:
            string_node = next((child for child in node.named_children if child.type == "string"), None)
            target = _string_value(string_node, source)
        elif node.type == "call_expression":
            function = node_text(node.child_by_field_name("function"), source)
            if function in {"require", "import"}:
                arguments = node.child_by_field_name("arguments")
                string_node = next(
                    (child for child in arguments.named_children if child.type == "string"),
                    None,
                ) if arguments else None
                target = _string_value(string_node, source)
        if target:
            dependencies.append(
                Dependency(
                    source=path,
                    target=target,
                    kind=DependencyKind.IMPORT,
                    location=location(path, node),
                )
            )
    return _unique_dependencies(dependencies)


def _resolve_dependency(
    dependency: Dependency,
    *,
    root: Path,
    workspaces: dict[str, Path],
    source_module: str,
) -> None:
    dependency.source_module = source_module
    if dependency.target.startswith("."):
        target_path = _resolve_relative(root, dependency.source, dependency.target)
        dependency.scope = DependencyScope.INTERNAL
        dependency.target_path = target_path
        dependency.target_module = _module_for_path(target_path, root, workspaces) if target_path else source_module
    else:
        package_name = _package_name(dependency.target)
        workspace = workspaces.get(package_name)
        if workspace is not None:
            dependency.scope = DependencyScope.INTERNAL
            dependency.target_module = package_name
            dependency.target_path = workspace.relative_to(root).as_posix()
        else:
            dependency.scope = DependencyScope.EXTERNAL
            dependency.target_module = package_name
    dependency.metadata["scope"] = dependency.scope.value


def _resolve_relative(root: Path, source_path: str, target: str) -> str | None:
    base = Path(os.path.normpath((root / source_path).parent / target))
    candidates = [base]
    candidates.extend(base.with_suffix(extension) for extension in RESOLUTION_EXTENSIONS)
    candidates.extend(base / f"index{extension}" for extension in RESOLUTION_EXTENSIONS)
    for candidate in candidates:
        if candidate.is_file():
            return candidate.relative_to(root).as_posix()
    return None


def _workspace_packages(root: Path) -> dict[str, Path]:
    packages: dict[str, Path] = {}
    for package_json in root.rglob("package.json"):
        if "node_modules" in package_json.parts:
            continue
        try:
            name = json.loads(package_json.read_text(encoding="utf-8")).get("name")
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(name, str) and name:
            packages[name] = package_json.parent
    return packages


def _module_for_path(path: str | None, root: Path, workspaces: dict[str, Path]) -> str:
    if path:
        absolute = (root / path).resolve()
        for name, workspace in sorted(workspaces.items(), key=lambda item: len(item[1].parts), reverse=True):
            if absolute == workspace.resolve() or workspace.resolve() in absolute.parents:
                return name
    parts = [part for part in PurePosixPath(path or "").parts if part not in {"src", "app", "lib", "packages"}]
    return parts[0].split(".", 1)[0] if parts else ""


def _package_name(target: str) -> str:
    parts = target.split("/")
    return "/".join(parts[:2]) if target.startswith("@") else parts[0]


def _language_for_path(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    return "typescript" if suffix in {".ts", ".tsx"} else "javascript"


def _string_value(node: Node | None, source: bytes) -> str:
    value = node_text(node, source)
    return value[1:-1] if len(value) >= 2 and value[0] in {'"', "'", "`"} else value


def _symbol(path: str, node: Node, name: str, kind: SymbolKind, owner: str | None = None) -> Symbol:
    return Symbol(name=name, kind=kind, owner=owner, location=location(path, node))


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
    seen: set[str] = set()
    result: list[Dependency] = []
    for dependency in dependencies:
        if dependency.target not in seen:
            seen.add(dependency.target)
            result.append(dependency)
    return result
