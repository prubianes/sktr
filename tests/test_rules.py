from __future__ import annotations

from sktr_core.config import ForbiddenDependency
from sktr_core.model import (
    Dependency,
    DependencyKind,
    FileChange,
    Location,
    Module,
    ReviewContext,
    SourceFile,
    Symbol,
    SymbolKind,
    System,
)
from sktr_rules import (
    ForbiddenDependencyRule,
    LargeFileChangedRule,
    LargeFunctionDetectedRule,
    NewDependencyDetectedRule,
    RuleRegistry,
)


def test_rule_registry_runs_multiple_rules() -> None:
    registry = RuleRegistry(
        [
            NewDependencyDetectedRule(),
            LargeFileChangedRule(threshold=10),
        ]
    )

    assert [rule.id for rule in registry.all()] == ["dependency.new", "change.large_file"]


def test_new_dependency_detected_rule_reports_import_dependencies() -> None:
    system = _system_with_file(
        SourceFile(
            path="controllers/order_controller.py",
            dependencies=[
                Dependency(
                    source="controllers/order_controller.py",
                    target="repositories.order_repository",
                    kind=DependencyKind.IMPORT,
                )
            ],
        )
    )

    issues = NewDependencyDetectedRule().evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].title == "New dependency detected"
    assert issues[0].metadata["target"] == "repositories.order_repository"


def test_large_file_changed_rule_reports_large_changed_file() -> None:
    context = ReviewContext(
        file_changes=[
            FileChange(path="src/small.py", status="modified", added_lines=3, removed_lines=2),
            FileChange(path="src/large.py", status="modified", added_lines=90, removed_lines=20),
        ]
    )

    issues = LargeFileChangedRule(threshold=100).evaluate(System(), context)

    assert len(issues) == 1
    assert issues[0].metadata["path"] == "src/large.py"
    assert issues[0].metadata["changed_lines"] == "110"


def test_large_function_detected_rule_reports_large_function() -> None:
    system = _system_with_file(
        SourceFile(
            path="services/orders.py",
            symbols=[
                Symbol(
                    name="process_order",
                    kind=SymbolKind.FUNCTION,
                    location=Location(file_path="services/orders.py", start_line=1, end_line=25),
                )
            ],
        )
    )

    issues = LargeFunctionDetectedRule(threshold=20).evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].metadata["symbol"] == "process_order"
    assert issues[0].metadata["line_count"] == "25"


def test_forbidden_dependency_rule_reports_direct_import_between_configured_modules() -> None:
    system = _system_with_file(
        SourceFile(
            path="controllers/order_controller.py",
            dependencies=[
                Dependency(
                    source="controllers/order_controller.py",
                    target="repositories.order_repository",
                    kind=DependencyKind.IMPORT,
                    location=Location(file_path="controllers/order_controller.py", start_line=1),
                )
            ],
        )
    )
    rule = ForbiddenDependencyRule(
        forbidden_dependencies=[
            ForbiddenDependency(source="controllers", target="repositories"),
        ]
    )

    issues = rule.evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].title == "Direct import between forbidden modules"
    assert issues[0].metadata["source"] == "controllers/order_controller.py"
    assert issues[0].metadata["target"] == "repositories/order_repository.py"


def _system_with_file(source_file: SourceFile) -> System:
    return System(
        modules=[
            Module(
                name="python",
                files=[source_file],
            )
        ]
    )
