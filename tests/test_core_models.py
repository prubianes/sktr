from __future__ import annotations

from pydantic import ValidationError

from sktr_core.model import (
    Dependency,
    DependencyKind,
    Issue,
    IssueCategory,
    IssueSeverity,
    Location,
    Module,
    SourceFile,
    Symbol,
    SymbolKind,
    System,
)


def test_system_model_supports_module_file_symbol_dependency_hierarchy() -> None:
    system = System(
        name="demo",
        modules=[
            Module(
                name="core",
                path="src/core",
                files=[
                    SourceFile(
                        path="src/core/service.py",
                        language="python",
                        symbols=[
                            Symbol(
                                name="ReviewService",
                                kind=SymbolKind.CLASS,
                                location=Location(file_path="src/core/service.py", start_line=3),
                            )
                        ],
                        dependencies=[
                            Dependency(
                                source="src/core/service.py",
                                target="src/core/model.py",
                                kind=DependencyKind.IMPORT,
                            )
                        ],
                    )
                ],
            )
        ],
    )

    module = system.modules[0]
    source_file = module.files[0]

    assert module.name == "core"
    assert source_file.symbols[0].kind is SymbolKind.CLASS
    assert source_file.dependencies[0].target == "src/core/model.py"


def test_issue_model_captures_severity_category_rule_and_location() -> None:
    issue = Issue(
        id="architecture.cycle",
        title="Potential cycle",
        description="A module-level cycle may make changes harder to isolate.",
        severity=IssueSeverity.HIGH,
        category=IssueCategory.ARCHITECTURE,
        location=Location(file_path="src/core/service.py", start_line=10, end_line=12),
        rule_id="architecture.no_cycles",
    )

    assert issue.severity is IssueSeverity.HIGH
    assert issue.category is IssueCategory.ARCHITECTURE
    assert issue.location is not None
    assert issue.location.end_line == 12


def test_location_rejects_non_positive_line_numbers() -> None:
    try:
        Location(file_path="src/core/service.py", start_line=0)
    except ValidationError as error:
        assert "greater than or equal to 1" in str(error)
    else:
        raise AssertionError("Expected Location to reject start_line=0")
