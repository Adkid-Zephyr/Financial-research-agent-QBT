from __future__ import annotations

from datetime import date, datetime
from typing import Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ResearchReport(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    symbol: str
    variety_code: str
    variety: str
    target_date: date
    generated_at: datetime
    review_rounds: int
    final_score: float
    content: str
    summary: str
    sentiment: str
    confidence: str
    key_factors: List[str] = Field(default_factory=list)
    risk_points: List[str] = Field(default_factory=list)
    data_sources: List[str] = Field(default_factory=list)
    markdown_path: Optional[str] = None
    markdown_url: Optional[str] = None
    pdf_path: Optional[str] = None
    pdf_url: Optional[str] = None
    indicator_snapshots: Optional[Dict[str, str]] = None
    strategy_signals: Optional[List[str]] = None
