from __future__ import annotations

import json
from typing import Any

from sktr_core.plugins import AIReviewContext


def structured_advisor_context(context: AIReviewContext) -> dict[str, Any]:
    """Whitelist only deterministic SKTR analysis; raw diffs and source stay out."""
    return {
        "knowledge_summary": context.system.metadata.get("knowledge_summary", {}),
        "changed_files": [
            {
                "path": change.path,
                "status": change.status,
                "added_lines": change.added_lines,
                "removed_lines": change.removed_lines,
            }
            for change in context.review.file_changes
        ],
        "issues": [
            {
                "id": issue.id,
                "title": issue.title,
                "description": issue.description,
                "severity": issue.severity.value,
                "category": issue.category.value,
                "rule_id": issue.rule_id,
                "location": issue.location.model_dump(mode="json") if issue.location else None,
                "metadata": issue.metadata,
            }
            for issue in context.issues
        ],
        "modules": [
            {
                "name": module.name,
                "metrics": module.metadata.get("metrics", {}),
            }
            for module in context.system.modules
        ],
        "dependencies": [
            {
                "source": dependency.source,
                "target": dependency.target,
                "kind": dependency.kind.value,
                "metrics": dependency.metadata.get("metrics", {}),
            }
            for module in context.system.modules
            for source_file in module.files
            for dependency in source_file.dependencies
        ],
        "existing_ai_summary": context.ai_summary.summary if context.ai_summary else None,
    }


def build_advisor_prompt(context: AIReviewContext) -> str:
    payload = json.dumps(structured_advisor_context(context), sort_keys=True)
    return f"""You are SKTR's AI Advisor.

You are given structured analysis produced by SKTR.
You are not reviewing raw source code.
You must not invent files, modules, dependencies or issues.
You must only recommend actions based on the provided issues, metrics and signals.
If there is not enough context for a specific recommendation, say so.
Prioritize practical engineering actions.
Keep recommendations concise and actionable.

Return JSON only, matching this shape:
{{"items":[{{"title":"...","why":"...","suggested_action":"...","related_issue_ids":[],"related_files":[],"confidence":"medium"}}]}}

Structured SKTR context:
{payload}"""
