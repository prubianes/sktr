from __future__ import annotations

from pathlib import Path

import typer

from sktr_core.config import load_config
from sktr_core.pipeline import ReviewPipeline
from sktr_git import ReviewScope, SubprocessGitProvider
from sktr_python import PythonAstAnalyzer
from sktr_report import output_for_format
from sktr_rules import RuleRegistry, rules_from_config

app = typer.Typer(help="System Knowledge & Technical Review.")


@app.callback()
def main() -> None:
    """System Knowledge & Technical Review."""


@app.command()
def review(
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write output to a file instead of stdout.",
    ),
    output_format: str = typer.Option(
        "terminal",
        "--format",
        help="Output format: terminal, json, or markdown.",
    ),
    branch: bool = typer.Option(
        False,
        "--branch",
        help="Review the current branch against its merge-base with the base branch.",
    ),
    base: str | None = typer.Option(
        None,
        "--base",
        help="Base branch for branch review. Defaults to config or main.",
    ),
    commit: str | None = typer.Option(
        None,
        "--commit",
        help="Review a commit against its parent.",
    ),
) -> None:
    """Analyze the current Git diff and produce an architecture-focused review."""
    config = load_config()
    scope = _review_scope(branch=branch, base=base, commit=commit)
    base_branch = base or config.git.default_base_branch
    rule_registry = RuleRegistry(rules_from_config(config.rules))
    git_diff = SubprocessGitProvider(
        scope=scope,
        base_branch=base_branch,
        commit=commit,
    ).current_diff()
    pipeline = ReviewPipeline(
        diff=git_diff,
        analyzers=[PythonAstAnalyzer()],
        rules=rule_registry.all(),
    )
    result = pipeline.run()
    try:
        selected_output = output_for_format(output_format)
    except ValueError as error:
        raise typer.BadParameter(str(error), param_hint="--format") from error
    selected_output.write(result, str(output) if output is not None else None)


def _review_scope(*, branch: bool, base: str | None, commit: str | None) -> ReviewScope:
    if commit is not None and (branch or base is not None):
        raise typer.BadParameter("--commit cannot be combined with --branch or --base")
    if commit is not None:
        return ReviewScope.COMMIT
    if branch or base is not None:
        return ReviewScope.BRANCH
    return ReviewScope.WORKING_TREE
