from __future__ import annotations

import ast
import sys
from pathlib import Path

from sktr_core.model import (
    APIExposure,
    AnalysisDiagnostic,
    Dependency,
    DependencyKind,
    DependencyScope,
    DiagnosticSeverity,
    Location,
    Module,
    SourceFile,
    Symbol,
    SymbolKind,
    SymbolVisibility,
    System,
)
from sktr_core.plugins import AnalysisContext


class PythonAstAnalyzer:
    language = "python"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root

    def analyze(self, context: AnalysisContext) -> System:
        root = self._root(context)
        snapshot_paths = set(context.diff.current_file_contents)
        snapshot_complete = context.diff.metadata.get("graph_scope") == "repository"
        changed_files = context.review.changed_files or context.diff.changed_files
        files: list[SourceFile] = []
        diagnostics: list[AnalysisDiagnostic] = []
        for path in changed_files:
            source_file, diagnostic = self._analyze_path(
                context,
                root,
                path,
                snapshot_paths=snapshot_paths,
                snapshot_complete=snapshot_complete,
            )
            if source_file is not None:
                files.append(source_file)
            if diagnostic is not None:
                diagnostics.append(diagnostic)

        return System(
            modules=[
                Module(
                    name="python",
                    path=".",
                    files=files,
                    metadata={"language": self.language},
                )
            ]
            if files
            else [],
            diagnostics=diagnostics,
            metadata={
                "analyzer": self.__class__.__name__,
                "test_infrastructure_detected": any(
                    _is_test_path(path) for path in context.diff.repository_files
                ),
            },
        )

    def _analyze_path(
        self,
        context: AnalysisContext,
        root: Path,
        path: str,
        *,
        snapshot_paths: set[str],
        snapshot_complete: bool,
    ) -> tuple[SourceFile | None, AnalysisDiagnostic | None]:
        if not path.endswith(".py"):
            return None, None
        current_source = context.diff.current_file_contents.get(path)
        if current_source is None and (root / path).is_file():
            current_source = (root / path).read_text(encoding="utf-8")
        baseline_source = context.diff.base_file_contents.get(path)
        if current_source is None and baseline_source is None:
            return None, None
        try:
            source_file = self._analyze_file(path, current_source, baseline_source)
        except SyntaxError as error:
            return None, self._syntax_diagnostic(path, error)
        source_module = self._module_for_path(path)
        source_file.module = source_module
        for dependency in source_file.dependencies:
            dependency.source_module = source_module
            dependency.target_module = self._target_module(dependency.target, source_module)
            dependency.target_path = self._target_path(
                root,
                dependency.target,
                available_paths=snapshot_paths,
                allow_filesystem=not snapshot_complete,
            )
            dependency.scope = (
                DependencyScope.INTERNAL
                if dependency.target_path
                else self._dependency_scope(root, dependency.target)
            )
            dependency.metadata["scope"] = dependency.scope.value
        baseline_targets = source_file.metadata.get("baseline_dependencies", [])
        if isinstance(baseline_targets, list):
            source_file.metadata["baseline_dependency_modules"] = sorted(
                {
                    self._target_module(str(target), source_module)
                    for target in baseline_targets
                    if str(target)
                }
            )
        return source_file, None

    def _syntax_diagnostic(self, path: str, error: SyntaxError) -> AnalysisDiagnostic:
        return AnalysisDiagnostic(
            analyzer=self.__class__.__name__,
            file_path=path,
            severity=DiagnosticSeverity.ERROR,
            code="parse_error",
            message=error.msg,
            location=Location(
                file_path=path,
                start_line=error.lineno,
                start_column=error.offset,
            ) if error.lineno else None,
        )

    def _root(self, context: AnalysisContext) -> Path:
        if self.root is not None:
            return self.root
        if context.diff.repository_root:
            return Path(context.diff.repository_root)
        return Path.cwd()

    def _analyze_file(
        self,
        relative_path: str,
        source: str | None,
        baseline_source: str | None,
    ) -> SourceFile:
        symbols, dependencies = self._analyze_source(relative_path, source) if source is not None else ([], [])
        baseline_symbols, baseline_dependencies = (
            self._analyze_source(relative_path, baseline_source) if baseline_source is not None else ([], [])
        )
        return SourceFile(
            path=relative_path,
            language=self.language,
            symbols=symbols,
            dependencies=dependencies,
            metadata={
                "baseline_dependencies": sorted({dependency.target for dependency in baseline_dependencies}),
                "baseline_public_symbols": sorted(
                    {
                        _symbol_identity(symbol)
                        for symbol in baseline_symbols
                        if symbol.api_exposure == APIExposure.EXPORTED
                    }
                ),
                "baseline_symbols": sorted(
                    {_symbol_identity(symbol) for symbol in baseline_symbols}
                ),
            },
        )

    def _analyze_source(self, relative_path: str, source: str) -> tuple[list[Symbol], list[Dependency]]:
        tree = ast.parse(source, filename=relative_path)
        symbols: list[Symbol] = []
        dependencies: list[Dependency] = []

        for node in tree.body:
            if isinstance(node, ast.Import | ast.ImportFrom):
                dependencies.extend(self._dependencies(relative_path, node))
            elif isinstance(node, ast.ClassDef):
                symbols.append(self._symbol(relative_path, node, SymbolKind.CLASS))
                symbols.extend(
                    self._symbol(relative_path, child, SymbolKind.METHOD, owner=node.name)
                    for child in node.body
                    if isinstance(child, ast.FunctionDef | ast.AsyncFunctionDef)
                )
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                symbols.append(self._symbol(relative_path, node, SymbolKind.FUNCTION))

        return symbols, dependencies

    def _dependencies(self, relative_path: str, node: ast.Import | ast.ImportFrom) -> list[Dependency]:
        if isinstance(node, ast.Import):
            targets = [alias.name for alias in node.names]
        else:
            prefix = "." * node.level
            module = node.module or ""
            targets = [f"{prefix}{module}".rstrip(".")]

        return [
            Dependency(
                source=relative_path,
                target=target,
                kind=DependencyKind.IMPORT,
                location=self._location(relative_path, node),
            )
            for target in targets
            if target
        ]

    def _symbol(
        self,
        relative_path: str,
        node: ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef,
        kind: SymbolKind,
        owner: str | None = None,
    ) -> Symbol:
        is_public = not node.name.startswith("_") and (owner is None or not owner.startswith("_"))
        metadata: dict[str, object] = {}
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            body_start = node.body[0].lineno if node.body else node.lineno
            body_end = getattr(node, "end_lineno", None) or body_start
            metadata["body_lines"] = max(0, body_end - body_start + 1)
        return Symbol(
            name=node.name,
            kind=kind,
            owner=owner,
            visibility=SymbolVisibility.PUBLIC if is_public else SymbolVisibility.PRIVATE,
            api_exposure=APIExposure.EXPORTED if is_public else APIExposure.NOT_EXPORTED,
            location=self._location(relative_path, node),
            metadata=metadata,
        )

    def _dependency_scope(self, root: Path, target: str) -> DependencyScope:
        if target.startswith("."):
            return DependencyScope.INTERNAL
        top_level = target.split(".", 1)[0]
        if top_level in sys.stdlib_module_names:
            return DependencyScope.STANDARD_LIBRARY
        search_roots = (root, root / "src", root / "app", root / "lib", root / "packages")
        if any(
            (search_root / f"{top_level}.py").is_file()
            or (search_root / top_level / "__init__.py").is_file()
            for search_root in search_roots
        ):
            return DependencyScope.INTERNAL
        return DependencyScope.EXTERNAL

    def _module_for_path(self, path: str) -> str:
        parts = [part for part in Path(path).parts if part not in {"src", "app", "lib", "packages"}]
        return parts[0].removesuffix(".py") if parts else ""

    def _target_module(self, target: str, source_module: str) -> str:
        normalized = target.strip(".")
        return normalized.split(".", 1)[0] if normalized else source_module

    def _target_path(
        self,
        root: Path,
        target: str,
        *,
        available_paths: set[str],
        allow_filesystem: bool,
    ) -> str | None:
        if target.startswith("."):
            return None
        relative = Path(*target.split("."))
        for search_root in (root, root / "src", root / "app", root / "lib", root / "packages"):
            for candidate in (search_root / relative.with_suffix(".py"), search_root / relative / "__init__.py"):
                relative_candidate = candidate.relative_to(root).as_posix()
                if relative_candidate in available_paths or (allow_filesystem and candidate.is_file()):
                    return relative_candidate
        return None

    def _location(self, relative_path: str, node: ast.AST) -> Location:
        return Location(
            file_path=relative_path,
            start_line=getattr(node, "lineno", None),
            end_line=getattr(node, "end_lineno", None),
            start_column=self._column(getattr(node, "col_offset", None)),
            end_column=self._column(getattr(node, "end_col_offset", None)),
        )

    def _column(self, value: int | None) -> int | None:
        if value is None:
            return None
        return value + 1


def _symbol_identity(symbol: Symbol) -> str:
    qualified_name = f"{symbol.owner}.{symbol.name}" if symbol.owner else symbol.name
    return f"{symbol.kind.value}:{qualified_name}"


def _is_test_path(path: str) -> bool:
    normalized = path.replace("\\", "/")
    return "/tests/" in f"/{normalized}" or normalized.rsplit("/", 1)[-1].startswith("test_")
