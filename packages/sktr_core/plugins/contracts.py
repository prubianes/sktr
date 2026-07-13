from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, Field

from sktr_core.model import AIReview, FileChange, Issue, ReviewContext, ReviewResult, System


class GitDiff(BaseModel):
    raw: str = ""
    repository_root: str | None = None
    changed_files: list[str] = Field(default_factory=list)
    file_changes: list[FileChange] = Field(default_factory=list)
    base_file_contents: dict[str, str] = Field(default_factory=dict)
    current_file_contents: dict[str, str] = Field(default_factory=dict)
    excluded_files: list[str] = Field(default_factory=list)
    repository_files: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class AnalysisContext(BaseModel):
    review: ReviewContext = Field(default_factory=ReviewContext)
    diff: GitDiff = Field(default_factory=GitDiff)


class AIReviewContext(BaseModel):
    review: ReviewContext = Field(default_factory=ReviewContext)
    system: System = Field(default_factory=System)
    issues: list[Issue] = Field(default_factory=list)


class GitProvider(Protocol):
    def current_diff(self) -> GitDiff: ...

    def changed_files(self) -> list[str]: ...


class Analyzer(Protocol):
    language: str

    def analyze(self, context: AnalysisContext) -> System: ...


class Rule(Protocol):
    id: str
    name: str

    def evaluate(self, system: System, context: ReviewContext) -> list[Issue]: ...


class AIProvider(Protocol):
    def review(self, context: AIReviewContext) -> AIReview: ...


class Output(Protocol):
    format: str

    def write(self, result: ReviewResult, destination: str | None = None) -> None: ...
