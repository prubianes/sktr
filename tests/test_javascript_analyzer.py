from __future__ import annotations

import json
from pathlib import Path

from sktr_core.model import DependencyScope, FileChange, SymbolKind
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_javascript import JavaScriptTypeScriptAnalyzer
from sktr_rules import LargeFunctionDetectedRule, NewDependencyDetectedRule, PublicApiChangedRule


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
    create_method = next(symbol for symbol in source_file.symbols if symbol.name == "create")
    assert create_method.metadata["body_lines"] >= 1


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


def test_javascript_repository_snapshot_resolves_relative_targets_without_files(tmp_path: Path) -> None:
    path = "src/orders/service.ts"
    target = "src/payments/index.ts"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path, target, "package.json"],
        current_file_contents={
            path: 'import { pay } from "../payments";\n',
            target: "export const pay = true;\n",
            "package.json": json.dumps({"name": "snapshot-app"}),
        },
        metadata={"graph_scope": "repository", "repository_revision": "abc123"},
    )

    dependency = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff)).modules[0].files[0].dependencies[0]

    assert dependency.scope == DependencyScope.INTERNAL
    assert dependency.target_path == target
    assert dependency.target_module == "payments"


def test_private_react_helper_removal_is_not_a_public_api_change(tmp_path: Path) -> None:
    path = "components/history/roundHistory.tsx"
    baseline = (
        "function formatDateTime(value: string) { return value; }\n"
        "export default function RoundHistory() { return <div />; }\n"
    )
    current = "export default function RoundHistory() { return <section />; }\n"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified")],
        base_file_contents={path: baseline},
        current_file_contents={path: current},
    )
    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)
    source_file = system.modules[0].files[0]

    assert "function:formatDateTime" in source_file.metadata["removed_symbols"]
    assert source_file.metadata["removed_public_symbols"] == []
    assert PublicApiChangedRule().evaluate(system, AnalysisContext(diff=diff).review) == []


def test_exported_javascript_symbol_removal_remains_a_public_api_change(tmp_path: Path) -> None:
    path = "components/keypad/keypad.tsx"
    baseline = (
        "export const voteStyle = () => 'active';\n"
        "export default function Keypad() { return <div />; }\n"
    )
    current = "export default function Keypad() { return <button />; }\n"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified")],
        base_file_contents={path: baseline},
        current_file_contents={path: current},
    )
    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = PublicApiChangedRule().evaluate(system, AnalysisContext(diff=diff).review)

    assert [issue.metadata["symbol"] for issue in issues] == ["voteStyle"]


def test_nextjs_root_package_uses_logical_route_and_component_modules(tmp_path: Path) -> None:
    sources = {
        "package.json": json.dumps({"name": "storyvote"}),
        "app/(room)/roomPageClient.tsx": "export default function RoomPageClient() { return <div />; }\n",
        "app/api/admin/story/route.ts": "export function POST() { return new Response(); }\n",
        "components/history/roundHistory.tsx": "export default function RoundHistory() { return <div />; }\n",
        "components/keypad/keypad.tsx": "export default function Keypad() { return <div />; }\n",
    }
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=list(sources),
        current_file_contents=sources,
        metadata={"graph_scope": "repository"},
    )

    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    modules = {source_file.path: source_file.module for source_file in system.modules[0].files}

    assert modules == {
        "app/(room)/roomPageClient.tsx": "app",
        "app/api/admin/story/route.ts": "app/api/admin",
        "components/history/roundHistory.tsx": "components/history",
        "components/keypad/keypad.tsx": "components/keypad",
    }
    assert all(source_file.metadata["package"] == "storyvote" for source_file in system.modules[0].files)


def test_declarative_react_component_gets_a_higher_size_threshold(tmp_path: Path) -> None:
    path = "components/header/header.tsx"
    jsx = "\n".join(f"      <span>{index}</span>" for index in range(95))
    source = (
        "export function Header() {\n"
        "  return (\n"
        "    <header>\n"
        f"{jsx}\n"
        "    </header>\n"
        "  );\n"
        "}\n"
    )
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified")],
        current_file_contents={path: source},
    )
    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)
    header = next(symbol for symbol in system.modules[0].files[0].symbols if symbol.name == "Header")

    assert header.metadata["metrics"]["role"] == "ui_component"
    assert header.metadata["metrics"]["declarative_ratio"] >= 0.5
    assert LargeFunctionDetectedRule(threshold=80).evaluate(system, AnalysisContext(diff=diff).review) == []


def test_javascript_analyzer_detects_package_test_infrastructure(tmp_path: Path) -> None:
    (tmp_path / "package.json").write_text(
        json.dumps({"scripts": {"test": "vitest run"}, "devDependencies": {"vitest": "latest"}}),
        encoding="utf-8",
    )
    path = "src/app.ts"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        current_file_contents={path: "export function app() { return true; }\n"},
    )

    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))

    assert system.metadata["test_infrastructure_detected"] is True


def test_typescript_path_alias_resolves_to_internal_logical_module(tmp_path: Path) -> None:
    path = "components/header/header.tsx"
    target = "system/supabase.ts"
    sources = {
        "tsconfig.json": json.dumps(
            {"compilerOptions": {"baseUrl": ".", "paths": {"@/*": ["./*"]}}}
        ),
        path: 'import { client } from "@/system/supabase";\nexport function Header() { return <div />; }\n',
        target: "export const client = {};\n",
    }
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=list(sources),
        current_file_contents=sources,
        metadata={"graph_scope": "repository"},
    )

    system = JavaScriptTypeScriptAnalyzer().analyze(AnalysisContext(diff=diff))
    header = next(source_file for source_file in system.modules[0].files if source_file.path == path)
    dependency = header.dependencies[0]

    assert dependency.scope == DependencyScope.INTERNAL
    assert dependency.target_path == target
    assert dependency.source_module == "components/header"
    assert dependency.target_module == "system"


def _workspace(root: Path, relative: str, name: str) -> Path:
    path = root / relative
    path.mkdir(parents=True)
    (path / "package.json").write_text(json.dumps({"name": name}), encoding="utf-8")
    return path
