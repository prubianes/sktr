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
            {"name": module.name, "metrics": module.metadata.get("metrics", {})}
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
    }
