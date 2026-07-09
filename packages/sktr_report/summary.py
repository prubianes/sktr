from __future__ import annotations

from sktr_core.model import IssueSeverity, ReviewResult

SEVERITY_WEIGHTS = {
    IssueSeverity.CRITICAL: 40,
    IssueSeverity.HIGH: 24,
    IssueSeverity.MEDIUM: 12,
    IssueSeverity.LOW: 5,
    IssueSeverity.INFO: 1,
}


def risk_score(result: ReviewResult) -> int:
    penalty = sum(SEVERITY_WEIGHTS.get(issue.severity, 1) for issue in result.issues)
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
