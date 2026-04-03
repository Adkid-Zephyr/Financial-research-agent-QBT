from __future__ import annotations

from futures_research.models.variety import VarietyDefinition
from futures_research.prompts.loader import PromptRepository


def build_aggregator_context(
    variety_definition: VarietyDefinition,
    prompt_repository: PromptRepository,
) -> str:
    return prompt_repository.load_market_template(variety_definition)
