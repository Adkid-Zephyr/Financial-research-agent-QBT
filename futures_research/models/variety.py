from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field, field_validator


class DataSourceConfig(BaseModel):
    type: str


class VarietyDefinition(BaseModel):
    code: str
    name: str
    exchange: str
    contracts: List[str] = Field(default_factory=list)
    key_factors: List[str] = Field(default_factory=list)
    news_keywords: List[str] = Field(default_factory=list)
    data_sources: List[DataSourceConfig] = Field(default_factory=list)
    prompt_template: str = "default_futures"

    @field_validator("news_keywords", mode="before")
    @classmethod
    def flatten_news_keywords(cls, value):
        if value is None:
            return []
        flattened = []
        for item in value:
            if isinstance(item, list):
                flattened.extend(str(token) for token in item)
            else:
                flattened.append(str(item))
        return flattened
