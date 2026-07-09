from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sktr_core.model import ReviewResult, SourceFile
from sktr_report.summary import risk_level, risk_score


def review_result_to_artifact(result: ReviewResult) -> dict[str, Any]:
    score = risk_score(result)
    risk = risk_level(score)
    knowledge_summary = _knowledge_model_summary(result)
    rules = _rules(result)
    return {
        "schema_version": "0.1",
        "metadata": {
            "tool": "sktr",
            "generated_at": str(result.metadata.get("generated_at", "unknown")),
            "review": result.metadata,
            "context": result.context.metadata,
            "system": result.system.metadata,
        },
        "repository": _repository(result),
        "summary": {
            "score": score,
            "risk": risk,
            "changed_files": len(result.context.file_changes),
            "issues": len(result.issues),
        },
        "status": result.status,
        "changed_files": [change.model_dump(mode="json") for change in result.context.file_changes],
        "knowledge_summary": result.knowledge_summary,
        "knowledge_model_summary": knowledge_summary,
        "issues": [issue.model_dump(mode="json") for issue in result.issues],
        "rules": rules,
        "rule_results": _rule_results(result),
        "score": score,
        "risk": risk,
        "review_result": result.model_dump(mode="json"),
    }


def review_result_to_json(result: ReviewResult) -> str:
    return json.dumps(review_result_to_artifact(result), indent=2, sort_keys=True)


def write_review_artifact(result: ReviewResult, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(review_result_to_json(result) + "\n", encoding="utf-8")


def _knowledge_model_summary(result: ReviewResult) -> dict[str, int]:
    source_files = _source_files(result)
    return {
        "modules": len(result.system.modules),
        "source_files": len(source_files),
        "symbols": sum(len(source_file.symbols) for source_file in source_files),
        "dependencies": sum(len(source_file.dependencies) for source_file in source_files),
    }


def _rule_results(result: ReviewResult) -> list[dict[str, Any]]:
    grouped: dict[str, list[str]] = {}
    for issue in result.issues:
        rule_id = issue.rule_id or "unknown"
        grouped.setdefault(rule_id, []).append(issue.id)

    return [
        {
            "rule_id": rule_id,
            "issue_count": len(issue_ids),
            "issue_ids": issue_ids,
        }
        for rule_id, issue_ids in sorted(grouped.items())
    ]


def _repository(result: ReviewResult) -> dict[str, str | None]:
    root_path = result.context.metadata.get("repository_root")
    if not root_path:
        root_path = result.context.metadata.get("root_path")

    name = result.context.metadata.get("repository_name")
    if not name and isinstance(root_path, str):
        name = Path(root_path).name
    if not name:
        name = result.system.name if result.system.name != "current" else None

    return {
        "name": str(name) if name else None,
        "root_path": str(root_path) if root_path else None,
    }


def _rules(result: ReviewResult) -> list[dict[str, Any]]:
    rules_executed = result.metadata.get("rules_executed", [])
    if isinstance(rules_executed, list) and rules_executed:
        return [
            rule
            for rule in rules_executed
            if isinstance(rule, dict)
        ]

    return [
        {
            "id": rule_result["rule_id"],
            "issue_count": rule_result["issue_count"],
        }
        for rule_result in _rule_results(result)
    ]


def _source_files(result: ReviewResult) -> list[SourceFile]:
    return [source_file for module in result.system.modules for source_file in module.files]
