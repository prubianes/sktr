from __future__ import annotations

from pathlib import PurePosixPath

from sktr_core.model import APIExposure, Dependency, DependencyKind, DependencyScope, Module, SourceFile, Symbol, System
from sktr_core.plugins import GitDiff

LARGE_FILE_CHANGED_LINES = 300
MANY_NEW_DEPENDENCIES = 5
LARGE_SYMBOL_LINES = 80


class FileMetricsEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        changes = {change.path: change for change in diff.file_changes}
        for source_file in _source_files(system):
            change = changes.get(source_file.path)
            added = change.added_lines if change else 0
            removed = change.removed_lines if change else 0
            total = added + removed
            estimated_size = sum(_symbol_size(symbol) for symbol in source_file.symbols)
            source_file.metadata["metrics"] = {
                "total_changed_lines": total,
                "added_lines": added,
                "removed_lines": removed,
                "change_ratio": round(total / max(estimated_size, 1), 4),
                "symbol_count": len(source_file.symbols),
                "dependency_count": len(source_file.dependencies),
            }
            source_file.metadata["change_status"] = change.status if change else "unchanged"


class SymbolMetricsEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        changed_paths = {change.path: change for change in diff.file_changes}
        for source_file in _source_files(system):
            baseline_symbols = {
                str(value) for value in source_file.metadata.get("baseline_symbols", [])
            }
            current_symbols = {_symbol_identity(symbol) for symbol in source_file.symbols}
            baseline_public_symbols = {
                str(value) for value in source_file.metadata.get("baseline_public_symbols", [])
            }
            current_public_symbols = {
                _symbol_identity(symbol)
                for symbol in source_file.symbols
                if symbol.api_exposure == APIExposure.EXPORTED
            }
            source_file.metadata["removed_symbols"] = sorted(baseline_symbols - current_symbols)
            source_file.metadata["new_symbols"] = sorted(current_symbols - baseline_symbols)
            source_file.metadata["removed_public_symbols"] = sorted(
                baseline_public_symbols - current_public_symbols
            )
            source_file.metadata["new_public_symbols"] = sorted(
                current_public_symbols - baseline_public_symbols
            )
            change_status = changed_paths.get(source_file.path).status if source_file.path in changed_paths else "unchanged"
            for symbol in source_file.symbols:
                metrics: dict[str, object] = {
                    "estimated_size": _symbol_size(symbol),
                    "change_status": change_status,
                    "dependency_count": len(source_file.dependencies),
                }
                for key in (
                    "complexity",
                    "statement_count",
                    "nested_function_count",
                    "declarative_ratio",
                    "role",
                ):
                    if key in symbol.metadata:
                        metrics[key] = symbol.metadata[key]
                symbol.metadata["metrics"] = metrics


class DependencyEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        changed_paths = {change.path for change in diff.file_changes}
        known_modules = {_source_module(source_file) for source_file in _source_files(system)}
        baseline_edges = {
            (_source_module(source_file), str(target_module))
            for source_file in _source_files(system)
            for target_module in _list(source_file.metadata.get("baseline_dependency_modules"))
            if target_module
        }
        for source_file in _source_files(system):
            source_module = _source_module(source_file)
            baseline_dependencies = {
                str(value) for value in source_file.metadata.get("baseline_dependencies", [])
            }
            current_dependencies = {dependency.target for dependency in source_file.dependencies}
            source_file.metadata["removed_dependencies"] = sorted(baseline_dependencies - current_dependencies)
            for dependency in source_file.dependencies:
                target_module = dependency.target_module or _module_from_dependency(dependency)
                cross_module = bool(target_module and source_module and target_module != source_module)
                scope = dependency.scope.value
                if scope == DependencyScope.UNKNOWN.value:
                    scope = str(dependency.metadata.get("scope", "unknown"))
                dependency.metadata["metrics"] = {
                    "new_dependency": (
                        (source_module, target_module) not in baseline_edges
                        if target_module
                        else dependency.target not in baseline_dependencies
                    ),
                    "removed_dependency": False,
                    "cross_module_dependency": cross_module
                    and (scope == "internal" or target_module in known_modules),
                    "same_module_dependency": bool(target_module and target_module == source_module),
                    "scope": scope,
                    "source_module": source_module,
                    "target_module": target_module,
                }


class ModuleEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        changed_paths = {change.path for change in diff.file_changes}
        for module in system.modules:
            module_files = module.files
            module_names = {_source_module(source_file) for source_file in module_files}
            changed_files = [source_file for source_file in module_files if source_file.path in changed_paths]
            changed_symbols = [
                symbol
                for source_file in changed_files
                for symbol in source_file.symbols
            ]
            incoming = 0
            outgoing = 0
            for source_file in _source_files(system):
                source_module = _source_module(source_file)
                for dependency in source_file.dependencies:
                    target_module = _dependency_metric(dependency, "target_module")
                    is_cross_module = bool(_dependency_metric(dependency, "cross_module_dependency"))
                    if is_cross_module and source_module not in module_names and target_module in module_names:
                        incoming += 1
                    if is_cross_module and source_module in module_names and target_module not in module_names:
                        outgoing += 1

            module.metadata["metrics"] = {
                "changed_files": len(changed_files),
                "changed_symbols": len(changed_symbols),
                "incoming_dependencies": incoming,
                "outgoing_dependencies": outgoing,
            }


class RiskEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        for source_file in _source_files(system):
            indicators: list[dict[str, str]] = []
            metrics = _dict(source_file.metadata.get("metrics"))
            total_changed = int(metrics.get("total_changed_lines", 0))
            if total_changed >= LARGE_FILE_CHANGED_LINES:
                indicators.append({"level": "HIGH", "reason": "file with many changes"})

            new_dependencies = [
                dependency
                for dependency in source_file.dependencies
                if _dependency_metric(dependency, "new_dependency")
                and _dependency_metric(dependency, "cross_module_dependency")
            ]
            if len(new_dependencies) >= MANY_NEW_DEPENDENCIES:
                indicators.append({"level": "MEDIUM", "reason": "many new dependencies"})

            if any(_dependency_metric(dependency, "cross_module_dependency") for dependency in source_file.dependencies):
                indicators.append({"level": "MEDIUM", "reason": "cross-module dependency"})

            for symbol in source_file.symbols:
                symbol_metrics = _dict(symbol.metadata.get("metrics"))
                if (
                    int(symbol_metrics.get("estimated_size", 0)) >= LARGE_SYMBOL_LINES
                    and symbol_metrics.get("change_status") != "unchanged"
                ):
                    indicators.append({"level": "HIGH", "reason": "large modified symbol"})

            source_file.metadata["risk_indicators"] = indicators
            source_file.metadata["risk_level"] = _highest_level([indicator["level"] for indicator in indicators])


class PriorityEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        for source_file in _source_files(system):
            risk_level = str(source_file.metadata.get("risk_level", "LOW"))
            metrics = _dict(source_file.metadata.get("metrics"))
            total_changed = int(metrics.get("total_changed_lines", 0))
            if risk_level == "CRITICAL":
                priority = "URGENT"
            elif risk_level == "HIGH":
                priority = "HIGH"
            elif risk_level == "MEDIUM" or total_changed > 0:
                priority = "NORMAL"
            else:
                priority = "LOW"
            source_file.metadata["review_priority"] = priority


class SummaryEnricher:
    def enrich(self, system: System, diff: GitDiff) -> None:
        changed_paths = {change.path for change in diff.file_changes}
        changed_source_files = [
            source_file for source_file in _source_files(system) if source_file.path in changed_paths
        ]
        changed_modules = {
            _source_module(source_file)
            for source_file in _source_files(system)
            if source_file.metadata.get("change_status") != "unchanged"
        }
        new_dependencies = [
            dependency
            for source_file in _source_files(system)
            for dependency in source_file.dependencies
            if _dependency_metric(dependency, "new_dependency")
            and _dependency_metric(dependency, "cross_module_dependency")
        ]
        cross_module_dependencies = [
            dependency
            for source_file in _source_files(system)
            for dependency in source_file.dependencies
            if _dependency_metric(dependency, "cross_module_dependency")
        ]
        high_risk_files = [
            source_file
            for source_file in _source_files(system)
            if source_file.metadata.get("risk_level") in {"HIGH", "CRITICAL"}
        ]
        high_priority_reviews = [
            source_file
            for source_file in _source_files(system)
            if source_file.metadata.get("review_priority") in {"HIGH", "URGENT"}
        ]
        system.metadata["knowledge_summary"] = {
            "changed_modules": len({module for module in changed_modules if module}),
            "changed_files": len(diff.file_changes),
            "new_dependencies": len(new_dependencies),
            "cross_module_dependencies": len(cross_module_dependencies),
            "high_risk_files": len(high_risk_files),
            "high_priority_reviews": len(high_priority_reviews),
            "production_changed_files": len(
                [source_file for source_file in changed_source_files if not _is_test_path(source_file.path)]
            ),
            "test_changed_files": len(
                [change for change in diff.file_changes if _is_test_path(change.path)]
            ),
            "documentation_changed_files": len(
                [change for change in diff.file_changes if _is_documentation_path(change.path)]
            ),
            "public_api_changes": sum(
                _public_symbol_changes(source_file) for source_file in changed_source_files
            ),
        }


def _source_files(system: System) -> list[SourceFile]:
    return [source_file for module in system.modules for source_file in module.files]


def _list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _is_test_path(path: str) -> bool:
    normalized_path = path.lower().replace("\\", "/")
    normalized = f"/{normalized_path}"
    name = normalized.rsplit("/", 1)[-1]
    return (
        "/tests/" in normalized
        or "/test/" in normalized
        or "/src/test/" in normalized
        or name.startswith("test_")
        or "_test." in name
        or ".test." in name
        or name.endswith("test.java")
    )


def _is_documentation_path(path: str) -> bool:
    normalized = path.lower().replace("\\", "/")
    name = normalized.rsplit("/", 1)[-1]
    return normalized.startswith("docs/") or name.startswith("readme") or name.endswith(".md")


def _public_symbol_changes(source_file: SourceFile) -> int:
    values = [
        *_list(source_file.metadata.get("new_public_symbols")),
        *_list(source_file.metadata.get("removed_public_symbols")),
    ]
    return sum(1 for value in values if not str(value).split(":", 1)[-1].split(".")[-1].startswith("_"))


def _symbol_size(symbol: Symbol) -> int:
    body_lines = symbol.metadata.get("body_lines")
    if isinstance(body_lines, int):
        return body_lines
    if symbol.location is None:
        return 0
    if symbol.location.start_line is None or symbol.location.end_line is None:
        return 0
    return symbol.location.end_line - symbol.location.start_line + 1


def _symbol_identity(symbol: Symbol) -> str:
    qualified_name = f"{symbol.owner}.{symbol.name}" if symbol.owner else symbol.name
    return f"{symbol.kind.value}:{qualified_name}"


def _module_from_path(path: str) -> str:
    parts = [part for part in path.split("/") if part]
    if parts and parts[0] in {"src", "app", "lib", "packages"}:
        parts = parts[1:]
    if not parts:
        return ""
    return PurePosixPath(parts[0]).stem


def _source_module(source_file: SourceFile) -> str:
    return source_file.module or _module_from_path(source_file.path)


def _module_from_dependency(dependency: Dependency) -> str:
    if dependency.kind != DependencyKind.IMPORT:
        return ""
    target = dependency.target.strip(".")
    if not target:
        return ""
    if "/" in target:
        return _module_from_path(target)
    return target.split(".", 1)[0]


def _dependency_metric(dependency: Dependency, key: str) -> object:
    metrics = _dict(dependency.metadata.get("metrics"))
    return metrics.get(key)


def _dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _highest_level(levels: list[str]) -> str:
    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    if not levels:
        return "LOW"
    return max(levels, key=lambda level: order.get(level, 0))
