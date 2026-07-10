from __future__ import annotations

from enum import StrEnum


class SymbolKind(StrEnum):
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    INTERFACE = "interface"
    TYPE = "type"
    VARIABLE = "variable"
    CONSTANT = "constant"
    UNKNOWN = "unknown"


class DependencyKind(StrEnum):
    IMPORT = "import"
    CALL = "call"
    EXTENDS = "extends"
    IMPLEMENTS = "implements"
    USES = "uses"
    REFERENCES = "references"
    UNKNOWN = "unknown"


class DependencyScope(StrEnum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    STANDARD_LIBRARY = "standard_library"
    UNKNOWN = "unknown"


class DiagnosticSeverity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class IssueSeverity(StrEnum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IssueCategory(StrEnum):
    ARCHITECTURE = "architecture"
    COUPLING = "coupling"
    MODULARITY = "modularity"
    MAINTAINABILITY = "maintainability"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    UNKNOWN = "unknown"
