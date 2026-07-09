from __future__ import annotations

import json
from pathlib import Path

from sktr_core.model import FileChange, ReviewContext, ReviewResult
from sktr_report import JsonOutput, MarkdownOutput, TerminalOutput, output_for_format


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


def test_json_output_writes_to_stdout(capsys) -> None:
    JsonOutput().write(_review_result())

    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "foundation ready"
    assert payload["changed_files"][0]["path"] == "src/orders/service.py"


def test_markdown_output_writes_to_stdout(capsys) -> None:
    MarkdownOutput().write(_review_result())

    output = capsys.readouterr().out
    assert "# SKTR Review" in output
    assert "- M `src/orders/service.py`" in output


def test_terminal_output_writes_to_stdout(capsys) -> None:
    TerminalOutput().write(_review_result())

    output = capsys.readouterr().out
    assert "SKTR Review" in output
    assert "M src/orders/service.py" in output


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


def _review_result() -> ReviewResult:
    return ReviewResult(
        status="foundation ready",
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
