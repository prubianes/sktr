from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from sktr_cli.main import app
from sktr_core.model import (
    AIRecommendation,
    AIReview,
    FileChange,
    Issue,
    IssueCategory,
    IssueSeverity,
    ReviewContext,
    ReviewResult,
)
from sktr_core.pipeline import ReviewPipeline
from sktr_core.plugins import GitDiff
from sktr_report import JsonOutput, MarkdownOutput, TerminalOutput, output_for_format, review_result_to_json

runner = CliRunner()


def test_output_selection_returns_requested_output() -> None:
    assert isinstance(output_for_format("terminal"), TerminalOutput)
    assert isinstance(output_for_format("json"), JsonOutput)
    assert isinstance(output_for_format("markdown"), MarkdownOutput)


def test_output_selection_rejects_unknown_format() -> None:
    try:
        output_for_format("xml")
    except ValueError as error:
        assert "Unsupported output format" in str(error)
    else:
        raise AssertionError("Expected unsupported output format to fail")


def test_outputs_show_review_breadth_when_enrichment_provides_it() -> None:
    result = ReviewResult(
        status="review complete",
        knowledge_summary={"production_changed_files": 10, "changed_modules": 6},
    )

    assert "Review breadth: 10 production files across 6 modules" in TerminalOutput().render(result)
    assert "Review breadth: 10 production files across 6 modules" in MarkdownOutput().render(result)


def test_ai_linked_recommendation_suppresses_duplicate_deterministic_suggestion() -> None:
    issue = Issue(
        id="symbol.large_function:graph",
        title="Large function detected",
        description="graph is too large.",
        severity=IssueSeverity.MEDIUM,
        category=IssueCategory.MAINTAINABILITY,
        metadata={
            "rule_key": "large_function",
            "suggestion": "Consider extracting validation and orchestration into smaller functions.",
        },
    )
    result = ReviewResult(
        status="review complete",
        issues=[issue],
        ai_review=AIReview(
            provider="openai",
            recommendations=[
                AIRecommendation(
                    title="Split graph into focused helpers",
                    why="The command has multiple responsibilities.",
                    suggested_action="Extract validation and orchestration into private helpers.",
                    related_issue_ids=[issue.id],
                )
            ],
        ),
    )

    terminal = TerminalOutput().render(result)
    markdown = MarkdownOutput().render(result)

    assert "[bold]Prioritized Actions[/bold]" in terminal
    assert "[bold]Suggested Actions[/bold]" not in terminal
    assert "### Prioritized Actions" in markdown
    assert "## Suggested Actions" not in markdown


def test_json_output_writes_to_stdout(capsys) -> None:
    JsonOutput().write(_review_result())

    payload = json.loads(capsys.readouterr().out)
    assert payload["summary"]["risk"] == "low"
    assert payload["changed_files"][0]["path"] == "src/orders/service.py"


def test_markdown_output_writes_to_stdout(capsys) -> None:
    MarkdownOutput().write(_review_result())

    output = capsys.readouterr().out
    assert "# SKTR Review" in output
    assert "| M | src/orders/service.py |" in output


def test_terminal_output_writes_to_stdout(capsys) -> None:
    TerminalOutput().write(_review_result())

    output = capsys.readouterr().out
    assert "SKTR Review" in output
    assert "M src/orders/service.py" in output


def test_terminal_output_preserves_bracketed_route_segments(capsys) -> None:
    result = ReviewResult(
        status="review complete",
        context=ReviewContext(
            file_changes=[FileChange(path="app/[rooms]/roomPageClient.tsx", status="modified")]
        ),
    )

    TerminalOutput().write(result)

    assert "app/[rooms]/roomPageClient.tsx" in capsys.readouterr().out


def test_pipeline_timestamp_is_shared_by_all_outputs(monkeypatch) -> None:
    generated_at = "2026-07-13T12:34:56Z"
    monkeypatch.setattr("sktr_core.pipeline.review._generated_at", lambda: generated_at)
    result = ReviewPipeline(diff=GitDiff()).run()

    assert result.metadata["generated_at"] == generated_at
    assert f"Generated at: {generated_at}" in TerminalOutput().render(result)
    assert f"Generated at: {generated_at}" in MarkdownOutput().render(result)
    assert json.loads(review_result_to_json(result))["metadata"]["generated_at"] == generated_at


def test_json_output_writes_to_file(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "sktr-review.json"

    JsonOutput().write(_review_result(), str(output_path))

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert payload["knowledge_model_summary"]["modules"] == 0
    assert payload["changed_files"][0]["status"] == "modified"


def test_markdown_output_writes_to_file(tmp_path: Path) -> None:
    output_path = tmp_path / "reports" / "REVIEW.md"

    MarkdownOutput().write(_review_result(), str(output_path))

    assert output_path.read_text(encoding="utf-8").startswith("# SKTR Review\n")


def test_markdown_output_snapshot() -> None:
    assert MarkdownOutput().render(_rich_review_result()) == "\n".join(
        [
            "# SKTR Review",
            "",
            "## Summary",
            "Risk: Medium  ",
            "Score: 76/100  ",
            "Changed files: 2  ",
            "Excluded files: 0  ",
            "Issues: 2",
            "",
            "## Changed Files",
            "| Status | File |",
            "|---|---|",
            "| M | controllers/order_controller.py |",
            "| A | services/order_service.py |",
            "",
            "## Findings",
            "### High",
            "- **Forbidden dependency**",
            "  `controllers/order_controller.py` imports `repositories/order_repository.py`.",
            "  Reason: Controllers should access repositories through services.",
            "### Medium",
            "- **Large function**",
            "  `create_order` has 114 lines.",
            "",
            "## Findings by Category",
            "| Category | Issues | Highest severity | Affected files | Rules |",
            "|---|---:|---|---|---|",
            "| Architecture | 1 | High | `controllers/order_controller.py` | architecture.forbidden_dependency |",
            "| Maintainability | 1 | Medium | - | symbol.large_function |",
            "",
            "## Suggested Actions",
            "- Consider extracting validation, payment handling and persistence.",
            "- Route the dependency through the configured boundary instead of importing it directly.",
            "",
            "## Metadata",
            "Generated by SKTR.",
            "Status: review complete",
            "Review scope: working_tree",
            "Repository root: /repo",
        ]
    )


def test_human_outputs_share_sections_and_group_repeated_findings() -> None:
    dependencies = [
        Issue(
            id=f"dependency.new:src/service.py:target_{index}",
            title="New dependency detected",
            description=f"src/service.py imports target_{index}.",
            severity=IssueSeverity.INFO,
            category=IssueCategory.COUPLING,
            rule_id="dependency.new",
            metadata={
                "rule_key": "new_dependency",
                "rule_name": "New dependency detected",
                "source": "src/service.py",
                "target": f"target_{index}",
            },
        )
        for index in range(5)
    ]
    result = ReviewResult(
        status="review complete",
        context=ReviewContext(
            file_changes=[FileChange(path="src/service.py", status="modified")],
            metadata={"review_scope": "working_tree", "repository_root": "/repo"},
        ),
        issues=dependencies,
        messages=["No AI provider configured yet."],
    )

    terminal = TerminalOutput().render(result)
    markdown = MarkdownOutput().render(result)

    for terminal_section, markdown_section in [
        ("[bold]Summary[/bold]", "## Summary"),
        ("[bold]Changed Files[/bold]", "## Changed Files"),
        ("[bold]Findings[/bold]", "## Findings"),
        ("[bold]Findings by Category[/bold]", "## Findings by Category"),
        ("[bold]Notes[/bold]", "## Notes"),
        ("[bold]Metadata[/bold]", "## Metadata"),
    ]:
        assert terminal_section in terminal
        assert markdown_section in markdown

    assert "New dependency detected (5 occurrences)" in terminal
    assert "**New dependency detected** (5 occurrences)" in markdown
    assert terminal.count("New dependency detected") == 1
    assert markdown.count("New dependency detected") == 2  # finding plus rule name in category summary


def test_report_command_renders_same_artifact_without_rerunning_ai(tmp_path: Path, monkeypatch) -> None:
    result = ReviewResult(
        status="review complete",
        ai_review=AIReview(
            provider="openai",
            overview="Stable summary.",
            recommendations=[
                AIRecommendation(
                    title="Stable advice",
                    why="The artifact is reused.",
                    suggested_action="Render it in each required format.",
                )
            ],
        ),
    )
    artifact = tmp_path / "review.json"
    JsonOutput().write(result, str(artifact))
    (tmp_path / "sktr.yml").write_text("project:\n  name: test\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)

    terminal = runner.invoke(app, ["report", str(artifact), "--format", "terminal"])
    markdown = runner.invoke(app, ["report", str(artifact), "--format", "markdown"])

    assert terminal.exit_code == 0
    assert markdown.exit_code == 0
    assert "Stable summary." in terminal.output
    assert "Stable summary." in markdown.output
    assert "Stable advice" in terminal.output
    assert "Stable advice" in markdown.output


def _review_result() -> ReviewResult:
    return ReviewResult(
        status="review complete",
        context=ReviewContext(
            changed_files=["src/orders/service.py"],
            file_changes=[
                FileChange(
                    path="src/orders/service.py",
                    status="modified",
                    added_lines=7,
                    removed_lines=2,
                )
            ],
        ),
        messages=["No AI provider configured yet."],
    )


def _rich_review_result() -> ReviewResult:
    return ReviewResult(
        status="review complete",
        context=ReviewContext(
            changed_files=[
                "controllers/order_controller.py",
                "services/order_service.py",
            ],
            file_changes=[
                FileChange(path="controllers/order_controller.py", status="modified"),
                FileChange(path="services/order_service.py", status="added"),
            ],
            metadata={
                "review_scope": "working_tree",
                "repository_root": "/repo",
            },
        ),
        issues=[
            Issue(
                id="architecture.forbidden_dependency:controllers/order_controller.py",
                title="Forbidden dependency",
                description="controllers/order_controller.py imports repositories/order_repository.py.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
                rule_id="architecture.forbidden_dependency",
                metadata={
                    "rule_key": "forbidden_dependency",
                    "source": "controllers/order_controller.py",
                    "target": "repositories/order_repository.py",
                    "reason": "Controllers should access repositories through services.",
                },
            ),
            Issue(
                id="symbol.large_function:services/order_service.py:create_order",
                title="Large function",
                description="create_order is too large.",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.MAINTAINABILITY,
                rule_id="symbol.large_function",
                metadata={
                    "rule_key": "large_function",
                    "symbol": "create_order",
                    "line_count": "114",
                    "suggestion": "Consider extracting validation, payment handling and persistence.",
                },
            ),
        ],
    )
