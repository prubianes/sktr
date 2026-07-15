from __future__ import annotations

import json
from typing import Any

from sktr_core.plugins import AIReviewContext


def build_ai_review_prompt(context: AIReviewContext) -> str:
    payload = json.dumps(structured_review_context(context), sort_keys=True)
    return f"""You are SKTR's AI Review assistant.

Explain and prioritize deterministic SKTR findings. Do not invent files, modules,
dependencies, issues, or source behavior. Recommend only actions supported by the
provided structured context. Keep the overview concise and actions practical.

Return JSON only with this shape:
{{"overview":"...","recommendations":[{{"title":"...","why":"...","suggested_action":"...","related_issue_ids":[],"related_files":[],"confidence":"medium"}}]}}

Structured SKTR context:
{payload}"""


def structured_review_context(context: AIReviewContext) -> dict[str, Any]:
    """Whitelist deterministic SKTR data and exclude raw diffs and source contents."""
    issue_groups = _issue_groups(context)
    dependency_edges = _dependency_edges(context)
    return {
        "knowledge_summary": context.system.metadata.get("knowledge_summary", {}),
        "changed_files": [
            {
                "path": change.path,
                "status": change.status,
                "added_lines": change.added_lines,
                "removed_lines": change.removed_lines,
            }
            for change in sorted(context.review.file_changes, key=lambda item: item.path)[:100]
        ],
        "issue_groups": issue_groups,
        "priority_issues": [_issue_payload(issue) for issue in _priority_issues(context)],
        "modules": [
            {"name": module.name, "metrics": module.metadata.get("metrics", {})}
            for module in context.system.modules
        ],
        "dependency_edges": dependency_edges,
        "analysis_diagnostics": [
            {
                "analyzer": diagnostic.analyzer,
                "file_path": diagnostic.file_path,
                "severity": diagnostic.severity.value,
                "code": diagnostic.code,
                "message": diagnostic.message,
            }
            for diagnostic in context.system.diagnostics[:20]
        ],
        "context_limits": {
            "changed_files_total": len(context.review.file_changes),
            "changed_files_included": min(len(context.review.file_changes), 100),
            "issues_total": len(context.issues),
            "priority_issues_included": len(_priority_issues(context)),
        },
    }


def _issue_groups(context: AIReviewContext) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for issue in context.issues:
        key = (issue.rule_id or issue.title, issue.title, issue.severity.value, issue.category.value)
        group = groups.setdefault(
            key,
            {
                "rule_id": issue.rule_id,
                "title": issue.title,
                "severity": issue.severity.value,
                "category": issue.category.value,
                "count": 0,
                "sample_issue_ids": [],
                "affected_files": [],
            },
        )
        group["count"] += 1
        if len(group["sample_issue_ids"]) < 3:
            group["sample_issue_ids"].append(issue.id)
        path = str(issue.metadata.get("path", ""))
        if path and path not in group["affected_files"] and len(group["affected_files"]) < 5:
            group["affected_files"].append(path)
        for listed_path in str(issue.metadata.get("paths", "")).split(","):
            if (
                listed_path
                and listed_path not in group["affected_files"]
                and len(group["affected_files"]) < 5
            ):
                group["affected_files"].append(listed_path)
    return [groups[key] for key in sorted(groups)]


def _priority_issues(context: AIReviewContext) -> list[Any]:
    order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    issues = sorted(context.issues, key=lambda issue: (order[issue.severity.value], issue.id))
    actionable = [issue for issue in issues if issue.severity.value != "info"]
    return actionable[:20]


def _issue_payload(issue: Any) -> dict[str, Any]:
    return {
        "id": issue.id,
        "title": issue.title,
        "description": issue.description,
        "severity": issue.severity.value,
        "category": issue.category.value,
        "rule_id": issue.rule_id,
        "location": issue.location.model_dump(mode="json") if issue.location else None,
        "metadata": issue.metadata,
    }


def _dependency_edges(context: AIReviewContext) -> list[dict[str, Any]]:
    edges: dict[tuple[str, str], dict[str, int]] = {}
    for module in context.system.modules:
        for source_file in module.files:
            for dependency in source_file.dependencies:
                metrics = dependency.metadata.get("metrics", {})
                if not isinstance(metrics, dict) or not metrics.get("cross_module_dependency"):
                    continue
                source = str(metrics.get("source_module", ""))
                target = str(metrics.get("target_module", ""))
                if source and target:
                    edge = edges.setdefault((source, target), {"total": 0, "new": 0})
                    edge["total"] += 1
                    edge["new"] += int(bool(metrics.get("new_dependency")))
    return [
        {
            "source_module": source,
            "target_module": target,
            "dependency_count": counts["total"],
            "new_dependency_count": counts["new"],
        }
        for (source, target), counts in sorted(edges.items())[:50]
    ]
