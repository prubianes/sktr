from __future__ import annotations

import json
import os
import re
from pathlib import Path, PurePosixPath

import tree_sitter_javascript
import tree_sitter_typescript
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
        snapshot_complete = context.diff.metadata.get("graph_scope") == "repository"
        available_paths = set(context.diff.current_file_contents)
        changed_paths = [
            path
            for path in (context.review.changed_files or context.diff.changed_files)
            if PurePosixPath(path).suffix.lower() in EXTENSIONS
        ]
        if not changed_paths:
            return System(metadata={"analyzer": self.__class__.__name__})
        workspaces = _workspace_packages(
            root,
            sources=context.diff.current_file_contents if snapshot_complete else None,
        )
        path_aliases = _tsconfig_paths(
            root,
            sources=context.diff.current_file_contents if snapshot_complete else None,
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
            source_file, file_diagnostics = self._analyze_file(
                root,
                workspaces,
                path,
                current,
                baseline,
                available_paths=available_paths,
                allow_filesystem=not snapshot_complete,
                path_aliases=path_aliases,
            )
            files.append(source_file)
            diagnostics.extend(file_diagnostics)

        return System(
            modules=[Module(name=self.language, path=".", files=files, metadata={"language": self.language})]
            if files
            else [],
            diagnostics=diagnostics,
            metadata={
                "analyzer": self.__class__.__name__,
                "test_infrastructure_detected": _test_infrastructure(root),
            },
        )

    def _analyze_file(
        self,
        root: Path,
        workspaces: dict[str, Path],
        path: str,
        current: str | None,
        baseline: str | None,
        *,
        available_paths: set[str],
        allow_filesystem: bool,
        path_aliases: list[tuple[str, str]],
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
            _resolve_dependency(
                dependency,
                root=root,
                workspaces=workspaces,
                source_module=source_module,
                available_paths=available_paths,
                allow_filesystem=allow_filesystem,
                path_aliases=path_aliases,
            )
        for dependency in baseline_dependencies:
            _resolve_dependency(
                dependency,
                root=root,
                workspaces=workspaces,
                source_module=source_module,
                available_paths=available_paths,
                allow_filesystem=allow_filesystem,
                path_aliases=path_aliases,
            )
        return (
            SourceFile(
                path=path,
                language=_language_for_path(path),
                module=source_module,
                symbols=symbols,
                dependencies=dependencies,
                metadata={
                    "package": _package_for_path(path, root, workspaces),
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
    exported_names = _exported_names(root, source)
    for node in walk(root):
        if node.type in {"class_declaration", "class"}:
            name = node_text(node.child_by_field_name("name"), source)
            if not name and _inside_export(node):
                name = "default"
            if name:
                exported = name in exported_names or _inside_export(node)
                symbols.append(_symbol(path, node, name, SymbolKind.CLASS, exported=exported))
                body = node.child_by_field_name("body")
                for method in body.named_children if body else []:
                    if method.type == "method_definition":
                        method_name = node_text(method.child_by_field_name("name"), source)
                        if method_name:
                            symbols.append(
                                _symbol(
                                    path,
                                    method,
                                    method_name,
                                    SymbolKind.METHOD,
                                    owner=name,
                                    exported=exported and not method_name.startswith("#"),
                                )
                            )
        elif node.type in {"function_declaration", "generator_function_declaration"}:
            name = node_text(node.child_by_field_name("name"), source)
            if not name and _inside_export(node):
                name = "default"
            if name:
                symbols.append(
                    _symbol(
                        path,
                        node,
                        name,
                        SymbolKind.FUNCTION,
                        exported=name in exported_names or _inside_export(node),
                    )
                )
        elif node.type == "interface_declaration":
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(
                    _symbol(
                        path,
                        node,
                        name,
                        SymbolKind.INTERFACE,
                        exported=name in exported_names or _inside_export(node),
                    )
                )
        elif node.type == "type_alias_declaration":
            name = node_text(node.child_by_field_name("name"), source)
            if name:
                symbols.append(
                    _symbol(
                        path,
                        node,
                        name,
                        SymbolKind.TYPE,
                        exported=name in exported_names or _inside_export(node),
                    )
                )
        elif node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in {"arrow_function", "function_expression"}:
                name = node_text(node.child_by_field_name("name"), source)
                if name:
                    symbols.append(
                        _symbol(
                            path,
                            node,
                            name,
                            SymbolKind.FUNCTION,
                            exported=name in exported_names or _inside_export(node),
                        )
                    )
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
    available_paths: set[str],
    allow_filesystem: bool,
    path_aliases: list[tuple[str, str]],
) -> None:
    dependency.source_module = source_module
    if dependency.target.startswith("."):
        target_path = _resolve_relative(
            root,
            dependency.source,
            dependency.target,
            available_paths=available_paths,
            allow_filesystem=allow_filesystem,
        )
        dependency.scope = DependencyScope.INTERNAL
        dependency.target_path = target_path
        dependency.target_module = _module_for_path(target_path, root, workspaces) if target_path else source_module
    else:
        alias_path = _resolve_alias(
            root,
            dependency.target,
            path_aliases,
            available_paths=available_paths,
            allow_filesystem=allow_filesystem,
        )
        if alias_path:
            dependency.scope = DependencyScope.INTERNAL
            dependency.target_path = alias_path
            dependency.target_module = _module_for_path(alias_path, root, workspaces)
            dependency.metadata["scope"] = dependency.scope.value
            return
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


def _resolve_relative(
    root: Path,
    source_path: str,
    target: str,
    *,
    available_paths: set[str],
    allow_filesystem: bool,
) -> str | None:
    base = Path(os.path.normpath((root / source_path).parent / target))
    return _resolve_module_path(
        root,
        base,
        available_paths=available_paths,
        allow_filesystem=allow_filesystem,
    )


def _resolve_module_path(
    root: Path,
    base: Path,
    *,
    available_paths: set[str],
    allow_filesystem: bool,
) -> str | None:
    candidates = [base]
    candidates.extend(base.with_suffix(extension) for extension in RESOLUTION_EXTENSIONS)
    candidates.extend(base / f"index{extension}" for extension in RESOLUTION_EXTENSIONS)
    for candidate in candidates:
        relative_candidate = candidate.relative_to(root).as_posix()
        if relative_candidate in available_paths or (allow_filesystem and candidate.is_file()):
            return relative_candidate
    return None


def _workspace_packages(root: Path, *, sources: dict[str, str] | None = None) -> dict[str, Path]:
    packages: dict[str, Path] = {}
    if sources is not None:
        package_sources = [
            (root / path, source)
            for path, source in sources.items()
            if PurePosixPath(path).name == "package.json" and "node_modules" not in PurePosixPath(path).parts
        ]
    else:
        package_sources = []
        for package_json in root.rglob("package.json"):
            if "node_modules" in package_json.parts:
                continue
            try:
                package_sources.append((package_json, package_json.read_text(encoding="utf-8")))
            except OSError:
                continue
    for package_json, source in package_sources:
        try:
            name = json.loads(source).get("name")
        except json.JSONDecodeError:
            continue
        if isinstance(name, str) and name:
            packages[name] = package_json.parent
    return packages


def _tsconfig_paths(
    root: Path,
    *,
    sources: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    source = sources.get("tsconfig.json") if sources is not None else None
    if source is None:
        try:
            source = (root / "tsconfig.json").read_text(encoding="utf-8")
        except OSError:
            return []
    try:
        data = json.loads(_strip_json_comments(source))
    except json.JSONDecodeError:
        return []
    compiler = data.get("compilerOptions", {})
    if not isinstance(compiler, dict):
        return []
    base_url = compiler.get("baseUrl", ".")
    paths = compiler.get("paths", {})
    if not isinstance(base_url, str) or not isinstance(paths, dict):
        return []
    aliases: list[tuple[str, str]] = []
    for pattern, replacements in sorted(paths.items()):
        if not isinstance(pattern, str) or not isinstance(replacements, list):
            continue
        aliases.extend(
            (pattern, str(PurePosixPath(base_url) / replacement))
            for replacement in replacements
            if isinstance(replacement, str)
        )
    return aliases


def _strip_json_comments(source: str) -> str:
    source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return re.sub(r"(^|\s)//.*$", r"\1", source, flags=re.MULTILINE)


def _resolve_alias(
    root: Path,
    target: str,
    aliases: list[tuple[str, str]],
    *,
    available_paths: set[str],
    allow_filesystem: bool,
) -> str | None:
    for pattern, replacement in aliases:
        wildcard = ""
        if "*" in pattern:
            prefix, suffix = pattern.split("*", 1)
            if not target.startswith(prefix) or not target.endswith(suffix):
                continue
            end = len(target) - len(suffix) if suffix else len(target)
            wildcard = target[len(prefix):end]
        elif target != pattern:
            continue
        resolved = _resolve_module_path(
            root,
            root / replacement.replace("*", wildcard),
            available_paths=available_paths,
            allow_filesystem=allow_filesystem,
        )
        if resolved:
            return resolved
    return None


def _test_infrastructure(root: Path) -> bool:
    config_names = ("jest.config.*", "vitest.config.*", "playwright.config.*", "cypress.config.*")
    if any(next(root.rglob(pattern), None) is not None for pattern in config_names):
        return True
    for package_json in root.rglob("package.json"):
        if "node_modules" in package_json.parts:
            continue
        try:
            data = json.loads(package_json.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scripts = data.get("scripts", {})
        dependencies = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
        if isinstance(scripts, dict) and scripts.get("test"):
            return True
        if isinstance(dependencies, dict) and any(
            name in dependencies for name in ("jest", "vitest", "@playwright/test", "cypress")
        ):
            return True
    return False


def _module_for_path(path: str | None, root: Path, workspaces: dict[str, Path]) -> str:
    if path:
        absolute = (root / path).resolve()
        for name, workspace in sorted(workspaces.items(), key=lambda item: len(item[1].parts), reverse=True):
            if workspace.resolve() == root.resolve():
                continue
            if absolute == workspace.resolve() or workspace.resolve() in absolute.parents:
                return name
    parts = list(PurePosixPath(path or "").parts)
    if parts and parts[0] in {"src", "lib"}:
        parts = parts[1:]
    directories = [part for part in parts[:-1] if not (part.startswith("(") and part.endswith(")"))]
    if not directories:
        return PurePosixPath(path or "").stem
    if directories[0] == "components" and len(directories) > 1:
        return "/".join(directories[:2])
    if directories[0] == "app":
        depth = 3 if len(directories) > 1 and directories[1] == "api" else 2
        return "/".join(directories[:depth])
    return directories[0]


def _package_for_path(path: str, root: Path, workspaces: dict[str, Path]) -> str | None:
    absolute = (root / path).resolve()
    for name, workspace in sorted(workspaces.items(), key=lambda item: len(item[1].parts), reverse=True):
        if absolute == workspace.resolve() or workspace.resolve() in absolute.parents:
            return name
    return None


def _package_name(target: str) -> str:
    parts = target.split("/")
    return "/".join(parts[:2]) if target.startswith("@") else parts[0]


def _language_for_path(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    return "typescript" if suffix in {".ts", ".tsx"} else "javascript"


def _string_value(node: Node | None, source: bytes) -> str:
    value = node_text(node, source)
    return value[1:-1] if len(value) >= 2 and value[0] in {'"', "'", "`"} else value


def _symbol(
    path: str,
    node: Node,
    name: str,
    kind: SymbolKind,
    owner: str | None = None,
    *,
    exported: bool = False,
) -> Symbol:
    body = node.child_by_field_name("body")
    if body is None and node.type == "variable_declarator":
        value = node.child_by_field_name("value")
        body = value.child_by_field_name("body") if value is not None else None
    metadata: dict[str, object] = {"body_lines": _node_lines(body)} if body is not None else {}
    if body is not None and kind in {SymbolKind.FUNCTION, SymbolKind.METHOD}:
        metadata.update(_function_metrics(body, name))
    return Symbol(
        name=name,
        kind=kind,
        owner=owner,
        visibility=SymbolVisibility.PUBLIC if exported else SymbolVisibility.INTERNAL,
        api_exposure=APIExposure.EXPORTED if exported else APIExposure.NOT_EXPORTED,
        location=location(path, node),
        metadata=metadata,
    )


def _node_lines(node: Node) -> int:
    return node.end_point.row - node.start_point.row + 1


def _inside_export(node: Node) -> bool:
    parent = node.parent
    while parent is not None and parent.type in {"lexical_declaration", "variable_declaration"}:
        parent = parent.parent
    return parent is not None and parent.type == "export_statement"


def _exported_names(root: Node, source: bytes) -> set[str]:
    names: set[str] = set()
    for node in walk(root):
        if node.type != "export_statement":
            continue
        declaration = next(
            (
                child
                for child in node.named_children
                if child.type.endswith("declaration") or child.type in {"class", "lexical_declaration"}
            ),
            None,
        )
        if declaration is not None:
            name = node_text(declaration.child_by_field_name("name"), source)
            if name:
                names.add(name)
            if declaration.type in {"lexical_declaration", "variable_declaration"}:
                for declarator in declaration.named_children:
                    if declarator.type == "variable_declarator":
                        value = node_text(declarator.child_by_field_name("name"), source)
                        if value:
                            names.add(value)
        text = node_text(node, source)
        match = re.search(r"export\s*\{([^}]*)\}", text, re.DOTALL)
        if match:
            for item in match.group(1).split(","):
                local_name = item.strip().split(" as ", 1)[0].strip()
                if local_name:
                    names.add(local_name)
        default_match = re.match(r"export\s+default\s+([A-Za-z_$][\w$]*)", text)
        if default_match:
            names.add(default_match.group(1))
    source_text = source.decode("utf-8", errors="replace")
    names.update(re.findall(r"(?:module\.)?exports\.([A-Za-z_$][\w$]*)\s*=", source_text))
    for match in re.finditer(r"module\.exports\s*=\s*\{([^}]*)\}", source_text, re.DOTALL):
        for item in match.group(1).split(","):
            local_name = item.strip().split(":", 1)[0].strip()
            if re.fullmatch(r"[A-Za-z_$][\w$]*", local_name):
                names.add(local_name)
    commonjs_default = re.search(r"module\.exports\s*=\s*([A-Za-z_$][\w$]*)", source_text)
    if commonjs_default:
        names.add(commonjs_default.group(1))
    return names


def _function_metrics(body: Node, name: str) -> dict[str, object]:
    nodes = list(walk(body))
    control_types = {
        "if_statement",
        "switch_statement",
        "for_statement",
        "for_in_statement",
        "while_statement",
        "do_statement",
        "catch_clause",
        "ternary_expression",
    }
    complexity = 1 + sum(node.type in control_types for node in nodes)
    statement_count = sum(node.type.endswith("_statement") for node in nodes)
    nested_functions = sum(
        node is not body and node.type in {"arrow_function", "function_expression", "function_declaration"}
        for node in nodes
    )
    jsx_rows = {
        row
        for node in nodes
        if node.type in {"jsx_element", "jsx_self_closing_element", "jsx_fragment"}
        for row in range(node.start_point.row, node.end_point.row + 1)
    }
    body_lines = max(_node_lines(body), 1)
    if name[:1].isupper():
        role = "ui_component"
    elif name.startswith("use") and len(name) > 3 and name[3].isupper():
        role = "hook"
    else:
        role = "function"
    return {
        "complexity": complexity,
        "statement_count": statement_count,
        "nested_function_count": nested_functions,
        "declarative_ratio": round(min(len(jsx_rows) / body_lines, 1.0), 4),
        "role": role,
    }


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
