from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sktr_core.model import AIReview, ReviewContext, ReviewResult, System
from sktr_core.plugins import AIProvider, AIReviewContext, AnalysisContext, Analyzer, GitDiff, GitProvider, Rule


class EnrichmentEngine(Protocol):
    def enrich(self, system: System, diff: GitDiff) -> System: ...


class ReviewPipeline:
    """Coordinates the review flow without owning language-specific logic."""

    def __init__(
        self,
        *,
        diff: GitDiff | None = None,
        git_provider: GitProvider | None = None,
        analyzers: Sequence[Analyzer] | None = None,
        enrichment_engine: EnrichmentEngine | None = None,
        rules: Sequence[Rule] | None = None,
        ai_provider: AIProvider | None = None,
        run_ai: bool = False,
    ) -> None:
        self.diff = diff
        self.git_provider = git_provider
        self.analyzers = list(analyzers or [])
        self.enrichment_engine = enrichment_engine
        self.rules = list(rules or [])
        self.ai_provider = ai_provider
        self.run_ai = run_ai

    def run(self) -> ReviewResult:
        diff = self.diff or (self.git_provider.current_diff() if self.git_provider else GitDiff())
        changed_files = diff.changed_files
        context = ReviewContext(
            changed_files=changed_files,
            file_changes=diff.file_changes,
            excluded_files=diff.excluded_files,
            repository_files=diff.repository_files,
            diff_summary=diff.raw if diff.raw else None,
            metadata={
                **diff.metadata,
                **({"repository_root": diff.repository_root} if diff.repository_root else {}),
            },
        )

        system = System()
        messages: list[str] = []

        if not self.analyzers:
            messages.append("No analyzers configured yet.")
        else:
            analysis_context = AnalysisContext(review=context, diff=diff)
            systems = [analyzer.analyze(analysis_context) for analyzer in self.analyzers]
            system = self._merge_systems(systems)

        if self.enrichment_engine is not None:
            system = self.enrichment_engine.enrich(system, diff)

        issues = []
        rules_executed = []
        if not self.rules:
            messages.append("No rules configured yet.")
        else:
            for rule in self.rules:
                rules_executed.append(
                    {
                        "id": rule.id,
                        "name": rule.name,
                    }
                )
                issues.extend(rule.evaluate(system, context))

        ai_review: AIReview | None = None
        if self.ai_provider is None and self.run_ai:
            messages.append("No AI provider configured yet.")
        elif self.ai_provider is not None and self.run_ai:
            ai_context = AIReviewContext(review=context, system=system, issues=issues)
            ai_review = self.ai_provider.review(ai_context)

        return ReviewResult(
            status="review complete",
            context=context,
            system=system,
            issues=issues,
            diagnostics=system.diagnostics,
            ai_review=ai_review,
            knowledge_summary=_knowledge_summary(system),
            messages=messages,
            metadata={"rules_executed": rules_executed},
        )

    def _merge_systems(self, systems: Sequence[System]) -> System:
        merged = System()
        analyzer_names: list[str] = []
        test_infrastructure_detected = False
        for system in systems:
            merged.modules.extend(system.modules)
            merged.diagnostics.extend(system.diagnostics)
            analyzer = system.metadata.get("analyzer")
            if isinstance(analyzer, str):
                analyzer_names.append(analyzer)
            test_infrastructure_detected = test_infrastructure_detected or bool(
                system.metadata.get("test_infrastructure_detected", False)
            )
            merged.metadata.update({key: value for key, value in system.metadata.items() if key != "analyzer"})
        merged.metadata["analyzers"] = analyzer_names
        merged.metadata["test_infrastructure_detected"] = test_infrastructure_detected
        return merged


def _knowledge_summary(system: System) -> dict[str, int]:
    value = system.metadata.get("knowledge_summary", {})
    if not isinstance(value, dict):
        return {}
    return {str(key): int(metric) for key, metric in value.items() if isinstance(metric, int)}
