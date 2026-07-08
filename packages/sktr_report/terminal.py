from __future__ import annotations

from sktr_core.model import ReviewResult


class TerminalReporter:
    def render(self, result: ReviewResult) -> str:
        lines = [
            "[bold]SKTR Review[/bold]",
            f"Changed files: {len(result.context.file_changes)}",
        ]

        for change in result.context.file_changes:
            lines.append(f"{self._status_label(change.status)} {change.path}")

        if not result.context.file_changes:
            lines.append(f"Status: {result.status}")

        lines.extend(result.messages)
        return "\n".join(lines)

    def _status_label(self, status: str) -> str:
        return {
            "added": "A",
            "modified": "M",
            "deleted": "D",
            "renamed": "R",
        }.get(status, "?")
