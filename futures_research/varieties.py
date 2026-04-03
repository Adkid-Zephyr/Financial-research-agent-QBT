from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional

import yaml

from futures_research import config
from futures_research.models.variety import VarietyDefinition


class VarietyRegistry:
    def __init__(self, varieties_dir: Path = config.VARIETIES_DIR):
        self.varieties_dir = varieties_dir
        self._varieties: Dict[str, VarietyDefinition] = {}

    def scan(self) -> None:
        self._varieties = {}
        if not self.varieties_dir.exists():
            return
        for path in sorted(self.varieties_dir.glob("*.yaml")):
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            variety = VarietyDefinition.model_validate(data)
            self._varieties[variety.code.upper()] = variety

    def register(self, variety: VarietyDefinition) -> None:
        self._varieties[variety.code.upper()] = variety

    def get(self, symbol_or_code: str) -> VarietyDefinition:
        normalized = symbol_or_code.upper()
        if normalized in self._varieties:
            return self._varieties[normalized]
        matched = self.match_contract(normalized)
        if matched is None:
            raise KeyError("No variety registered for '%s'" % symbol_or_code)
        return matched

    def match_contract(self, contract: str) -> Optional[VarietyDefinition]:
        for code, variety in self._varieties.items():
            if contract.startswith(code):
                return variety
        return None

    def resolve_contract(self, symbol_or_code: str) -> str:
        normalized = symbol_or_code.upper()
        if normalized in self._varieties:
            variety = self._varieties[normalized]
            if not variety.contracts:
                raise ValueError("Variety '%s' has no configured contracts" % normalized)
            return variety.contracts[0]
        return symbol_or_code.upper()

    def list_codes(self):
        return sorted(self._varieties.keys())
