from __future__ import annotations

from dataclasses import dataclass

from sktr_core.config import DEFAULT_ENABLED_RULES, ForbiddenDependency, RuleConfig
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
    key: str = "new_dependency"
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
                            "rule_key": self.key,
                            "rule_name": self.name,
                            "source": dependency.source,
                            "target": dependency.target,
                            "dependency_kind": dependency.kind.value,
                        },
                    )
                )
        return issues


@dataclass(frozen=True)
class LargeFileChangedRule:
    threshold: int = 300
    id: str = "change.large_file"
    key: str = "large_file"
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
                        "rule_key": self.key,
                        "rule_name": self.name,
                        "path": change.path,
                        "status": change.status,
                        "added_lines": str(change.added_lines),
                        "removed_lines": str(change.removed_lines),
                        "changed_lines": str(changed_lines),
                        "max_changed_lines": str(self.threshold),
                    },
                )
            )
        return issues


@dataclass(frozen=True)
class LargeFunctionDetectedRule:
    threshold: int = 80
    id: str = "symbol.large_function"
    key: str = "large_function"
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
                            "rule_key": self.key,
                            "rule_name": self.name,
                            "path": source_file.path,
                            "symbol": symbol.name,
                            "symbol_kind": symbol.kind.value,
                            "line_count": str(line_count),
                            "max_lines": str(self.threshold),
                        },
                    )
                )
        return issues


@dataclass(frozen=True)
class ForbiddenDependencyRule:
    forbidden_dependencies: list[ForbiddenDependency]
    id: str = "architecture.forbidden_dependency"
    key: str = "forbidden_dependency"
    name: str = "Forbidden dependency"

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
                        title=self.name,
                        description=(
                            f"{dependency.source} imports {target_path}.\n"
                            f"Reason:\n{violation.reason or 'This violates configured dependency rules.'}"
                        ),
                        severity=IssueSeverity.HIGH,
                        category=IssueCategory.ARCHITECTURE,
                        location=dependency.location,
                        rule_id=self.id,
                        metadata={
                            "rule_key": self.key,
                            "rule_name": self.name,
                            "source": dependency.source,
                            "target": target_path,
                            "forbidden_source": violation.source,
                            "forbidden_target": violation.target,
                            "reason": violation.reason or "",
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
    enabled: list[str] | None = None,
    forbidden_dependencies: list[ForbiddenDependency] | None = None,
    large_file_max_changed_lines: int = 300,
    large_function_max_lines: int = 80,
) -> list[Rule]:
    enabled_rules = set(enabled or DEFAULT_ENABLED_RULES)
    rules_by_key: dict[str, Rule] = {
        "new_dependency": NewDependencyDetectedRule(),
        "large_file": LargeFileChangedRule(threshold=large_file_max_changed_lines),
        "large_function": LargeFunctionDetectedRule(threshold=large_function_max_lines),
        "forbidden_dependency": ForbiddenDependencyRule(forbidden_dependencies=forbidden_dependencies or []),
    }
    return [rule for key, rule in rules_by_key.items() if key in enabled_rules]


def rules_from_config(config: RuleConfig) -> list[Rule]:
    return default_rules(
        enabled=config.enabled,
        forbidden_dependencies=config.forbidden_dependencies,
        large_file_max_changed_lines=config.large_file.max_changed_lines,
        large_function_max_lines=config.large_function.max_lines,
    )


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
