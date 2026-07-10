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
        del context
        edges: dict[tuple[str, str], list[Dependency]] = {}
        for source_file in _source_files(system):
            if _is_test_path(source_file.path):
                continue
            for dependency in source_file.dependencies:
                if dependency.kind != DependencyKind.IMPORT:
                    continue
                metrics = _metadata_dict(dependency.metadata.get("metrics"))
                if not metrics.get("new_dependency") or not metrics.get("cross_module_dependency"):
                    continue
                source_module = str(metrics.get("source_module", ""))
                target_module = str(metrics.get("target_module", ""))
                if not source_module or not target_module:
                    continue
                edges.setdefault((source_module, target_module), []).append(dependency)

        issues: list[Issue] = []
        for (source_module, target_module), dependencies in sorted(edges.items()):
            paths = sorted({dependency.source for dependency in dependencies})
            count = len(dependencies)
            detail = "import" if count == 1 else f"{count} imports"
            issues.append(
                Issue(
                    id=f"{self.id}:{source_module}:{target_module}",
                    title="New dependency detected",
                    description=(
                        f"{source_module} added {detail} to {target_module} "
                        f"across {len(paths)} file{'s' if len(paths) != 1 else ''}."
                    ),
                    severity=IssueSeverity.INFO,
                    category=IssueCategory.COUPLING,
                    location=dependencies[0].location,
                    rule_id=self.id,
                    metadata={
                        "rule_key": self.key,
                        "rule_name": self.name,
                        "source": source_module,
                        "target": target_module,
                        "paths": ",".join(paths),
                        "dependency_count": str(count),
                        "dependency_kind": DependencyKind.IMPORT.value,
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
        files_by_path = {source_file.path: source_file for source_file in _source_files(system)}
        for change in context.file_changes:
            metrics = _metadata_dict(files_by_path.get(change.path).metadata.get("metrics")) if change.path in files_by_path else {}
            changed_lines = int(metrics.get("total_changed_lines", change.added_lines + change.removed_lines))
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
                metrics = _metadata_dict(symbol.metadata.get("metrics"))
                line_count = int(metrics.get("estimated_size", _line_count(symbol) or 0))
                change_status = str(metrics.get("change_status", source_file.metadata.get("change_status", "unknown")))
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
                            "change_status": change_status,
                            "max_lines": str(self.threshold),
                            "suggestion": (
                                "Consider extracting validation, orchestration, and persistence into smaller functions."
                            ),
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


@dataclass(frozen=True)
class DependencyCycleRule:
    id: str = "architecture.dependency_cycle"
    key: str = "dependency_cycle"
    name: str = "Dependency cycle detected"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        del context
        graph: dict[str, set[str]] = {}
        for source_file in _source_files(system):
            if _is_test_path(source_file.path):
                continue
            for dependency in source_file.dependencies:
                metrics = _metadata_dict(dependency.metadata.get("metrics"))
                source = str(metrics.get("source_module", ""))
                target = str(metrics.get("target_module", ""))
                if source and target and source != target and metrics.get("cross_module_dependency"):
                    graph.setdefault(source, set()).add(target)

        cycles = _dependency_cycles(graph)
        return [
            Issue(
                id=f"{self.id}:{'->'.join(cycle)}",
                title=self.name,
                description=f"Module dependency cycle detected: {' -> '.join(cycle)}.",
                severity=IssueSeverity.HIGH,
                category=IssueCategory.ARCHITECTURE,
                rule_id=self.id,
                metadata={"rule_key": self.key, "rule_name": self.name, "cycle": " -> ".join(cycle)},
            )
            for cycle in cycles
        ]


@dataclass(frozen=True)
class HighFanOutRule:
    threshold: int = 8
    id: str = "coupling.high_fan_out"
    key: str = "high_fan_out"
    name: str = "High module fan-out"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        del context
        targets_by_source: dict[str, set[str]] = {}
        paths_by_source: dict[str, str] = {}
        for source_file in _source_files(system):
            if _is_test_path(source_file.path):
                continue
            for dependency in source_file.dependencies:
                metrics = _metadata_dict(dependency.metadata.get("metrics"))
                source = str(metrics.get("source_module", ""))
                target = str(metrics.get("target_module", ""))
                if source and target and metrics.get("cross_module_dependency"):
                    targets_by_source.setdefault(source, set()).add(target)
                    paths_by_source.setdefault(source, source_file.path)
        return [
            Issue(
                id=f"{self.id}:{source}",
                title=self.name,
                description=f"Module {source} depends on {len(targets)} other modules.",
                severity=IssueSeverity.MEDIUM,
                category=IssueCategory.COUPLING,
                rule_id=self.id,
                metadata={
                    "rule_key": self.key,
                    "rule_name": self.name,
                    "path": paths_by_source[source],
                    "module": source,
                    "fan_out": str(len(targets)),
                    "max_modules": str(self.threshold),
                },
            )
            for source, targets in sorted(targets_by_source.items())
            if len(targets) > self.threshold
        ]


@dataclass(frozen=True)
class PublicApiChangedRule:
    id: str = "api.public_symbol_removed"
    key: str = "public_api_change"
    name: str = "Public API symbol removed"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        del context
        issues: list[Issue] = []
        for source_file in _source_files(system):
            if _is_test_path(source_file.path):
                continue
            removed = [str(value) for value in source_file.metadata.get("removed_symbols", [])]
            removed_set = set(removed)
            for value in removed:
                kind, _, symbol = value.partition(":")
                if not symbol or symbol.rsplit(".", 1)[-1].startswith("_"):
                    continue
                if kind == SymbolKind.METHOD.value:
                    owner, separator, _ = symbol.rpartition(".")
                    if separator and any(
                        f"{container_kind.value}:{owner}" in removed_set
                        for container_kind in (SymbolKind.CLASS, SymbolKind.INTERFACE)
                    ):
                        continue
                if kind == SymbolKind.METHOD.value and "." not in symbol:
                    continue
                issues.append(
                    Issue(
                        id=f"{self.id}:{source_file.path}:{value}",
                        title=self.name,
                        description=f"{symbol} was removed from {source_file.path}.",
                        severity=IssueSeverity.HIGH,
                        category=IssueCategory.ARCHITECTURE,
                        rule_id=self.id,
                        metadata={
                            "rule_key": self.key,
                            "rule_name": self.name,
                            "path": source_file.path,
                            "symbol": symbol,
                        },
                    )
                )
        return issues


@dataclass(frozen=True)
class MissingTestsRule:
    id: str = "testing.missing_changes"
    key: str = "missing_tests"
    name: str = "Source changes without test changes"

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]:
        changed_paths = {change.path for change in context.file_changes}
        source_paths = {source_file.path for source_file in _source_files(system)}
        if not source_paths or any(_is_test_path(path) for path in changed_paths):
            return []
        affected = sorted(path for path in source_paths if path in changed_paths and not _is_test_path(path))
        if not affected:
            return []
        return [
            Issue(
                id=self.id,
                title=self.name,
                description=f"{len(affected)} source files changed without corresponding test-file changes.",
                severity=IssueSeverity.LOW,
                category=IssueCategory.TESTING,
                rule_id=self.id,
                metadata={
                    "rule_key": self.key,
                    "rule_name": self.name,
                    "path": affected[0],
                    "affected_files": ",".join(affected),
                    "suggestion": "Add or update focused tests for the changed behavior.",
                },
            )
        ]


def default_rules(
    *,
    enabled: list[str] | None = None,
    forbidden_dependencies: list[ForbiddenDependency] | None = None,
    large_file_max_changed_lines: int = 300,
    large_function_max_lines: int = 80,
    fan_out_max_modules: int = 8,
) -> list[Rule]:
    enabled_rules = set(enabled or DEFAULT_ENABLED_RULES)
    rules_by_key: dict[str, Rule] = {
        "new_dependency": NewDependencyDetectedRule(),
        "large_file": LargeFileChangedRule(threshold=large_file_max_changed_lines),
        "large_function": LargeFunctionDetectedRule(threshold=large_function_max_lines),
        "forbidden_dependency": ForbiddenDependencyRule(forbidden_dependencies=forbidden_dependencies or []),
        "dependency_cycle": DependencyCycleRule(),
        "high_fan_out": HighFanOutRule(threshold=fan_out_max_modules),
        "public_api_change": PublicApiChangedRule(),
        "missing_tests": MissingTestsRule(),
    }
    return [rule for key, rule in rules_by_key.items() if key in enabled_rules]


def rules_from_config(config: RuleConfig) -> list[Rule]:
    return default_rules(
        enabled=config.enabled,
        forbidden_dependencies=config.forbidden_dependencies,
        large_file_max_changed_lines=config.large_file.max_changed_lines,
        large_function_max_lines=config.large_function.max_lines,
        fan_out_max_modules=config.fan_out.max_modules,
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


def _metadata_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _is_test_path(path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    normalized = f"/{normalized_path}"
    name = normalized.rsplit("/", 1)[-1]
    return "/tests/" in normalized or "/test/" in normalized or name.startswith("test_") or "_test." in name


def _dependency_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: set[tuple[str, ...]] = set()

    def visit(node: str, path: list[str]) -> None:
        if node in path:
            cycle = path[path.index(node):] + [node]
            body = cycle[:-1]
            rotations = [tuple(body[index:] + body[:index]) for index in range(len(body))]
            canonical = min(rotations)
            cycles.add((*canonical, canonical[0]))
            return
        if len(path) > len(graph):
            return
        for target in sorted(graph.get(node, set())):
            visit(target, [*path, node])

    for node in sorted(graph):
        visit(node, [])
    return [list(cycle) for cycle in sorted(cycles)]
