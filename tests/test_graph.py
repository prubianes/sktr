from __future__ import annotations

from pathlib import Path

from sktr_core.model import Dependency, DependencyKind, DependencyScope, Module, SourceFile, System
from sktr_graph import GraphBuilder, GraphLevel, GraphQuery, MermaidGraphOutput


def test_module_graph_generation_deduplicates_edges() -> None:
    graph = GraphBuilder().build(_system(), level=GraphLevel.MODULE)

    assert [node.id for node in graph.nodes] == ["invoices", "orders", "payments"]
    assert [(edge.source, edge.target) for edge in graph.edges] == [
        ("orders", "payments"),
        ("payments", "invoices"),
    ]
    assert MermaidGraphOutput().render(graph) == "\n".join(
        [
            "graph TD",
            '  invoices["invoices"]',
            '  orders["orders"]',
            '  payments["payments"]',
            "  orders --> payments",
            "  payments --> invoices",
        ]
    )


def test_file_graph_generation_uses_known_files_only() -> None:
    graph = GraphBuilder().build(_system(), level=GraphLevel.FILE)

    assert [(edge.source, edge.target) for edge in graph.edges] == [
        ("orders/service.py", "payments/client.py"),
        ("payments/client.py", "invoices/api.py"),
    ]


def test_mermaid_graph_output_writes_to_stdout(capsys) -> None:
    graph = GraphBuilder().build(_system(), level=GraphLevel.MODULE)

    MermaidGraphOutput().write(graph)

    assert "orders --> payments" in capsys.readouterr().out


def test_mermaid_graph_output_writes_to_file(tmp_path: Path) -> None:
    graph = GraphBuilder().build(_system(), level=GraphLevel.MODULE)
    output_path = tmp_path / "architecture.mmd"

    MermaidGraphOutput().write(graph, str(output_path))

    assert output_path.read_text(encoding="utf-8").startswith("graph TD\n")


def test_change_graph_keeps_unchanged_internal_target_as_context() -> None:
    system = System(
        modules=[
            Module(
                name="python",
                files=[
                    SourceFile(
                        path="orders/service.py",
                        module="orders",
                        dependencies=[
                            Dependency(
                                source="orders/service.py",
                                target="payments.client",
                                target_module="payments",
                                target_path="payments/client.py",
                                kind=DependencyKind.IMPORT,
                                scope=DependencyScope.INTERNAL,
                            )
                        ],
                    )
                ],
            )
        ]
    )

    graph = GraphBuilder().build(system, changed_files={"orders/service.py"})

    assert [(node.id, node.changed, node.context) for node in graph.nodes] == [
        ("orders", True, False),
        ("payments", False, True),
    ]
    rendered = MermaidGraphOutput().render(graph)
    assert "class orders changed" in rendered
    assert "class payments context" in rendered


def test_file_graph_renders_module_subgraphs_and_isolated_nodes() -> None:
    graph = GraphBuilder().build(_system(), level=GraphLevel.FILE)

    rendered = MermaidGraphOutput().render(graph)

    assert 'subgraph module_invoices["invoices"]' in rendered
    assert 'invoices_api_py["invoices/api.py"]' in rendered
    assert 'orders_service_py --> payments_client_py' in rendered


def test_graph_queries_support_focus_traversal_and_cycles() -> None:
    graph = GraphBuilder().build(_cyclic_system())
    query = GraphQuery()

    assert [node.id for node in query.focus(graph, "payments").nodes] == [
        "invoices",
        "orders",
        "payments",
    ]
    assert [node.id for node in query.dependencies_of(graph, "orders").nodes] == [
        "invoices",
        "orders",
        "payments",
    ]
    assert [node.id for node in query.dependents_of(graph, "orders").nodes] == [
        "invoices",
        "orders",
        "payments",
    ]
    assert [(edge.source, edge.target) for edge in query.cycles(graph).edges] == [
        ("invoices", "orders"),
        ("orders", "payments"),
        ("payments", "invoices"),
    ]


def test_mermaid_node_ids_are_stable_when_normalized_paths_collide() -> None:
    system = System(
        modules=[
            Module(
                name="mixed",
                files=[
                    SourceFile(path="a-b.py", module="a-b"),
                    SourceFile(path="a/b.py", module="a/b"),
                ],
            )
        ]
    )

    rendered_once = MermaidGraphOutput().render(GraphBuilder().build(system))
    rendered_twice = MermaidGraphOutput().render(GraphBuilder().build(system))

    assert rendered_once == rendered_twice
    declarations = [line for line in rendered_once.splitlines() if line.startswith("  a_b_")]
    assert len(declarations) == 2


def test_graph_combines_normalized_dependencies_from_mixed_languages() -> None:
    files = [
        SourceFile(
            path="services/orders.py",
            language="python",
            module="orders",
            dependencies=[
                Dependency(
                    source="services/orders.py",
                    target="web.payments",
                    target_module="payments",
                    target_path="web/payments.ts",
                    scope=DependencyScope.INTERNAL,
                )
            ],
        ),
        SourceFile(
            path="web/payments.ts",
            language="typescript",
            module="payments",
            dependencies=[
                Dependency(
                    source="web/payments.ts",
                    target="com.sample.Invoices",
                    target_module="invoices",
                    target_path="src/main/java/com/sample/Invoices.java",
                    scope=DependencyScope.INTERNAL,
                )
            ],
        ),
        SourceFile(
            path="src/main/java/com/sample/Invoices.java",
            language="java",
            module="invoices",
        ),
    ]

    graph = GraphBuilder().build(System(modules=[Module(name="mixed", files=files)]))

    assert [(edge.source, edge.target) for edge in graph.edges] == [
        ("orders", "payments"),
        ("payments", "invoices"),
    ]
    file_graph = GraphBuilder().build(
        System(modules=[Module(name="mixed", files=files)]),
        level=GraphLevel.FILE,
    )
    java_node = next(
        node
        for node in file_graph.nodes
        if node.id == "src/main/java/com/sample/Invoices.java"
    )
    assert java_node.module == "invoices"


def _system() -> System:
    return System(
        modules=[
            Module(
                name="python",
                files=[
                    SourceFile(
                        path="orders/service.py",
                        dependencies=[
                            Dependency(
                                source="orders/service.py",
                                target="payments.client",
                                target_path="payments/client.py",
                                kind=DependencyKind.IMPORT,
                            ),
                            Dependency(
                                source="orders/service.py",
                                target="payments.client",
                                target_path="payments/client.py",
                                kind=DependencyKind.IMPORT,
                            ),
                            Dependency(
                                source="orders/service.py",
                                target="os",
                                kind=DependencyKind.IMPORT,
                            ),
                        ],
                    ),
                    SourceFile(
                        path="payments/client.py",
                        dependencies=[
                            Dependency(
                                source="payments/client.py",
                                target="invoices.api",
                                target_path="invoices/api.py",
                                kind=DependencyKind.IMPORT,
                            )
                        ],
                    ),
                    SourceFile(path="invoices/api.py"),
                ],
            )
        ]
    )


def _cyclic_system() -> System:
    system = _system()
    system.modules[0].files[2].dependencies.append(
        Dependency(
            source="invoices/api.py",
            target="orders.service",
            target_path="orders/service.py",
            kind=DependencyKind.IMPORT,
        )
    )
    return system
