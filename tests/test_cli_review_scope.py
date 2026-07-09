from __future__ import annotations

import typer
from typer.testing import CliRunner

from sktr_cli.main import app
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
    result = runner.invoke(app, ["review", "--commit", "HEAD~1", "--branch"])

    assert result.exit_code != 0
    assert "--commit cannot be combined" in result.output


def test_cli_rejects_commit_with_base() -> None:
    result = runner.invoke(app, ["review", "--commit", "HEAD~1", "--base", "main"])

    assert result.exit_code != 0
    assert "--commit cannot be combined" in result.output
