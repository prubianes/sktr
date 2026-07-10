from __future__ import annotations

from pydantic import BaseModel, Field

from sktr_core.model.enums import IssueCategory, IssueSeverity
from sktr_core.model.knowledge import AnalysisDiagnostic, Location, System


class FileChange(BaseModel):
    path: str
    status: str
    added_lines: int = 0
    removed_lines: int = 0
    old_path: str | None = None


class Issue(BaseModel):
    id: str
    title: str
    description: str
    severity: IssueSeverity = IssueSeverity.INFO
    category: IssueCategory = IssueCategory.UNKNOWN
    location: Location | None = None
    rule_id: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewContext(BaseModel):
    changed_files: list[str] = Field(default_factory=list)
    file_changes: list[FileChange] = Field(default_factory=list)
    excluded_files: list[str] = Field(default_factory=list)
    diff_summary: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class AIRecommendation(BaseModel):
    title: str
    why: str
    suggested_action: str
    related_issue_ids: list[str] = Field(default_factory=list)
    related_files: list[str] = Field(default_factory=list)
    confidence: str | None = None


class AIReview(BaseModel):
    provider: str
    model: str | None = None
    overview: str | None = None
    recommendations: list[AIRecommendation] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewResult(BaseModel):
    status: str
    context: ReviewContext = Field(default_factory=ReviewContext)
    system: System = Field(default_factory=System)
    issues: list[Issue] = Field(default_factory=list)
    diagnostics: list[AnalysisDiagnostic] = Field(default_factory=list)
    ai_review: AIReview | None = None
    knowledge_summary: dict[str, int] = Field(default_factory=dict)
    messages: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
