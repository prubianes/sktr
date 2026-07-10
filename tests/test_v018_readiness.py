from __future__ import annotations

import json
from pathlib import Path

from jsonschema import validate
from typer.testing import CliRunner

from sktr_cli import main as cli_main
from sktr_core.config import DEFAULT_EXCLUDES, load_config
from sktr_core.model import (
    AnalysisDiagnostic,
    DiagnosticSeverity,
    FileChange,
    Issue,
    IssueCategory,
    IssueSeverity,
    ReviewContext,
    ReviewResult,
)
from sktr_core.pipeline import ReviewPipeline, filter_git_diff
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_java import JavaAnalyzer
from sktr_javascript import JavaScriptTypeScriptAnalyzer
from sktr_python import PythonAstAnalyzer
from sktr_report import MarkdownOutput, TerminalOutput, review_result_to_artifact
from sktr_report.summary import risk_score

runner = CliRunner()
ROOT = Path(__file__).parents[1]


def test_default_exclusions_filter_diff_and_record_paths() -> None:
    diff = GitDiff(
        changed_files=["src/app.py", "node_modules/pkg/index.js", "dist/app.min.js"],
        file_changes=[
            FileChange(path="src/app.py", status="modified"),
            FileChange(path="node_modules/pkg/index.js", status="modified"),
            FileChange(path="dist/app.min.js", status="added"),
        ],
        current_file_contents={
            "src/app.py": "pass\n",
            "node_modules/pkg/index.js": "export {};\n",
            "dist/app.min.js": "x=1",
        },
    )

    filtered = filter_git_diff(diff, DEFAULT_EXCLUDES)

    assert filtered.changed_files == ["src/app.py"]
    assert filtered.excluded_files == ["dist/app.min.js", "node_modules/pkg/index.js"]
    assert list(filtered.current_file_contents) == ["src/app.py"]
    assert filtered.metadata["excluded_file_count"] == "2"


def test_explicit_empty_exclusions_disable_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "sktr.yml"
    config_path.write_text("review:\n  exclude: []\n", encoding="utf-8")

    assert load_config(config_path).review.exclude == []


def test_fail_on_writes_output_before_nonzero_exit(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "sktr.yml"
    output = tmp_path / "review.md"
    config.write_text("project:\n  name: ci-test\n", encoding="utf-8")
    result = ReviewResult(
        status="ready",
        issues=[
            Issue(
                id="high",
                title="High finding",
                description="Architecture risk.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
            )
        ],
    )
    monkeypatch.setattr(cli_main, "_build_review_result", lambda **kwargs: result)

    invocation = runner.invoke(
        cli_main.app,
        [
            "review",
            "--config",
            str(config),
            "--format",
            "markdown",
            "--output",
            str(output),
            "--fail-on",
            "high",
        ],
    )

    assert invocation.exit_code == 1
    assert output.is_file()
    assert "High finding" in output.read_text(encoding="utf-8")


def test_fail_on_ignores_lower_severity_and_ai_warnings(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "sktr.yml"
    config.write_text("project:\n  name: ci-test\n", encoding="utf-8")
    result = ReviewResult(
        status="ready",
        issues=[
            Issue(
                id="low",
                title="Low finding",
                description="Minor risk.",
                severity=IssueSeverity.LOW,
            )
        ],
    )
    monkeypatch.setattr(cli_main, "_build_review_result", lambda **kwargs: result)

    invocation = runner.invoke(
        cli_main.app,
        ["review", "--config", str(config), "--fail-on", "high"],
    )

    assert invocation.exit_code == 0


def test_configured_fail_on_is_used_without_cli_override(tmp_path: Path, monkeypatch) -> None:
    config = tmp_path / "sktr.yml"
    config.write_text("review:\n  fail_on: medium\n", encoding="utf-8")
    result = ReviewResult(
        status="ready",
        issues=[
            Issue(
                id="medium",
                title="Medium finding",
                description="Review required.",
                severity=IssueSeverity.MEDIUM,
            )
        ],
    )
    monkeypatch.setattr(cli_main, "_build_review_result", lambda **kwargs: result)

    invocation = runner.invoke(cli_main.app, ["review", "--config", str(config)])

    assert invocation.exit_code == 1


def test_diagnostics_render_without_affecting_score() -> None:
    diagnostic = AnalysisDiagnostic(
        analyzer="sktr-java",
        file_path="src/Broken.java",
        severity=DiagnosticSeverity.ERROR,
        code="parse_error",
        message="Invalid method declaration.",
    )
    result = ReviewResult(status="ready", diagnostics=[diagnostic])

    assert risk_score(result) == 100
    assert "Analysis Diagnostics" in TerminalOutput().render(result)
    assert "src/Broken.java" in MarkdownOutput().render(result)


def test_artifact_validates_against_frozen_schema() -> None:
    schema = json.loads(
        (ROOT / "docs" / "schema" / "sktr-review-0.1.schema.json").read_text(encoding="utf-8")
    )
    result = ReviewResult(
        status="ready",
        context=ReviewContext(excluded_files=["dist/bundle.js"]),
        diagnostics=[
            AnalysisDiagnostic(
                analyzer="sktr-javascript-typescript",
                file_path="src/broken.ts",
                code="parse_error",
                message="Incomplete syntax.",
            )
        ],
    )

    artifact = review_result_to_artifact(result)

    validate(artifact, schema)
    assert artifact["schema_version"] == "0.1"
    assert artifact["excluded_files"] == ["dist/bundle.js"]
    assert artifact["diagnostics"][0]["code"] == "parse_error"


def test_mixed_language_pipeline_merges_all_analyzers(tmp_path: Path) -> None:
    paths = {
        "src/python_service.py": "def python_service():\n    pass\n",
        "src/web/service.ts": "export function webService() { return true; }\n",
        "src/main/java/com/sample/JavaService.java": (
            "package com.sample; public class JavaService { public void run() {} }\n"
        ),
    }
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=list(paths),
        file_changes=[FileChange(path=path, status="added") for path in paths],
        current_file_contents=paths,
    )

    result = ReviewPipeline(
        diff=diff,
        analyzers=[PythonAstAnalyzer(), JavaScriptTypeScriptAnalyzer(), JavaAnalyzer()],
    ).run()

    languages = {
        source_file.language
        for module in result.system.modules
        for source_file in module.files
    }
    assert languages == {"python", "typescript", "java"}
