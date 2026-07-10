from __future__ import annotations

import json
from pathlib import Path

from sktr_core.model import DependencyScope, FileChange, SymbolKind
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_javascript import JavaScriptTypeScriptAnalyzer
from sktr_rules import NewDependencyDetectedRule


def test_javascript_typescript_extracts_symbols_and_dependencies(tmp_path: Path) -> None:
    orders = _workspace(tmp_path, "packages/orders", "@sample/orders")
    payments = _workspace(tmp_path, "packages/payments", "@sample/payments")
    (payments / "client.ts").write_text("export class PaymentClient {}\n", encoding="utf-8")
    path = "packages/orders/service.tsx"
    source = """
import { PaymentClient } from "@sample/payments";
export { audit } from "audit-sdk";
const legacy = require("legacy-sdk");
interface Order { id: string }
type OrderId = string;
export class OrderService { create() { return new PaymentClient(); } }
export function validate() { return true; }
const calculate = () => 1;
"""
    (orders / "service.tsx").write_text(source, encoding="utf-8")
    diff = GitDiff(repository_root=str(tmp_path), changed_files=[path], current_file_contents={path: source})

    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    source_file = system.modules[0].files[0]

    assert source_file.language == "typescript"
    assert source_file.module == "@sample/orders"
    assert {(symbol.name, symbol.kind, symbol.owner) for symbol in source_file.symbols} >= {
        ("Order", SymbolKind.INTERFACE, None),
        ("OrderId", SymbolKind.TYPE, None),
        ("OrderService", SymbolKind.CLASS, None),
        ("create", SymbolKind.METHOD, "OrderService"),
        ("validate", SymbolKind.FUNCTION, None),
        ("calculate", SymbolKind.FUNCTION, None),
    }
    dependencies = {dependency.target: dependency for dependency in source_file.dependencies}
    assert dependencies["@sample/payments"].scope == DependencyScope.INTERNAL
    assert dependencies["@sample/payments"].target_path == "packages/payments"
    assert dependencies["audit-sdk"].scope == DependencyScope.EXTERNAL
    assert dependencies["legacy-sdk"].scope == DependencyScope.EXTERNAL


def test_javascript_resolves_relative_index_and_reports_parse_diagnostics(tmp_path: Path) -> None:
    path = "src/orders/service.js"
    target = tmp_path / "src" / "payments" / "index.js"
    target.parent.mkdir(parents=True)
    target.write_text("export const pay = () => true;\n", encoding="utf-8")
    source = 'import { pay } from "../payments";\nfunction broken( {\n'
    diff = GitDiff(repository_root=str(tmp_path), changed_files=[path], current_file_contents={path: source})

    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    dependency = system.modules[0].files[0].dependencies[0]

    assert dependency.scope == DependencyScope.INTERNAL
    assert dependency.target_path == "src/payments/index.js"
    assert system.diagnostics
    assert system.diagnostics[0].code == "parse_error"


def test_javascript_baseline_and_rules_detect_new_workspace_dependency(tmp_path: Path) -> None:
    orders = _workspace(tmp_path, "packages/orders", "orders")
    _workspace(tmp_path, "packages/payments", "payments")
    path = "packages/orders/service.ts"
    baseline = "export function createOrder() { return true; }\n"
    current = 'import { pay } from "payments";\n' + baseline
    (orders / "service.ts").write_text(current, encoding="utf-8")
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified", added_lines=1)],
        base_file_contents={path: baseline},
        current_file_contents={path: current},
    )
    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = NewDependencyDetectedRule().evaluate(system, AnalysisContext(diff=diff).review)

    assert len(issues) == 1
    assert issues[0].metadata["source"] == "orders"
    assert issues[0].metadata["target"] == "payments"


def test_javascript_deleted_file_keeps_baseline_and_deduplicates_dependencies() -> None:
    path = "src/legacy.ts"
    baseline = 'import "legacy-sdk";\nimport "legacy-sdk";\nexport function legacy() {}\n'
    diff = GitDiff(changed_files=[path], base_file_contents={path: baseline})

    source_file = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff)).modules[0].files[0]

    assert source_file.symbols == []
    assert source_file.dependencies == []
    assert source_file.metadata["baseline_dependencies"] == ["legacy-sdk"]
    assert source_file.metadata["baseline_symbols"] == ["function:legacy"]


def _workspace(root: Path, relative: str, name: str) -> Path:
    path = root / relative
    path.mkdir(parents=True)
    (path / "package.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return path
