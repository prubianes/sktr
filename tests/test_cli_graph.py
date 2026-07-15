from __future__ import annotations

import re
from pathlib import Path

from typer.testing import CliRunner

from sktr_cli import main as cli_main
from sktr_core.model import Dependency, DependencyKind, Module, ReviewResult, SourceFile, System

runner = CliRunner()
ANSI_ESCAPE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


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


def test_graph_repository_scope_uses_repository_model_and_change_highlighting(monkeypatch) -> None:
    calls: list[str] = []

    def repository_result(**kwargs) -> ReviewResult:
        calls.append("repository")
        return _fake_review_result()

    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)
    monkeypatch.setattr(cli_main, "_build_repository_result", repository_result)
    with _isolated(Path.cwd() / ".tmp-graph-test-4"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(cli_main.app, ["graph", "--scope", "repository"])

    assert result.exit_code == 0
    assert calls == ["repository"]
    assert "orders --> payments" in result.output


def test_graph_supports_review_scopes(monkeypatch) -> None:
    calls: list[dict] = []

    def build(**kwargs) -> ReviewResult:
        calls.append(kwargs)
        return _fake_review_result()

    monkeypatch.setattr(cli_main, "_build_review_result", build)
    with _isolated(Path.cwd() / ".tmp-graph-test-5"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        branch = runner.invoke(cli_main.app, ["graph", "--branch", "--base", "develop"])
        commit = runner.invoke(cli_main.app, ["graph", "--commit", "HEAD~1"])

    assert branch.exit_code == 0
    assert calls[0]["scope"].value == "branch"
    assert calls[0]["base_branch"] == "develop"
    assert commit.exit_code == 0
    assert calls[1]["scope"].value == "commit"
    assert calls[1]["commit"] == "HEAD~1"


def test_graph_rejects_conflicting_review_and_query_options(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)
    with _isolated(Path.cwd() / ".tmp-graph-test-6"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        review_conflict = runner.invoke(cli_main.app, ["graph", "--commit", "HEAD", "--branch"])
        query_conflict = runner.invoke(cli_main.app, ["graph", "--focus", "orders", "--cycles"])

    assert review_conflict.exit_code != 0
    assert "--commit cannot be combined" in _plain(review_conflict.output)
    assert query_conflict.exit_code != 0
    assert "Use only one of" in _plain(query_conflict.output)


def test_graph_focused_views(monkeypatch) -> None:
    monkeypatch.setattr(cli_main, "_build_review_result", _fake_review_result)
    with _isolated(Path.cwd() / ".tmp-graph-test-7"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(cli_main.app, ["graph", "--dependencies-of", "orders"])

    assert result.exit_code == 0
    assert "orders --> payments" in result.output


def _fake_review_result(**kwargs) -> ReviewResult:
    return ReviewResult(
        status="review complete",
        context={"changed_files": ["orders/service.py"]},
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


def _plain(output: str) -> str:
    return ANSI_ESCAPE.sub("", output)


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
