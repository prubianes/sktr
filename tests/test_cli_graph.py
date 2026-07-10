from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from sktr_cli import main as cli_main
from sktr_core.model import Dependency, DependencyKind, Module, ReviewResult, SourceFile, System

runner = CliRunner()


def test_graph_command_writes_mermaid_to_stdout(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)

    with _isolated(Path.cwd() / ".tmp-graph-test-1"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(cli_main.app, ["graph"])

    assert result.exit_code == 0
    assert "graph TD" in result.output
    assert "orders --> payments" in result.output


def test_graph_command_writes_mermaid_to_file(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)
    output_path = tmp_path / "architecture.mmd"

    with _isolated(Path.cwd() / ".tmp-graph-test-2"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(cli_main.app, ["graph", "--output", str(output_path)])

    assert result.exit_code == 0
    assert result.output == ""
    assert "orders --> payments" in output_path.read_text(encoding="utf-8")


def test_graph_command_requires_config() -> None:
    with _isolated(Path.cwd() / ".tmp-graph-test-3"):
        result = runner.invoke(cli_main.app, ["graph"])

        assert result.exit_code == 1
        assert "No SKTR config found" in result.output


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


def _config() -> str:
    return "project:\n  name: test\n  default_base: main\n"


class _isolated:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.previous = Path.cwd()

    def __enter__(self):
        import os
        import shutil

        if self.path.exists():
            shutil.rmtree(self.path)
        self.path.mkdir()
        os.chdir(self.path)

    def __exit__(self, exc_type, exc, tb):
        import os
        import shutil

        os.chdir(self.previous)
        shutil.rmtree(self.path)
