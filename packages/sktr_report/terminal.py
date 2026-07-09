from __future__ import annotations

from sktr_core.model import Issue, IssueCategory, ReviewResult


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

        architecture_issues = [issue for issue in result.issues if issue.category == IssueCategory.ARCHITECTURE]
        other_issues = [issue for issue in result.issues if issue.category != IssueCategory.ARCHITECTURE]

        if architecture_issues:
            lines.append("")
            lines.append("[bold]Architecture[/bold]")
            lines.extend(self._issue_lines(architecture_issues))

        if other_issues:
            lines.append("")
            lines.append("[bold]Findings[/bold]")
            lines.extend(self._issue_lines(other_issues))

        lines.extend(result.messages)
        return "\n".join(lines)

    def _status_label(self, status: str) -> str:
        return {
            "added": "A",
            "modified": "M",
            "deleted": "D",
            "renamed": "R",
        }.get(status, "?")

    def _issue_lines(self, issues: list[Issue]) -> list[str]:
        lines: list[str] = []
        for issue in issues:
            if issue.metadata.get("rule_key") == "forbidden_dependency":
                lines.extend(self._forbidden_dependency_lines(issue))
            else:
                lines.append(f"[yellow]⚠[/yellow] {issue.title}")
                lines.append(issue.description)
        return lines

    def _forbidden_dependency_lines(self, issue: Issue) -> list[str]:
        source = issue.metadata.get("source", "")
        target = issue.metadata.get("target", "")
        reason = issue.metadata.get("reason") or "This violates configured dependency rules."
        return [
            f"[yellow]⚠[/yellow] {issue.title}",
            f"{source} imports {target}",
            "Reason:",
            reason,
        ]
