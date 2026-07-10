from __future__ import annotations

from sktr_core.config import ForbiddenDependency, RuleConfig
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
    DependencyCycleRule,
    HighFanOutRule,
    LargeFileChangedRule,
    LargeFunctionDetectedRule,
    NewDependencyDetectedRule,
    MissingTestsRule,
    PublicApiChangedRule,
    RuleRegistry,
    rules_from_config,
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
                    metadata={
                        "metrics": {
                            "new_dependency": True,
                            "cross_module_dependency": True,
                            "source_module": "controllers",
                            "target_module": "repositories",
                        }
                    },
                )
            ],
        )
    )

    issues = NewDependencyDetectedRule().evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].title == "New dependency detected"
    assert issues[0].metadata["target"] == "repositories"
    assert issues[0].metadata["rule_key"] == "new_dependency"


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
    assert issues[0].metadata["max_changed_lines"] == "100"


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
    assert issues[0].metadata["max_lines"] == "20"


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
            ForbiddenDependency(
                source="controllers",
                target="repositories",
                reason="Controllers should access repositories through services.",
            ),
        ]
    )

    issues = rule.evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].title == "Forbidden dependency"
    assert issues[0].metadata["source"] == "controllers/order_controller.py"
    assert issues[0].metadata["target"] == "repositories/order_repository.py"
    assert issues[0].metadata["rule_key"] == "forbidden_dependency"
    assert issues[0].metadata["reason"] == "Controllers should access repositories through services."


def test_disabled_rules_are_not_registered() -> None:
    rules = rules_from_config(
        RuleConfig(
            enabled=["large_file"],
            forbidden_dependencies=[
                ForbiddenDependency(source="controllers", target="repositories"),
            ],
        )
    )

    assert [rule.id for rule in rules] == ["change.large_file"]


def test_dependency_cycle_rule_reports_module_cycle() -> None:
    system = _system_with_file(
        SourceFile(
            path="orders/service.py",
            dependencies=[
                Dependency(
                    source="orders/service.py",
                    target="payments.client",
                    kind=DependencyKind.IMPORT,
                    metadata={"metrics": {"source_module": "orders", "target_module": "payments", "cross_module_dependency": True}},
                ),
                Dependency(
                    source="payments/client.py",
                    target="orders.service",
                    kind=DependencyKind.IMPORT,
                    metadata={"metrics": {"source_module": "payments", "target_module": "orders", "cross_module_dependency": True}},
                ),
            ],
        )
    )

    issues = DependencyCycleRule().evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert "orders -> payments -> orders" in issues[0].description


def test_high_fan_out_rule_reports_module_above_threshold() -> None:
    dependencies = [
        Dependency(
            source="orders/service.py",
            target=f"module_{index}",
            kind=DependencyKind.IMPORT,
            metadata={
                "metrics": {
                    "source_module": "orders",
                    "target_module": f"module_{index}",
                    "cross_module_dependency": True,
                }
            },
        )
        for index in range(3)
    ]
    system = _system_with_file(SourceFile(path="orders/service.py", dependencies=dependencies))

    issues = HighFanOutRule(threshold=2).evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].metadata["fan_out"] == "3"


def test_dependency_rules_ignore_non_architecture_imports() -> None:
    dependencies = [
        Dependency(
            source="orders/service.py",
            target=target,
            kind=DependencyKind.IMPORT,
            metadata={
                "metrics": {
                    "new_dependency": True,
                    "cross_module_dependency": False,
                    "source_module": "orders",
                    "target_module": target,
                }
            },
        )
        for target in ("os", "pydantic", "orders")
    ]
    system = _system_with_file(SourceFile(path="orders/service.py", dependencies=dependencies))

    assert NewDependencyDetectedRule().evaluate(system, ReviewContext()) == []
    assert HighFanOutRule(threshold=1).evaluate(system, ReviewContext()) == []


def test_new_dependencies_are_grouped_by_module_edge() -> None:
    dependencies = [
        Dependency(
            source=f"orders/file_{index}.py",
            target=f"payments.client_{index}",
            kind=DependencyKind.IMPORT,
            metadata={
                "metrics": {
                    "new_dependency": True,
                    "cross_module_dependency": True,
                    "source_module": "orders",
                    "target_module": "payments",
                }
            },
        )
        for index in range(3)
    ]
    system = _system_with_file(SourceFile(path="orders/service.py", dependencies=dependencies))

    issues = NewDependencyDetectedRule().evaluate(system, ReviewContext())

    assert len(issues) == 1
    assert issues[0].metadata["dependency_count"] == "3"
    assert "3 imports" in issues[0].description


def test_public_api_removal_suppresses_methods_owned_by_removed_class() -> None:
    system = _system_with_file(
        SourceFile(
            path="reporter.py",
            metadata={
                "removed_symbols": [
                    "class:Reporter",
                    "method:Reporter.render",
                    "method:Output.write",
                ]
            },
        )
    )

    issues = PublicApiChangedRule().evaluate(system, ReviewContext())

    assert [issue.metadata["symbol"] for issue in issues] == ["Reporter", "Output.write"]


def test_missing_tests_rule_only_reports_when_no_test_file_changed() -> None:
    system = _system_with_file(SourceFile(path="src/orders/service.py"))
    without_tests = ReviewContext(file_changes=[FileChange(path="src/orders/service.py", status="modified")])
    with_tests = ReviewContext(
        file_changes=[
            FileChange(path="src/orders/service.py", status="modified"),
            FileChange(path="tests/test_orders.py", status="modified"),
        ]
    )

    assert len(MissingTestsRule().evaluate(system, without_tests)) == 1
    assert MissingTestsRule().evaluate(system, with_tests) == []


def test_architecture_rules_ignore_test_modules() -> None:
    test_file = SourceFile(
        path="tests/test_service.py",
        dependencies=[
            Dependency(
                source="tests/test_service.py",
                target=f"module_{index}",
                kind=DependencyKind.IMPORT,
                metadata={"metrics": {"source_module": "tests", "target_module": f"module_{index}"}},
            )
            for index in range(3)
        ],
        metadata={"removed_symbols": ["function:test_old_behavior"]},
    )
    system = _system_with_file(test_file)

    assert HighFanOutRule(threshold=1).evaluate(system, ReviewContext()) == []
    assert PublicApiChangedRule().evaluate(system, ReviewContext()) == []


def _system_with_file(source_file: SourceFile) -> System:
    return System(
        modules=[
            Module(
                name="python",
                files=[source_file],
            )
        ]
    )
