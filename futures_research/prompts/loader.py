from __future__ import annotations

from pathlib import Path

from futures_research import config
from futures_research.models.variety import VarietyDefinition


class PromptRepository:
    def __init__(self, prompts_dir: Path = config.PROMPTS_DIR, variety_prompts_dir: Path = config.VARIETY_PROMPTS_DIR):
        self.prompts_dir = prompts_dir
        self.variety_prompts_dir = variety_prompts_dir

    def load_market_template(self, variety_definition: VarietyDefinition) -> str:
        override_path = self.variety_prompts_dir / ("%s.md" % variety_definition.code)
        if override_path.exists():
            template = override_path.read_text(encoding="utf-8")
        else:
            template_path = self.prompts_dir / ("%s.md" % variety_definition.prompt_template)
            template = template_path.read_text(encoding="utf-8")
        return template.format(
            code=variety_definition.code,
            name=variety_definition.name,
            exchange=variety_definition.exchange,
            contracts=", ".join(variety_definition.contracts),
            key_factors="；".join(variety_definition.key_factors),
            news_keywords="、".join(variety_definition.news_keywords),
        )
