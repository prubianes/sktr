from __future__ import annotations

from dataclasses import dataclass

from tree_sitter import Language, Node, Parser, Tree

from sktr_core.model import AnalysisDiagnostic, DiagnosticSeverity, Location


@dataclass(frozen=True)
class ParsedSource:
    source: bytes
    tree: Tree
    diagnostics: list[AnalysisDiagnostic]


class TreeSitterParser:
    def __init__(self, language_capsule: object, *, analyzer: str) -> None:
        self.parser = Parser(Language(language_capsule))
        self.analyzer = analyzer

    def parse(self, source: str, *, file_path: str) -> ParsedSource:
        encoded = source.encode("utf-8")
        tree = self.parser.parse(encoded)
        diagnostics = [
            AnalysisDiagnostic(
                analyzer=self.analyzer,
                file_path=file_path,
                severity=DiagnosticSeverity.ERROR,
                code="parse_error",
                message="The parser found invalid or incomplete syntax.",
                location=_location(file_path, node),
            )
            for node in walk(tree.root_node)
            if node.type == "ERROR" or node.is_missing
        ]
        return ParsedSource(source=encoded, tree=tree, diagnostics=_deduplicate(diagnostics))


def walk(node: Node):
    yield node
    for child in node.named_children:
        yield from walk(child)


def node_text(node: Node | None, source: bytes) -> str:
    if node is None:
        return ""
    return source[node.start_byte : node.end_byte].decode("utf-8")


def location(file_path: str, node: Node) -> Location:
    return _location(file_path, node)


def _location(file_path: str, node: Node) -> Location:
    return Location(
        file_path=file_path,
        start_line=node.start_point.row + 1,
        end_line=node.end_point.row + 1,
        start_column=node.start_point.column + 1,
        end_column=node.end_point.column + 1,
    )


def _deduplicate(diagnostics: list[AnalysisDiagnostic]) -> list[AnalysisDiagnostic]:
    seen: set[tuple[int | None, int | None]] = set()
    result: list[AnalysisDiagnostic] = []
    for diagnostic in diagnostics:
        key = (
            diagnostic.location.start_line if diagnostic.location else None,
            diagnostic.location.start_column if diagnostic.location else None,
        )
        if key not in seen:
            seen.add(key)
            result.append(diagnostic)
    return result
