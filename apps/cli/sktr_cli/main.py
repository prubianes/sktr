from __future__ import annotations

import typer
from rich.console import Console

from sktr_core.pipeline import ReviewPipeline
from sktr_report import TerminalReporter

app = typer.Typer(help="System Knowledge & Technical Review.")


@app.command()
def review() -> None:
    """Analyze the current Git diff and produce an architecture-focused review."""
    pipeline = ReviewPipeline()
    result = pipeline.run()
    report = TerminalReporter().render(result)
    Console().print(report)
