from __future__ import annotations

from sktr_core.model import IssueCategory, IssueSeverity, ReviewResult

SEVERITY_WEIGHTS = {
    IssueSeverity.CRITICAL: 65,
    IssueSeverity.HIGH: 18,
    IssueSeverity.MEDIUM: 6,
    IssueSeverity.LOW: 2,
    IssueSeverity.INFO: 0,
}

REPEATED_GROUP_CAPS = {
    IssueSeverity.CRITICAL: 75,
    IssueSeverity.HIGH: 28,
    IssueSeverity.MEDIUM: 12,
    IssueSeverity.LOW: 4,
    IssueSeverity.INFO: 0,
}

CATEGORY_CAPS = {
    IssueCategory.ARCHITECTURE: 65,
    IssueCategory.COUPLING: 30,
    IssueCategory.MODULARITY: 35,
    IssueCategory.MAINTAINABILITY: 18,
    IssueCategory.TESTING: 10,
    IssueCategory.DOCUMENTATION: 5,
    IssueCategory.UNKNOWN: 10,
}


def risk_score(result: ReviewResult) -> int:
    grouped: dict[tuple[str, IssueSeverity, IssueCategory], int] = {}
    for issue in result.issues:
        key = issue.rule_id or issue.id
        group = (key, issue.severity, issue.category)
        grouped[group] = grouped.get(group, 0) + 1

    category_penalties: dict[IssueCategory, int] = {}
    for (_, severity, category), count in grouped.items():
        weight = SEVERITY_WEIGHTS.get(severity, 1)
        if weight == 0:
            continue
        repeated_increment = max(1, weight // 5)
        group_penalty = weight + repeated_increment * (count - 1)
        capped = min(group_penalty, REPEATED_GROUP_CAPS.get(severity, weight * 2))
        category_penalties[category] = category_penalties.get(category, 0) + capped

    penalty = sum(
        min(value, CATEGORY_CAPS.get(category, 10))
        for category, value in category_penalties.items()
    )
    return max(0, 100 - penalty)


def risk_level(score: int) -> str:
    if score >= 85:
        return "low"
    if score >= 65:
        return "medium"
    if score >= 40:
        return "high"
    return "critical"
