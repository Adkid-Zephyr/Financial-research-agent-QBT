from __future__ import annotations

from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from futures_research import config
from futures_research.models.report import ResearchReport
from futures_research.models.review import ReviewResult


class WorkflowState(BaseModel):
    run_id: UUID = Field(default_factory=uuid4)
    symbol: str
    variety_code: str
    variety: str
    target_date: date
    current_step: str = "init"
    review_round: int = 0
    max_review_rounds: int = config.MAX_REVIEW_ROUNDS
    raw_data: Dict[str, Any] = Field(default_factory=dict)
    analysis_result: str = ""
    report_draft: str = ""
    review_result: Optional[ReviewResult] = None
    review_history: List[ReviewResult] = Field(default_factory=list)
    final_report: Optional[ResearchReport] = None
    data_sources_used: List[str] = Field(default_factory=list)
    error: Optional[str] = None
