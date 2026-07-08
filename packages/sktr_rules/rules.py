from __future__ import annotations

from dataclasses import dataclass

from sktr_core.config import ForbiddenDependency
from sktr_core.model import (
    Dependency,
    DependencyKind,
    Issue,
    IssueCategory,
    IssueSeverity,
    ReviewContext,
    SourceFile,
    Symbol,
    SymbolKind,
    System,
)
from sktr_core.plugins import Rule


@dataclass(frozen=True)
class NewDependencyDetectedRule:
    id: str = "dependency.new"
    name: str = "New dependency detected"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for source_file in _source_files(system):
            for dependency in source_file.dependencies:
                if dependency.kind != DependencyKind.IMPORT:
                    continue
                issues.append(
                    Issue(
                        id=f"{self.id}:{dependency.source}:{dependency.target}",
                        title="New dependency detected",
                        description=f"{dependency.source} imports {dependency.target}.",
                        severity=IssueSeverity.INFO,
                        category=IssueCategory.COUPLING,
                        location=dependency.location,
                        rule_id=self.id,
                        metadata={
                            "source": dependency.source,
                            "target": dependency.target,
                        },
                    )
                )
        return issues


@dataclass(frozen=True)
class LargeFileChangedRule:
    threshold: int = 300
    id: str = "change.large_file"
    name: str = "Large file changed"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for change in context.file_changes:
            changed_lines = change.added_lines + change.removed_lines
            if changed_lines < self.threshold:
                continue
            issues.append(
                Issue(
                    id=f"{self.id}:{change.path}",
                    title="Large file changed",
                    description=f"{change.path} changed {changed_lines} lines.",
                    severity=IssueSeverity.MEDIUM,
                    category=IssueCategory.MAINTAINABILITY,
                    rule_id=self.id,
                    metadata={
                        "path": change.path,
                        "changed_lines": str(changed_lines),
                        "threshold": str(self.threshold),
                    },
                )
            )
        return issues


@dataclass(frozen=True)
class LargeFunctionDetectedRule:
    threshold: int = 80
    id: str = "symbol.large_function"
    name: str = "Large function detected"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for source_file in _source_files(system):
            for symbol in source_file.symbols:
                if symbol.kind not in {SymbolKind.FUNCTION, SymbolKind.METHOD}:
                    continue
                line_count = _line_count(symbol)
                if line_count is None or line_count < self.threshold:
                    continue
                issues.append(
                    Issue(
                        id=f"{self.id}:{source_file.path}:{symbol.name}",
                        title="Large function detected",
                        description=f"{symbol.name} in {source_file.path} is {line_count} lines long.",
                        severity=IssueSeverity.MEDIUM,
                        category=IssueCategory.MAINTAINABILITY,
                        location=symbol.location,
                        rule_id=self.id,
                        metadata={
                            "path": source_file.path,
                            "symbol": symbol.name,
                            "line_count": str(line_count),
                            "threshold": str(self.threshold),
                        },
                    )
                )
        return issues


@dataclass(frozen=True)
class ForbiddenDependencyRule:
    forbidden_dependencies: list[ForbiddenDependency]
    id: str = "architecture.forbidden_dependency"
    name: str = "Direct import between forbidden modules"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        issues: list[Issue] = []
        for source_file in _source_files(system):
            for dependency in source_file.dependencies:
                violation = self._violation(dependency)
                if violation is None:
                    continue
                target_path = _target_path(dependency.target)
                issues.append(
                    Issue(
                        id=f"{self.id}:{dependency.source}:{dependency.target}",
                        title="Direct import between forbidden modules",
                        description=(
                            f"{dependency.source} imports {target_path} directly.\n"
                            "This violates configured dependency rules."
                        ),
                        severity=IssueSeverity.HIGH,
                        category=IssueCategory.ARCHITECTURE,
                        location=dependency.location,
                        rule_id=self.id,
                        metadata={
                            "source": dependency.source,
                            "target": target_path,
                            "forbidden_source": violation.source,
                            "forbidden_target": violation.target,
                        },
                    )
                )
        return issues

    def _violation(self, dependency: Dependency) -> ForbiddenDependency | None:
        if dependency.kind != DependencyKind.IMPORT:
            return None
        source_parts = _parts(dependency.source)
        target_parts = _parts(dependency.target)
        for forbidden in self.forbidden_dependencies:
            if forbidden.source in source_parts and forbidden.target in target_parts:
                return forbidden
        return None


def default_rules(
    *,
    forbidden_dependencies: list[ForbiddenDependency] | None = None,
    large_file_changed_lines: int = 300,
    large_function_lines: int = 80,
) -> list[Rule]:
    rules: list[Rule] = [
        NewDependencyDetectedRule(),
        LargeFileChangedRule(threshold=large_file_changed_lines),
        LargeFunctionDetectedRule(threshold=large_function_lines),
    ]
    if forbidden_dependencies:
        rules.append(ForbiddenDependencyRule(forbidden_dependencies=forbidden_dependencies))
    return rules


def _source_files(system: System) -> list[SourceFile]:
    return [source_file for module in system.modules for source_file in module.files]


def _line_count(symbol: Symbol) -> int | None:
    if symbol.location is None:
        return None
    if symbol.location.start_line is None or symbol.location.end_line is None:
        return None
    return symbol.location.end_line - symbol.location.start_line + 1


def _parts(value: str) -> set[str]:
    normalized = value.replace(".", "/")
    return {part for part in normalized.split("/") if part}


def _target_path(target: str) -> str:
    if target.endswith(".py"):
        return target
    return target.replace(".", "/") + ".py"
