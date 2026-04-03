from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class ReviewResult(BaseModel):
    round: int
    total_score: float
    passed: bool
    dimension_scores: Dict[str, float] = Field(default_factory=dict)
    feedback: str = ""
    blocking_issues: List[str] = Field(default_factory=list)
