from __future__ import annotations

from collections.abc import Sequence

from sktr_core.model import AIReview, ReviewContext, ReviewResult, System
from sktr_core.plugins import AIProvider, AIReviewContext, AnalysisContext, Analyzer, GitDiff, GitProvider, Rule


class ReviewPipeline:
    """Coordinates the review flow without owning language-specific logic."""

    def __init__(
        self,
        *,
        git_provider: GitProvider | None = None,
        analyzers: Sequence[Analyzer] | None = None,
        rules: Sequence[Rule] | None = None,
        ai_provider: AIProvider | None = None,
    ) -> None:
        self.git_provider = git_provider
        self.analyzers = list(analyzers or [])
        self.rules = list(rules or [])
        self.ai_provider = ai_provider

    def run(self) -> ReviewResult:
        diff = self.git_provider.current_diff() if self.git_provider else GitDiff()
        changed_files = self.git_provider.changed_files() if self.git_provider else []
        context = ReviewContext(
            changed_files=changed_files,
            diff_summary=diff.raw if diff.raw else None,
        )

        system = System()
        messages: list[str] = []

        if not self.analyzers:
            messages.append("No analyzers configured yet.")
        else:
            analysis_context = AnalysisContext(review=context, diff=diff)
            systems = [analyzer.analyze(analysis_context) for analyzer in self.analyzers]
            system = self._merge_systems(systems)

        issues = []
        if not self.rules:
            messages.append("No rules configured yet.")
        else:
            for rule in self.rules:
                issues.extend(rule.evaluate(system))

        ai_review: AIReview | None = None
        if self.ai_provider is None:
            messages.append("No AI provider configured yet.")
        else:
            ai_context = AIReviewContext(review=context, system=system, issues=issues)
            ai_review = self.ai_provider.review(ai_context)

        return ReviewResult(
            status="foundation ready",
            context=context,
            system=system,
            issues=issues,
            ai_review=ai_review,
            messages=messages,
        )

    def _merge_systems(self, systems: Sequence[System]) -> System:
        merged = System()
        for system in systems:
            merged.modules.extend(system.modules)
            merged.metadata.update(system.metadata)
        return merged
