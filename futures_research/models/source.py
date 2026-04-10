from __future__ import annotations

from datetime import date
from typing import Dict, List

from pydantic import BaseModel, Field


class DataFetchRequest(BaseModel):
    variety_code: str
    variety_name: str
    contract: str
    contracts: List[str] = Field(default_factory=list)
    target_date: date
    exchange: str
    key_factors: List[str] = Field(default_factory=list)
    news_keywords: List[str] = Field(default_factory=list)


class SourcePayload(BaseModel):
    source_type: str
    summary: str
    highlights: List[str] = Field(default_factory=list)
    metrics: Dict[str, str] = Field(default_factory=dict)
    sources: List[str] = Field(default_factory=list)
    raw_items: List[Dict[str, str]] = Field(default_factory=list)
