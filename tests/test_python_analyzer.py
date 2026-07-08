from __future__ import annotations

from pathlib import Path

from sktr_core.model import DependencyKind, SymbolKind
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_python import PythonAstAnalyzer


def test_python_analyzer_extracts_imports_classes_functions_and_methods(tmp_path: Path) -> None:
    source_path = tmp_path / "src" / "orders" / "service.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text(
        "\n".join(
            [
                "import os",
                "import sys as system",
                "from payments.client import PaymentClient",
                "",
                "class OrderService:",
                "    def create_order(self):",
                "        pass",
                "",
                "    async def cancel_order(self):",
                "        pass",
                "",
                "def helper():",
                "    pass",
                "",
                "async def async_helper():",
                "    pass",
            ]
        ),
        encoding="utf-8",
    )

    context = AnalysisContext(
        diff=GitDiff(
            repository_root=str(tmp_path),
            changed_files=["src/orders/service.py"],
        )
    )

    system = PythonAstAnalyzer().analyze(context)

    assert len(system.modules) == 1
    source_file = system.modules[0].files[0]
    assert source_file.path == "src/orders/service.py"
    assert source_file.language == "python"
    assert [(symbol.name, symbol.kind) for symbol in source_file.symbols] == [
        ("OrderService", SymbolKind.CLASS),
        ("create_order", SymbolKind.METHOD),
        ("cancel_order", SymbolKind.METHOD),
        ("helper", SymbolKind.FUNCTION),
        ("async_helper", SymbolKind.FUNCTION),
    ]
    assert [(dependency.target, dependency.kind) for dependency in source_file.dependencies] == [
        ("os", DependencyKind.IMPORT),
        ("sys", DependencyKind.IMPORT),
        ("payments.client", DependencyKind.IMPORT),
    ]


def test_python_analyzer_ignores_non_python_and_missing_files(tmp_path: Path) -> None:
    source_path = tmp_path / "src" / "orders" / "service.py"
    source_path.parent.mkdir(parents=True)
    source_path.write_text("def helper():\n    pass\n", encoding="utf-8")

    context = AnalysisContext(
        diff=GitDiff(
            repository_root=str(tmp_path),
            changed_files=[
                "src/orders/service.py",
                "README.md",
                "src/orders/deleted.py",
            ],
        )
    )

    system = PythonAstAnalyzer().analyze(context)

    assert len(system.modules) == 1
    assert [source_file.path for source_file in system.modules[0].files] == ["src/orders/service.py"]
