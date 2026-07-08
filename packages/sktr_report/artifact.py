from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sktr_core.model import ReviewResult, SourceFile


def review_result_to_artifact(result: ReviewResult) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "status": result.status,
        "changed_files": [change.model_dump(mode="json") for change in result.context.file_changes],
        "knowledge_model_summary": _knowledge_model_summary(result),
        "issues": [issue.model_dump(mode="json") for issue in result.issues],
        "rule_results": _rule_results(result),
        "metadata": {
            "review": result.metadata,
            "context": result.context.metadata,
            "system": result.system.metadata,
        },
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


def _source_files(result: ReviewResult) -> list[SourceFile]:
    return [source_file for module in result.system.modules for source_file in module.files]
