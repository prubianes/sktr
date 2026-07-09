from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_cli import main as cli_main
from sktr_core.model import Dependency, DependencyKind, Module, ReviewResult, SourceFile, System

runner = CliRunner()


def test_graph_command_writes_mermaid_to_stdout(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)

    result = runner.invoke(cli_main.app, ["graph"])

    assert result.exit_code == 0
    assert "graph TD" in result.output
    assert "orders --> payments" in result.output


def test_graph_command_writes_mermaid_to_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)
    output_path = tmp_path / "architecture.mmd"

    result = runner.invoke(cli_main.app, ["graph", "--output", str(output_path)])

    assert result.exit_code == 0
    assert result.output == ""
    assert "orders --> payments" in output_path.read_text(encoding="utf-8")


def _fake_review_result(**kwargs) -> ReviewResult:
    return ReviewResult(
        status="foundation ready",
        system=System(
            modules=[
                Module(
                    name="python",
                    files=[
                        SourceFile(
                            path="orders/service.py",
                            dependencies=[
                                Dependency(
                                    source="orders/service.py",
                                    target="payments.client",
                                    kind=DependencyKind.IMPORT,
                                )
                            ],
                        ),
                        SourceFile(path="payments/client.py"),
                    ],
                )
            ]
        ),
    )
