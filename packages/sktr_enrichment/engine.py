from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sktr_core.model import System
from sktr_core.plugins import GitDiff
from sktr_enrichment.enrichers import (
    DependencyEnricher,
    FileMetricsEnricher,
    ModuleEnricher,
    PriorityEnricher,
    RiskEnricher,
    SummaryEnricher,
    SymbolMetricsEnricher,
)


class Enricher(Protocol):
    def enrich(self, system: System, diff: GitDiff) -> None: ...


class KnowledgeEnrichmentEngine:
    def __init__(self, enrichers: Sequence[Enricher] | None = None) -> None:
        self.enrichers = list(enrichers or self.default_enrichers())

    def enrich(self, system: System, diff: GitDiff) -> System:
        for enricher in self.enrichers:
            enricher.enrich(system, diff)
        return system

    @classmethod
    def default(cls) -> "KnowledgeEnrichmentEngine":
        return cls()

    @staticmethod
    def default_enrichers() -> list[Enricher]:
        return [
            FileMetricsEnricher(),
            SymbolMetricsEnricher(),
            DependencyEnricher(),
            ModuleEnricher(),
            RiskEnricher(),
            PriorityEnricher(),
            SummaryEnricher(),
        ]
