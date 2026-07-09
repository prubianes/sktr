from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console

from sktr_core.model import Issue, IssueCategory, IssueSeverity, ReviewResult
from sktr_core.plugins import Output
from sktr_report.artifact import review_result_to_json
from sktr_report.summary import risk_level, risk_score


class TerminalOutput:
    format = "terminal"

    def write(self, result: ReviewResult, destination: str | None = None) -> None:
        content = self.render(result)
        if destination is not None:
            _write_text(destination, content)
            return

        Console(file=sys.stdout).print(content)

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


class JsonOutput:
    format = "json"

    def write(self, result: ReviewResult, destination: str | None = None) -> None:
        content = review_result_to_json(result)
        if destination is not None:
            _write_text(destination, content)
            return

        sys.stdout.write(content + "\n")


class MarkdownOutput:
    format = "markdown"

    def write(self, result: ReviewResult, destination: str | None = None) -> None:
        content = self.render(result)
        if destination is not None:
            _write_text(destination, content)
            return

        sys.stdout.write(content + "\n")

    def render(self, result: ReviewResult) -> str:
        score = risk_score(result)
        risk = risk_level(score)
        lines = [
            "# SKTR Review",
            "",
            "## Summary",
            f"Risk: {risk.title()}  ",
            f"Score: {score}/100  ",
            f"Changed files: {len(result.context.file_changes)}  ",
            f"Issues: {len(result.issues)}",
        ]

        lines.append("")
        lines.append("## Changed Files")
        lines.append("| Status | File |")
        lines.append("|---|---|")
        for change in result.context.file_changes:
            lines.append(f"| {self._status_label(change.status)} | {change.path} |")
        if not result.context.file_changes:
            lines.append("| - | No changed files |")

        if result.issues:
            lines.append("")
            lines.append("## Issues")
            lines.extend(self._issues_by_severity(result.issues))

            lines.append("")
            lines.append("## Issues by Category")
            lines.extend(self._issues_by_category(result.issues))

        architecture_issues = [issue for issue in result.issues if issue.category == IssueCategory.ARCHITECTURE]
        maintainability_issues = [issue for issue in result.issues if issue.category == IssueCategory.MAINTAINABILITY]

        lines.append("")
        lines.append("## Architecture Findings")
        if architecture_issues:
            lines.extend(self._issue_blocks(architecture_issues, heading_level=3))
        else:
            lines.append("None.")

        lines.append("")
        lines.append("## Maintainability Findings")
        if maintainability_issues:
            lines.extend(self._issue_blocks(maintainability_issues, heading_level=3))
        else:
            lines.append("None.")

        lines.append("")
        lines.append("## Suggestions")
        suggestions = self._suggestions(result.issues)
        if suggestions:
            for suggestion in suggestions:
                lines.append(f"- {suggestion}")
        else:
            lines.append("- No deterministic suggestions.")

        lines.append("")
        lines.append("## Metadata")
        lines.append("Generated by SKTR.")
        lines.append(f"Status: {result.status}")
        if result.context.metadata.get("review_scope"):
            lines.append(f"Review scope: {result.context.metadata['review_scope']}")
        if result.context.metadata.get("repository_root"):
            lines.append(f"Repository root: {result.context.metadata['repository_root']}")

        return "\n".join(lines)

    def _status_label(self, status: str) -> str:
        return {
            "added": "A",
            "modified": "M",
            "deleted": "D",
            "renamed": "R",
        }.get(status, "?")

    def _issues_by_severity(self, issues: list[Issue]) -> list[str]:
        lines: list[str] = []
        for severity in [
            IssueSeverity.CRITICAL,
            IssueSeverity.HIGH,
            IssueSeverity.MEDIUM,
            IssueSeverity.LOW,
            IssueSeverity.INFO,
        ]:
            severity_issues = [issue for issue in issues if issue.severity == severity]
            if not severity_issues:
                continue
            lines.append(f"### {severity.value.title()}")
            lines.extend(self._issue_blocks(severity_issues, heading_level=4))
        return lines

    def _issues_by_category(self, issues: list[Issue]) -> list[str]:
        lines: list[str] = [
            "| Category | Issues | Highest severity | Affected files | Rules |",
            "|---|---:|---|---|---|",
        ]
        categories = sorted({issue.category for issue in issues}, key=lambda category: category.value)
        for category in categories:
            category_issues = [issue for issue in issues if issue.category == category]
            lines.append(
                "| "
                f"{category.value.title()} | "
                f"{len(category_issues)} | "
                f"{self._highest_severity(category_issues).value.title()} | "
                f"{self._affected_files(category_issues)} | "
                f"{self._rule_names(category_issues)} |"
            )
        return lines

    def _highest_severity(self, issues: list[Issue]) -> IssueSeverity:
        severity_order = {
            IssueSeverity.CRITICAL: 5,
            IssueSeverity.HIGH: 4,
            IssueSeverity.MEDIUM: 3,
            IssueSeverity.LOW: 2,
            IssueSeverity.INFO: 1,
        }
        return max(issues, key=lambda issue: severity_order[issue.severity]).severity

    def _affected_files(self, issues: list[Issue]) -> str:
        files = sorted(
            {
                path
                for issue in issues
                for path in [
                    issue.metadata.get("path"),
                    issue.metadata.get("source"),
                    issue.location.file_path if issue.location else None,
                ]
                if path
            }
        )
        if not files:
            return "-"
        if len(files) <= 3:
            return ", ".join(f"`{path}`" for path in files)
        return ", ".join(f"`{path}`" for path in files[:3]) + f", +{len(files) - 3} more"

    def _rule_names(self, issues: list[Issue]) -> str:
        rules = sorted({issue.metadata.get("rule_name") or issue.rule_id or "unknown" for issue in issues})
        return ", ".join(str(rule) for rule in rules)

    def _issue_blocks(self, issues: list[Issue], *, heading_level: int) -> list[str]:
        lines: list[str] = []
        prefix = "#" * heading_level
        for issue in issues:
            lines.append(f"{prefix} {issue.title}")
            lines.extend(self._issue_body(issue))
        return lines

    def _issue_body(self, issue: Issue) -> list[str]:
        if issue.metadata.get("rule_key") == "forbidden_dependency":
            source = issue.metadata.get("source", "")
            target = issue.metadata.get("target", "")
            reason = issue.metadata.get("reason") or "This violates configured dependency rules."
            return [
                f"`{source}` imports `{target}`.",
                f"Reason: {reason}",
            ]

        if issue.metadata.get("rule_key") == "large_function":
            symbol = issue.metadata.get("symbol", issue.title)
            line_count = issue.metadata.get("line_count", "unknown")
            return [
                f"`{symbol}` has {line_count} lines.",
            ]

        return [issue.description]

    def _suggestions(self, issues: list[Issue]) -> list[str]:
        suggestions: list[str] = []
        for issue in issues:
            suggestion = issue.metadata.get("suggestion")
            if suggestion:
                suggestions.append(suggestion)
            elif issue.metadata.get("rule_key") == "large_function":
                suggestions.append("Consider extracting validation, orchestration, and persistence into smaller functions.")
            elif issue.metadata.get("rule_key") == "forbidden_dependency":
                suggestions.append("Route the dependency through the configured boundary instead of importing it directly.")
        return sorted(dict.fromkeys(suggestions))


def output_for_format(format_name: str) -> Output:
    outputs: dict[str, Output] = {
        "terminal": TerminalOutput(),
        "json": JsonOutput(),
        "markdown": MarkdownOutput(),
    }
    try:
        return outputs[format_name]
    except KeyError:
        supported = ", ".join(sorted(outputs))
        raise ValueError(f"Unsupported output format '{format_name}'. Supported formats: {supported}.") from None


def _write_text(destination: str, content: str) -> None:
    path = Path(destination)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content + "\n", encoding="utf-8")
