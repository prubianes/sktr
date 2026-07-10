from __future__ import annotations

from pathlib import Path

from sktr_core.model import DependencyKind, FileChange, SymbolKind
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_python import PythonAstAnalyzer
from sktr_rules import NewDependencyDetectedRule, PublicApiChangedRule


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


def test_python_analyzer_and_enrichment_only_mark_added_imports_as_new() -> None:
    path = "src/orders/service.py"
    diff = GitDiff(
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified")],
        base_file_contents={path: "import os\n"},
        current_file_contents={path: "import os\nimport payments.client\n"},
    )
    system = PythonAstAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = NewDependencyDetectedRule().evaluate(system, context=AnalysisContext(diff=diff).review)

    assert [issue.metadata["target"] for issue in issues] == ["payments.client"]


def test_removed_public_symbol_is_available_to_deterministic_rules() -> None:
    path = "src/orders/service.py"
    diff = GitDiff(
        changed_files=[path],
        file_changes=[FileChange(path=path, status="deleted")],
        base_file_contents={path: "def create_order():\n    pass\n\ndef _private():\n    pass\n"},
    )
    system = PythonAstAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = PublicApiChangedRule().evaluate(system, context=AnalysisContext(diff=diff).review)

    assert [issue.metadata["symbol"] for issue in issues] == ["create_order"]
