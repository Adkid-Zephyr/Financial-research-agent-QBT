from __future__ import annotations

from pathlib import Path
from typing import Iterable, List

import yaml

from futures_research import config
from futures_research.models.variety import DataSourceConfig, VarietyDefinition


def load_ctp_contract_catalog(path: Path = config.CTP_CONTRACT_CATALOG_PATH) -> List[VarietyDefinition]:
    if not path.exists():
        return []
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [_build_catalog_variety(item) for item in payload.get("varieties", [])]


def merge_contracts(primary: Iterable[str], extra: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen = set()
    for contract in [*primary, *extra]:
        normalized = str(contract or "").strip().upper()
        if normalized and normalized not in seen:
            seen.add(normalized)
            merged.append(normalized)
    return merged


def merge_catalog_variety(curated: VarietyDefinition, catalog: VarietyDefinition) -> VarietyDefinition:
    return curated.model_copy(update={"contracts": merge_contracts(curated.contracts, catalog.contracts)})


def _build_catalog_variety(item: dict) -> VarietyDefinition:
    code = str(item.get("code") or "").strip().upper()
    name = str(item.get("name") or code).strip() or code
    contracts = [str(contract).strip().upper() for contract in item.get("contracts", []) if str(contract).strip()]
    return VarietyDefinition(
        code=code,
        name=name,
        exchange=str(item.get("exchange") or "").strip().upper(),
        contracts=contracts,
        key_factors=[
            "{name}主力合约盘面价格与成交活跃度".format(name=name),
            "{name}跨期结构与近远月价差变化".format(name=name),
            "{name}交易所库存、仓单和持仓变化".format(name=name),
            "宏观风险偏好与相关品种联动",
        ],
        news_keywords=[name, code],
        data_sources=[DataSourceConfig(type="ctp_snapshot")],
        prompt_template="default_futures",
    )
