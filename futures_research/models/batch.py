from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class BatchResearchItem(BaseModel):
    requested_symbol: str
    resolved_symbol: str = ""
    variety_code: str = ""
    variety: str = ""
    run_id: Optional[UUID] = None
    final_score: Optional[float] = None
    review_passed: bool = False
    status: str = "failed"
    error: Optional[str] = None


class BatchResearchSummary(BaseModel):
    batch_id: UUID = Field(default_factory=uuid4)
    target_date: date
    requested_symbols: List[str] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
    concurrency: int = 1
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    passed: int = 0
    marginal: int = 0
    average_score: Optional[float] = None
    items: List[BatchResearchItem] = Field(default_factory=list)
