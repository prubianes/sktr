from __future__ import annotations

import typer
from rich.console import Console

from sktr_core.pipeline import ReviewPipeline
from sktr_git import SubprocessGitProvider
from sktr_python import PythonAstAnalyzer
from sktr_report import TerminalReporter

app = typer.Typer(help="System Knowledge & Technical Review.")


@app.callback()
def main() -> None:
    """System Knowledge & Technical Review."""


@app.command()
def review() -> None:
    """Analyze the current Git diff and produce an architecture-focused review."""
    pipeline = ReviewPipeline(
        git_provider=SubprocessGitProvider(),
        analyzers=[PythonAstAnalyzer()],
    )
    result = pipeline.run()
    report = TerminalReporter().render(result)
    Console().print(report)
