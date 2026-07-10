from __future__ import annotations

import json
from pathlib import Path

from sktr_core.model import (
    Dependency,
    DependencyKind,
    FileChange,
    Issue,
    IssueCategory,
    IssueSeverity,
    Location,
    Module,
    ReviewContext,
    ReviewResult,
    SourceFile,
    Symbol,
    SymbolKind,
    System,
)
from sktr_report import review_result_to_artifact, review_result_to_json, write_review_artifact


def test_review_result_serializes_to_json_artifact() -> None:
    result = _review_result()

    artifact = json.loads(review_result_to_json(result))

    assert artifact["schema_version"] == "0.1"
    assert artifact["metadata"]["tool"] == "sktr"
    assert artifact["metadata"]["generated_at"] == "unknown"
    assert artifact["repository"] == {"name": None, "root_path": None}
    assert artifact["summary"] == {
        "score": 82,
        "risk": "medium",
        "changed_files": 1,
        "issues": 1,
    }
    assert artifact["changed_files"] == [
        {
            "path": "controllers/order_controller.py",
            "status": "modified",
            "added_lines": 12,
            "removed_lines": 3,
            "old_path": None,
        }
    ]
    assert artifact["knowledge_model_summary"] == {
        "modules": 1,
        "source_files": 1,
        "symbols": 1,
        "dependencies": 1,
    }
    assert artifact["issues"][0]["severity"] == "high"
    assert artifact["issues"][0]["category"] == "architecture"
    assert artifact["rule_results"] == [
        {
            "rule_id": "architecture.forbidden_dependency",
            "issue_count": 1,
            "issue_ids": ["architecture.forbidden_dependency:controllers/order_controller.py"],
        }
    ]
    assert artifact["rules"] == [
        {
            "id": "architecture.forbidden_dependency",
            "issue_count": 1,
        }
    ]
    assert artifact["score"] == 82
    assert artifact["risk"] == "medium"
    assert artifact["metadata"]["review"] == {"run_id": "test-run"}
    assert artifact["review_result"]["status"] == "foundation ready"


def test_write_review_artifact_writes_json_file(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "sktr-review.json"

    write_review_artifact(_review_result(), output_path)

    artifact = json.loads(output_path.read_text(encoding="utf-8"))
    assert artifact == review_result_to_artifact(_review_result())


def _review_result() -> ReviewResult:
    path = "controllers/order_controller.py"
    return ReviewResult(
        status="foundation ready",
        context=ReviewContext(
            changed_files=[path],
            file_changes=[
                FileChange(
                    path=path,
                    status="modified",
                    added_lines=12,
                    removed_lines=3,
                )
            ],
        ),
        system=System(
            modules=[
                Module(
                    name="python",
                    files=[
                        SourceFile(
                            path=path,
                            language="python",
                            symbols=[
                                Symbol(
                                    name="OrderController",
                                    kind=SymbolKind.CLASS,
                                    location=Location(file_path=path, start_line=3, end_line=8),
                                )
                            ],
                            dependencies=[
                                Dependency(
                                    source=path,
                                    target="repositories.order_repository",
                                    kind=DependencyKind.IMPORT,
                                    location=Location(file_path=path, start_line=1),
                                )
                            ],
                        )
                    ],
                )
            ],
            metadata={"analyzer": "PythonAstAnalyzer"},
        ),
        issues=[
            Issue(
                id="architecture.forbidden_dependency:controllers/order_controller.py",
                title="Forbidden dependency",
                description="controllers/order_controller.py imports repositories/order_repository.py directly.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
                rule_id="architecture.forbidden_dependency",
            )
        ],
        metadata={"run_id": "test-run"},
    )
