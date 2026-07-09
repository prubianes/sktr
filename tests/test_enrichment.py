from __future__ import annotations

from sktr_core.model import Dependency, DependencyKind, FileChange, Location, Module, SourceFile, Symbol, SymbolKind, System
from sktr_core.pipeline import ReviewPipeline
from sktr_core.plugins import GitDiff
from sktr_enrichment import KnowledgeEnrichmentEngine


def test_file_metrics() -> None:
    system = _enriched_system()
    source_file = _file(system, "orders/service.py")

    assert source_file.metadata["metrics"] == {
        "total_changed_lines": 320,
        "added_lines": 300,
        "removed_lines": 20,
        "change_ratio": 2.6667,
        "symbol_count": 2,
        "dependency_count": 6,
    }
    assert source_file.metadata["change_status"] == "modified"


def test_dependency_metrics() -> None:
    source_file = _file(_enriched_system(), "orders/service.py")
    dependency = source_file.dependencies[0]

    assert dependency.metadata["metrics"]["new_dependency"] is True
    assert dependency.metadata["metrics"]["removed_dependency"] is False
    assert dependency.metadata["metrics"]["cross_module_dependency"] is True
    assert dependency.metadata["metrics"]["same_module_dependency"] is False


def test_module_metrics() -> None:
    module = _enriched_system().modules[0]

    assert module.metadata["metrics"]["changed_files"] == 1
    assert module.metadata["metrics"]["changed_symbols"] == 2
    assert module.metadata["metrics"]["incoming_dependencies"] == 0
    assert module.metadata["metrics"]["outgoing_dependencies"] == 6


def test_risk_calculation() -> None:
    source_file = _file(_enriched_system(), "orders/service.py")

    assert source_file.metadata["risk_level"] == "HIGH"
    assert {"level": "HIGH", "reason": "file with many changes"} in source_file.metadata["risk_indicators"]
    assert {"level": "MEDIUM", "reason": "many new dependencies"} in source_file.metadata["risk_indicators"]
    assert {"level": "HIGH", "reason": "large modified symbol"} in source_file.metadata["risk_indicators"]


def test_review_priority() -> None:
    source_file = _file(_enriched_system(), "orders/service.py")

    assert source_file.metadata["review_priority"] == "HIGH"


def test_summary_generation() -> None:
    system = _enriched_system()

    assert system.metadata["knowledge_summary"] == {
        "changed_modules": 1,
        "changed_files": 1,
        "new_dependencies": 6,
        "cross_module_dependencies": 6,
        "high_risk_files": 1,
        "high_priority_reviews": 1,
    }


def test_pipeline_adds_knowledge_summary_to_review_result() -> None:
    class Analyzer:
        language = "test"

        def analyze(self, context):
            return _raw_system()

    result = ReviewPipeline(
        diff=_diff(),
        analyzers=[Analyzer()],
        enrichment_engine=KnowledgeEnrichmentEngine.default(),
    ).run()

    assert result.knowledge_summary["changed_files"] == 1
    assert result.knowledge_summary["new_dependencies"] == 6


def _enriched_system() -> System:
    return KnowledgeEnrichmentEngine.default().enrich(_raw_system(), _diff())


def _raw_system() -> System:
    system = System(
        modules=[
            Module(
                name="orders",
                files=[
                    SourceFile(
                        path="orders/service.py",
                        symbols=[
                            Symbol(
                                name="OrderService",
                                kind=SymbolKind.CLASS,
                                location=Location(file_path="orders/service.py", start_line=1, end_line=20),
                            ),
                            Symbol(
                                name="create_order",
                                kind=SymbolKind.FUNCTION,
                                location=Location(file_path="orders/service.py", start_line=21, end_line=120),
                            ),
                        ],
                        dependencies=[
                            Dependency(source="orders/service.py", target=f"payments.dep{i}", kind=DependencyKind.IMPORT)
                            for i in range(6)
                        ],
                    ),
                ],
            ),
            Module(name="payments", files=[SourceFile(path="payments/dep0.py")]),
        ]
    )
    return system


def _diff() -> GitDiff:
    return GitDiff(
        changed_files=["orders/service.py"],
        file_changes=[
            FileChange(path="orders/service.py", status="modified", added_lines=300, removed_lines=20),
        ],
    )


def _file(system: System, path: str) -> SourceFile:
    for module in system.modules:
        for source_file in module.files:
            if source_file.path == path:
                return source_file
    raise AssertionError(f"Missing file {path}")
