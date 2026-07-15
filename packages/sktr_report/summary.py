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

    issue_penalty = sum(
        min(value, CATEGORY_CAPS.get(category, 10))
        for category, value in category_penalties.items()
    )
    return max(0, 100 - issue_penalty - breadth_penalty(result))


def review_breadth(result: ReviewResult) -> dict[str, int]:
    summary = result.knowledge_summary
    if not summary:
        value = result.system.metadata.get("knowledge_summary", {})
        summary = value if isinstance(value, dict) else {}
    return {
        "changed_files": len(result.context.file_changes),
        "production_files": int(summary.get("production_changed_files", 0)),
        "test_files": int(summary.get("test_changed_files", 0)),
        "documentation_files": int(summary.get("documentation_changed_files", 0)),
        "modules": int(summary.get("changed_modules", 0)),
        "public_api_changes": int(summary.get("public_api_changes", 0)),
    }


def breadth_penalty(result: ReviewResult) -> int:
    system_summary = result.system.metadata.get("knowledge_summary", {})
    if not result.knowledge_summary and not isinstance(system_summary, dict):
        return 0
    if not result.knowledge_summary and not system_summary:
        return 0
    breadth = review_breadth(result)
    production_files = breadth["production_files"]
    modules = breadth["modules"]
    total_files = breadth["changed_files"]
    public_api_changes = breadth["public_api_changes"]

    production_penalty = 8 if production_files >= 20 else 5 if production_files >= 10 else 2 if production_files >= 5 else 0
    module_penalty = 6 if modules >= 10 else 3 if modules >= 5 else 0
    total_penalty = 3 if total_files >= 30 else 1 if total_files >= 15 else 0
    api_penalty = 2 if public_api_changes >= 5 else 1 if public_api_changes > 0 else 0
    return min(16, production_penalty + module_penalty + total_penalty + api_penalty)


def risk_level(score: int) -> str:
    if score >= 85:
        return "low"
    if score >= 65:
        return "medium"
    if score >= 40:
        return "high"
    return "critical"
