from __future__ import annotations

import ast
import sys
from pathlib import Path

from sktr_core.model import Dependency, DependencyKind, Location, Module, SourceFile, Symbol, SymbolKind, System
from sktr_core.plugins import AnalysisContext


class PythonAstAnalyzer:
    language = "python"

    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root

    def analyze(self, context: AnalysisContext) -> System:
        root = self._root(context)
        changed_files = context.review.changed_files or context.diff.changed_files
        files: list[SourceFile] = []
        for path in changed_files:
            if not path.endswith(".py"):
                continue
            current_source = context.diff.current_file_contents.get(path)
            if current_source is None and (root / path).is_file():
                current_source = (root / path).read_text(encoding="utf-8")
            baseline_source = context.diff.base_file_contents.get(path)
            if current_source is None and baseline_source is None:
                continue
            source_file = self._analyze_file(path, current_source, baseline_source)
            for dependency in source_file.dependencies:
                dependency.metadata["scope"] = self._dependency_scope(root, dependency.target)
            files.append(source_file)

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
            metadata={"analyzer": self.__class__.__name__},
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
        return Symbol(
            name=node.name,
            kind=kind,
            owner=owner,
            location=self._location(relative_path, node),
        )

    def _dependency_scope(self, root: Path, target: str) -> str:
        if target.startswith("."):
            return "internal"
        top_level = target.split(".", 1)[0]
        if top_level in sys.stdlib_module_names:
            return "standard_library"
        search_roots = (root, root / "src", root / "app", root / "lib", root / "packages")
        if any(
            (search_root / f"{top_level}.py").is_file()
            or (search_root / top_level / "__init__.py").is_file()
            for search_root in search_roots
        ):
            return "internal"
        return "external"

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
