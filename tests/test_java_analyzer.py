from __future__ import annotations

from pathlib import Path

from sktr_core.model import DependencyScope, FileChange, SymbolKind
from sktr_core.plugins import AnalysisContext, GitDiff
from sktr_enrichment import KnowledgeEnrichmentEngine
from sktr_java import JavaAnalyzer
from sktr_rules import NewDependencyDetectedRule, PublicApiChangedRule


def test_java_extracts_packages_types_methods_and_imports(tmp_path: Path) -> None:
    repo = tmp_path / "src/main/java/com/sample/repositories/OrderRepository.java"
    repo.parent.mkdir(parents=True)
    repo.write_text(
        "package com.sample.repositories; public class OrderRepository {}\n",
        encoding="utf-8",
    )
    path = "src/main/java/com/sample/orders/OrderService.java"
    source = """
package com.sample.orders;
import java.util.List;
import com.sample.repositories.OrderRepository;
import static com.sample.repositories.OrderRepository.create;
public record OrderService(String id) {
    public OrderService {}
    @Deprecated public String createOrder() { return id; }
}
interface OrderPort { String load(); }
enum Status { CREATED }
"""
    diff = GitDiff(repository_root=str(tmp_path), changed_files=[path], current_file_contents={path: source})

    system = JavaAnalyzer().analyze(AnalysisContext(diff=diff))
    source_file = system.modules[0].files[0]

    assert source_file.module == "com.sample.orders"
    assert {(symbol.name, symbol.kind, symbol.owner) for symbol in source_file.symbols} >= {
        ("OrderService", SymbolKind.CLASS, None),
        ("OrderService", SymbolKind.METHOD, "OrderService"),
        ("createOrder", SymbolKind.METHOD, "OrderService"),
        ("OrderPort", SymbolKind.INTERFACE, None),
        ("Status", SymbolKind.TYPE, None),
    }
    dependencies = {dependency.target: dependency for dependency in source_file.dependencies}
    assert dependencies["java.util.List"].scope == DependencyScope.STANDARD_LIBRARY
    assert dependencies["com.sample.repositories.OrderRepository"].scope == DependencyScope.INTERNAL
    assert dependencies["com.sample.repositories.OrderRepository"].target_path.endswith("OrderRepository.java")
    assert dependencies["com.sample.repositories.OrderRepository.create"].scope == DependencyScope.INTERNAL
    create_method = next(symbol for symbol in source_file.symbols if symbol.name == "createOrder")
    assert create_method.metadata["body_lines"] >= 1
    assert create_method.metadata["annotations"] == ["Deprecated"]


def test_java_supports_gradle_test_roots_and_reports_parse_diagnostics(tmp_path: Path) -> None:
    path = "src/test/java/com/sample/orders/OrderServiceTest.java"
    source = "package com.sample.orders; class OrderServiceTest { void broken( { }"
    diff = GitDiff(repository_root=str(tmp_path), changed_files=[path], current_file_contents={path: source})

    system = JavaAnalyzer().analyze(AnalysisContext(diff=diff))

    assert system.modules[0].files[0].module == "com.sample.orders"
    assert system.diagnostics
    assert system.diagnostics[0].file_path == path


def test_java_baseline_and_rules_detect_new_internal_dependency(tmp_path: Path) -> None:
    repo = tmp_path / "src/main/java/com/sample/repositories/OrderRepository.java"
    repo.parent.mkdir(parents=True)
    repo.write_text("package com.sample.repositories; public class OrderRepository {}", encoding="utf-8")
    path = "src/main/java/com/sample/orders/OrderService.java"
    baseline = "package com.sample.orders; public class OrderService {}\n"
    current = (
        "package com.sample.orders; import com.sample.repositories.OrderRepository; "
        "public class OrderService {}\n"
    )
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified", added_lines=1)],
        base_file_contents={path: baseline},
        current_file_contents={path: current},
    )
    system = JavaAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = NewDependencyDetectedRule().evaluate(system, AnalysisContext(diff=diff).review)

    assert len(issues) == 1
    assert issues[0].metadata["source"] == "com.sample.orders"
    assert issues[0].metadata["target"] == "com.sample.repositories"


def test_java_deleted_file_retains_baseline_symbols_and_dependencies() -> None:
    path = "src/main/java/com/sample/Legacy.java"
    baseline = (
        "package com.sample; import java.util.List; "
        "public class Legacy { public void run() {} }"
    )
    diff = GitDiff(changed_files=[path], base_file_contents={path: baseline})

    source_file = JavaAnalyzer().analyze(AnalysisContext(diff=diff)).modules[0].files[0]

    assert source_file.symbols == []
    assert source_file.dependencies == []
    assert source_file.metadata["baseline_dependencies"] == ["java.util.List"]
    assert source_file.metadata["baseline_symbols"] == ["class:Legacy", "method:Legacy.run"]


def test_java_repository_snapshot_resolves_classes_without_working_tree_files(tmp_path: Path) -> None:
    path = "src/main/java/com/sample/orders/OrderService.java"
    target = "src/main/java/com/sample/repositories/OrderRepository.java"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path, target],
        current_file_contents={
            path: (
                "package com.sample.orders; "
                "import com.sample.repositories.OrderRepository; "
                "class OrderService {}"
            ),
            target: "package com.sample.repositories; class OrderRepository {}",
        },
        metadata={"graph_scope": "repository", "repository_revision": "abc123"},
    )

    dependency = JavaAnalyzer().analyze(AnalysisContext(diff=diff)).modules[0].files[0].dependencies[0]

    assert dependency.scope == DependencyScope.INTERNAL
    assert dependency.target_path == target


def test_java_visibility_and_inheritance_are_normalized(tmp_path: Path) -> None:
    sources = {
        "services/orders/src/main/java/com/sample/BaseService.java": (
            "package com.sample; public class BaseService {}"
        ),
        "services/orders/src/main/java/com/sample/OrderPort.java": (
            "package com.sample; public interface OrderPort {}"
        ),
        "services/orders/src/main/java/com/sample/OrderService.java": (
            "package com.sample; public class OrderService extends BaseService implements OrderPort { "
            "public void create() {} private void helper() {} }"
        ),
    }
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=list(sources),
        current_file_contents=sources,
        metadata={"graph_scope": "repository"},
    )

    system = JavaAnalyzer().analyze(AnalysisContext(diff=diff))
    service = next(
        source_file for source_file in system.modules[0].files if source_file.path.endswith("OrderService.java")
    )
    symbols = {symbol.name: symbol for symbol in service.symbols}

    assert symbols["OrderService"].api_exposure.value == "exported"
    assert symbols["create"].api_exposure.value == "exported"
    assert symbols["helper"].api_exposure.value == "not_exported"
    assert service.metadata["build_module"] == "services/orders"
    assert {(dependency.kind.value, dependency.target_module) for dependency in service.dependencies} >= {
        ("extends", "com.sample"),
        ("implements", "com.sample"),
    }


def test_java_public_api_rule_ignores_removed_private_method(tmp_path: Path) -> None:
    path = "src/main/java/com/sample/Service.java"
    baseline = (
        "package com.sample; public class Service { "
        "public void run() {} private void helper() {} }"
    )
    current = "package com.sample; public class Service {}"
    diff = GitDiff(
        repository_root=str(tmp_path),
        changed_files=[path],
        file_changes=[FileChange(path=path, status="modified")],
        base_file_contents={path: baseline},
        current_file_contents={path: current},
    )
    system = JavaAnalyzer().analyze(AnalysisContext(diff=diff))
    KnowledgeEnrichmentEngine.default().enrich(system, diff)

    issues = PublicApiChangedRule().evaluate(system, AnalysisContext(diff=diff).review)

    assert [issue.metadata["symbol"] for issue in issues] == ["Service.run"]
