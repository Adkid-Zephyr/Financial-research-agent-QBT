from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


DocumentFormat = Literal["markdown", "text", "pdf"]
ReviewStatus = Literal["pass", "revise", "fail"]
Severity = Literal["critical", "major", "minor"]


class ParsedDocument(BaseModel):
    filename: str
    format: DocumentFormat
    content: str
    char_count: int
    page_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DimensionScore(BaseModel):
    key: str
    label: str
    score: float
    max_score: float
    rationale: str


class ReviewFinding(BaseModel):
    severity: Severity
    title: str
    detail: str
    recommendation: str
    evidence: list[str] = Field(default_factory=list)
    target_sections: list[str] = Field(default_factory=list)


class ImprovementAction(BaseModel):
    priority: int
    title: str
    action: str
    target_sections: list[str] = Field(default_factory=list)


class ReviewArtifacts(BaseModel):
    markdown_path: str
    pdf_path: str
    json_path: str
    original_file_path: str


class ReviewResult(BaseModel):
    review_id: str
    created_at: datetime
    filename: str
    document_format: DocumentFormat
    overall_score: float
    status: ReviewStatus
    passed: bool
    executive_summary: str
    strengths: list[str] = Field(default_factory=list)
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    findings: list[ReviewFinding] = Field(default_factory=list)
    improvement_actions: list[ImprovementAction] = Field(default_factory=list)
    suggested_outline: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    artifacts: ReviewArtifacts


class ReviewResponse(BaseModel):
    review_id: str
    overall_score: float
    status: ReviewStatus
    passed: bool
    executive_summary: str
    strengths: list[str]
    findings: list[ReviewFinding]
    improvement_actions: list[ImprovementAction]
    download_urls: dict[str, str]


class StoredReviewBundle(BaseModel):
    result: ReviewResult
    markdown_content: str
