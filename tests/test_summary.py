from __future__ import annotations

from sktr_core.model import FileChange, Issue, IssueCategory, IssueSeverity, ReviewContext, ReviewResult
from sktr_report.summary import breadth_penalty, risk_score


def test_score_caps_repeated_findings_from_the_same_rule() -> None:
    issues = [
        Issue(
            id=f"dependency.new:{index}",
            title="New dependency detected",
            description="A dependency was added.",
            severity=IssueSeverity.INFO,
            category=IssueCategory.COUPLING,
            rule_id="dependency.new",
        )
        for index in range(74)
    ]
    result = ReviewResult(
        status="ready",
        context=ReviewContext(
            file_changes=[FileChange(path=f"src/file_{index}.py", status="modified") for index in range(15)]
        ),
        issues=issues,
    )

    assert risk_score(result) == 100


def test_score_caps_repeated_findings_by_category() -> None:
    issues = [
        Issue(
            id=f"api.removed:{index}",
            title="Public API removed",
            description="A public symbol was removed.",
            severity=IssueSeverity.HIGH,
            category=IssueCategory.ARCHITECTURE,
            rule_id="api.removed",
        )
        for index in range(100)
    ]

    assert risk_score(ReviewResult(status="ready", issues=issues)) == 72


def test_score_reflects_independent_risk_categories() -> None:
    result = ReviewResult(
        status="ready",
        issues=[
            Issue(
                id="architecture",
                title="Architecture issue",
                description="Boundary removed.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
            ),
            Issue(
                id="maintainability",
                title="Maintainability issue",
                description="Large function.",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.MAINTAINABILITY,
            ),
        ],
    )

    assert risk_score(result) == 76


def test_score_includes_bounded_change_breadth_metadata() -> None:
    result = ReviewResult(
        status="review complete",
        context=ReviewContext(
            file_changes=[FileChange(path=f"src/file_{index}.py", status="modified") for index in range(30)]
        ),
        knowledge_summary={
            "production_changed_files": 10,
            "changed_modules": 5,
            "public_api_changes": 5,
        },
    )

    assert breadth_penalty(result) == 13
    assert risk_score(result) == 87
