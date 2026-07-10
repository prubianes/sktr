from __future__ import annotations

from pydantic import BaseModel, Field

from sktr_core.model.enums import DependencyKind, DependencyScope, DiagnosticSeverity, SymbolKind


class Location(BaseModel):
    file_path: str
    start_line: int | None = Field(default=None, ge=1)
    end_line: int | None = Field(default=None, ge=1)
    start_column: int | None = Field(default=None, ge=1)
    end_column: int | None = Field(default=None, ge=1)


class Symbol(BaseModel):
    name: str
    kind: SymbolKind = SymbolKind.UNKNOWN
    owner: str | None = None
    location: Location | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class Dependency(BaseModel):
    source: str
    target: str
    kind: DependencyKind = DependencyKind.UNKNOWN
    scope: DependencyScope = DependencyScope.UNKNOWN
    source_module: str | None = None
    target_module: str | None = None
    target_path: str | None = None
    location: Location | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class SourceFile(BaseModel):
    path: str
    language: str | None = None
    module: str | None = None
    symbols: list[Symbol] = Field(default_factory=list)
    dependencies: list[Dependency] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class Module(BaseModel):
    name: str
    path: str | None = None
    files: list[SourceFile] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)


class AnalysisDiagnostic(BaseModel):
    analyzer: str
    file_path: str
    severity: DiagnosticSeverity = DiagnosticSeverity.ERROR
    code: str
    message: str
    location: Location | None = None


class System(BaseModel):
    name: str = "current"
    modules: list[Module] = Field(default_factory=list)
    diagnostics: list[AnalysisDiagnostic] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
