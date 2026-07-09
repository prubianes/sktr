from __future__ import annotations

from pathlib import Path

from sktr_core.model import Dependency, DependencyKind, Module, SourceFile, System
from sktr_graph import GraphBuilder, GraphLevel, MermaidGraphOutput


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
                                kind=DependencyKind.IMPORT,
                            ),
                            Dependency(
                                source="orders/service.py",
                                target="payments.client",
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
                                kind=DependencyKind.IMPORT,
                            )
                        ],
                    ),
                    SourceFile(path="invoices/api.py"),
                ],
            )
        ]
    )
