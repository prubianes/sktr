from __future__ import annotations

from sktr_core.model import ReviewResult


class TerminalReporter:
    def render(self, result: ReviewResult) -> str:
        lines = [
            "[bold]SKTR Review[/bold]",
            f"Status: {result.status}",
        ]
        lines.extend(result.messages)
        return "\n".join(lines)
