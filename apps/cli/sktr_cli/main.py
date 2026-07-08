from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from sktr_core.config import load_config
from sktr_core.pipeline import ReviewPipeline
from sktr_git import SubprocessGitProvider
from sktr_python import PythonAstAnalyzer
from sktr_report import TerminalReporter, write_review_artifact
from sktr_rules import RuleRegistry, default_rules

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
        help="Write the structured review artifact to a JSON file.",
    ),
) -> None:
    """Analyze the current Git diff and produce an architecture-focused review."""
    config = load_config()
    rule_registry = RuleRegistry(
        default_rules(
            forbidden_dependencies=config.rules.forbidden_dependencies,
            large_file_changed_lines=config.rules.large_file_changed_lines,
            large_function_lines=config.rules.large_function_lines,
        )
    )
    pipeline = ReviewPipeline(
        git_provider=SubprocessGitProvider(),
        analyzers=[PythonAstAnalyzer()],
        rules=rule_registry.all(),
    )
    result = pipeline.run()
    if output is not None:
        write_review_artifact(result, output)
    report = TerminalReporter().render(result)
    Console().print(report)
