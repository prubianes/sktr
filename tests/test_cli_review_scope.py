from __future__ import annotations

import typer
from typer.testing import CliRunner
from pathlib import Path

from sktr_cli.main import app
from sktr_cli.main import _progress
from sktr_cli.main import _review_scope
from sktr_git import ReviewScope

runner = CliRunner()


def test_default_cli_scope_is_working_tree() -> None:
    assert _review_scope(branch=False, base=None, commit=None) == ReviewScope.WORKING_TREE


def test_branch_flag_selects_branch_scope() -> None:
    assert _review_scope(branch=True, base=None, commit=None) == ReviewScope.BRANCH


def test_explicit_base_selects_branch_scope() -> None:
    assert _review_scope(branch=False, base="develop", commit=None) == ReviewScope.BRANCH


def test_commit_selects_commit_scope() -> None:
    assert _review_scope(branch=False, base=None, commit="HEAD~1") == ReviewScope.COMMIT


def test_commit_and_branch_are_invalid_combination() -> None:
    try:
        _review_scope(branch=True, base=None, commit="HEAD~1")
    except typer.BadParameter as error:
        assert "--commit cannot be combined" in str(error)
    else:
        raise AssertionError("Expected commit plus branch to be invalid")


def test_commit_and_base_are_invalid_combination() -> None:
    try:
        _review_scope(branch=False, base="main", commit="HEAD~1")
    except typer.BadParameter as error:
        assert "--commit cannot be combined" in str(error)
    else:
        raise AssertionError("Expected commit plus base to be invalid")


def test_cli_rejects_commit_with_branch() -> None:
    with _isolated(Path.cwd() / ".tmp-review-scope-test-1"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(app, ["review", "--commit", "HEAD~1", "--branch"])

    assert result.exit_code != 0
    assert "--commit cannot be combined" in result.output


def test_cli_rejects_commit_with_base() -> None:
    with _isolated(Path.cwd() / ".tmp-review-scope-test-2"):
        Path("sktr.yml").write_text(_config(), encoding="utf-8")
        result = runner.invoke(app, ["review", "--commit", "HEAD~1", "--base", "main"])

    assert result.exit_code != 0
    assert "--commit cannot be combined" in result.output


def test_review_command_requires_config() -> None:
    with _isolated(Path.cwd() / ".tmp-review-scope-test-3"):
        result = runner.invoke(app, ["review"])

        assert result.exit_code == 1
        assert "SKTR is not initialized" in result.output


def test_progress_uses_spinner_only_for_interactive_terminal() -> None:
    interactive = _FakeConsole(is_terminal=True)
    non_interactive = _FakeConsole(is_terminal=False)

    with _progress("Analyzing...", console=interactive):
        pass
    with _progress("Analyzing...", console=non_interactive):
        pass

    assert interactive.messages == [("[cyan]Analyzing...[/cyan]", "dots")]
    assert non_interactive.messages == []


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


class _FakeConsole:
    def __init__(self, *, is_terminal: bool) -> None:
        self.is_terminal = is_terminal
        self.messages: list[tuple[str, str]] = []

    def status(self, message: str, *, spinner: str):
        from contextlib import nullcontext

        self.messages.append((message, spinner))
        return nullcontext()
