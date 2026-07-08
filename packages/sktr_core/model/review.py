from __future__ import annotations

from pydantic import BaseModel, Field

from sktr_core.model.enums import IssueCategory, IssueSeverity
from sktr_core.model.knowledge import Location, System


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
    diff_summary: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class AIReview(BaseModel):
    summary: str | None = None
    recommendations: list[str] = Field(default_factory=list)
    model: str | None = None
    metadata: dict[str, str] = Field(default_factory=dict)


class ReviewResult(BaseModel):
    status: str
    context: ReviewContext = Field(default_factory=ReviewContext)
    system: System = Field(default_factory=System)
    issues: list[Issue] = Field(default_factory=list)
    ai_review: AIReview | None = None
    messages: list[str] = Field(default_factory=list)
    metadata: dict[str, str] = Field(default_factory=dict)
