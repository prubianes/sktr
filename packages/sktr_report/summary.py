from __future__ import annotations

from sktr_core.model import IssueSeverity, ReviewResult

SEVERITY_WEIGHTS = {
    IssueSeverity.CRITICAL: 40,
    IssueSeverity.HIGH: 24,
    IssueSeverity.MEDIUM: 12,
    IssueSeverity.LOW: 5,
    IssueSeverity.INFO: 1,
}

REPEATED_GROUP_CAPS = {
    IssueSeverity.CRITICAL: 60,
    IssueSeverity.HIGH: 40,
    IssueSeverity.MEDIUM: 24,
    IssueSeverity.LOW: 10,
    IssueSeverity.INFO: 5,
}


def risk_score(result: ReviewResult) -> int:
    grouped: dict[tuple[str, IssueSeverity], int] = {}
    for issue in result.issues:
        key = issue.rule_id or issue.id
        grouped[(key, issue.severity)] = grouped.get((key, issue.severity), 0) + 1

    penalty = 0
    for (_, severity), count in grouped.items():
        weight = SEVERITY_WEIGHTS.get(severity, 1)
        repeated_increment = max(1, weight // 4)
        group_penalty = weight + repeated_increment * (count - 1)
        penalty += min(group_penalty, REPEATED_GROUP_CAPS.get(severity, weight * 2))
    changed_file_penalty = min(len(result.context.file_changes), 10)
    return max(0, 100 - penalty - changed_file_penalty)


def risk_level(score: int) -> str:
    if score >= 85:
        return "low"
    if score >= 65:
        return "medium"
    if score >= 40:
        return "high"
    return "critical"
