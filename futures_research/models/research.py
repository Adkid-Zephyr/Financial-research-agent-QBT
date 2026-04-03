from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class ResearchOption(BaseModel):
    id: str
    label: str
    description: str
    prompt_directive: str
    template_hint: str = ""


class VarietyOption(BaseModel):
    code: str
    name: str
    exchange: str
    contracts: List[str] = Field(default_factory=list)
    default_contract: str = ""
    key_factors: List[str] = Field(default_factory=list)


class ResearchProfile(BaseModel):
    horizon: str = "medium_term"
    persona: str = "futures_desk"
    user_focus: str = ""
    briefing_summary: str = ""
    key_points: List[str] = Field(default_factory=list)
    writing_directives: List[str] = Field(default_factory=list)
    recommended_template: str = ""


class ResearchPreview(BaseModel):
    resolved_symbol: str
    variety_code: str
    variety: str
    summary: str
    key_points: List[str] = Field(default_factory=list)
    writing_directives: List[str] = Field(default_factory=list)
    recommended_template: str = ""


class ResearchOptionsCatalog(BaseModel):
    varieties: List[VarietyOption] = Field(default_factory=list)
    horizons: List[ResearchOption] = Field(default_factory=list)
    personas: List[ResearchOption] = Field(default_factory=list)
