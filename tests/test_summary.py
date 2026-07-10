from __future__ import annotations

from sktr_core.model import FileChange, Issue, IssueCategory, IssueSeverity, ReviewContext, ReviewResult
from sktr_report.summary import risk_score


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

    assert risk_score(result) == 85
